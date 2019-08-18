from datetime import timedelta

import pytz
from flask import _app_ctx_stack
from mitoc_const import affiliations

from member.errors import IncorrectPayment, InvalidAffiliation
from member.extensions import mysql

# Map from the two-letter codes in MITOC Trips to the affiliation strings in the geardb,
# as well as the expected price for that membership level
AFFILIATION_MAPPING = {
    aff.CODE: (aff.VALUE, aff.ANNUAL_DUES) for aff in affiliations.ALL
}


EST = pytz.timezone('US/Eastern')  # GMT-4 or GMT-5, depending on DST


def get_db():
    """ Opens a new connection if not already in current app context. """
    top = _app_ctx_stack.top
    if not hasattr(top, 'conn'):
        top.conn = mysql.connect()
    return top.conn


def close_db(_exception):
    """Closes the database again at the end of the request."""
    top = _app_ctx_stack.top
    if hasattr(top, 'conn'):
        top.conn.close()


def commit():
    """ Commit the current transaction. """
    get_db().commit()


def add_person(first, last, email):
    """ Create a new person in the gear database.

    This is only to be done when we cannot find an existing membership
    under any known email addresses.
    """
    cursor = get_db().cursor()
    cursor.execute(
        '''
        -- Omitted columns (left `null`):
        -- * phone: Tracked by mitoc-trips, and CyberSource only gives the billing phone
        -- * affiliation: better tracked by people_memberships OR by mitoc-trips
        -- * city & state: we've historically not bothered tracking
        insert into people (firstname, lastname, email, mitoc_credit, date_inserted)
        values (%(first)s, %(last)s, %(email)s, 0, now())
        ''',
        {'first': first, 'last': last, 'email': email},
    )
    return cursor.lastrowid


def current_membership_expires(person_id):
    """ Returns the date on which the current membership expires.

    If there's no current membership, `None` is returned.
    """
    cursor = get_db().cursor()
    cursor.execute(
        '''
        select max(expires)
          from people_memberships
         where person_id = %(person_id)s
           and expires > now()
        ''',
        {'person_id': person_id},
    )
    return cursor.fetchone()[0]


def membership_start(person_id, datetime_paid):
    """ Return the date on which a 12-month membership should start.

    This method enables participants to pay for a membership before their
    last one expires without losing the remaining days.

    For example, if a participant has already have paid their membership dues
    through December 15th, and it's late November, paying dues again should
    allow their membership to be valid through December 15th of the next year.

    First-time members (or already-expired members) will obviously have
    memberships valid one calendar year from the datetime they paid.
    """
    date_paid = EST.fromutc(datetime_paid).date()

    future_expiration = current_membership_expires(person_id)
    if not future_expiration:  # New member, or already expired
        return date_paid

    # If the membership expires some time in the next 40 days,
    # then the next membership should be valid for one year after the expiration
    if (future_expiration - date_paid) < timedelta(days=40):
        return future_expiration

    return date_paid


def update_affiliation(person_id, affiliation):
    """ Update the current affiliation known for the person. """
    if affiliation not in {aff.VALUE for aff in affiliations.ALL}:
        raise ValueError(f"Unknown affiliation! {affiliation}")

    db = get_db()
    cursor = db.cursor()

    # We store the member's current affiliation directly on `people`
    cursor.execute(
        '''
        update people
           set affiliation = %(affiliation)s
         where id = %(person_id)s
        ''',
        {'affiliation': affiliation, 'person_id': person_id},
    )


def add_membership(person_id, price_paid, datetime_paid, two_letter_affiliation_code):
    """ Add a membership payment for an existing MITOC member. """
    db = get_db()
    cursor = db.cursor()
    try:
        affiliation, expected_price = AFFILIATION_MAPPING[two_letter_affiliation_code]
    except KeyError:
        raise InvalidAffiliation(f"{two_letter_affiliation_code} is not a recognized")

    # Because form data can be manipulated by users, it's perfectly possible to charge
    # yourself $1, and have a valid callback to this endpoint. Ensure that users
    # are actually paying the value we expect
    if expected_price != float(price_paid):
        raise IncorrectPayment(f"Expected {expected_price}, got {price_paid}")

    cursor.execute(
        '''
        insert into people_memberships
               (person_id, price_paid, membership_type, date_inserted, expires)
        values (%(person_id)s, %(price_paid)s, %(membership_type)s, now(),
                date_add(%(membership_start)s, interval 1 year))
        ''',
        {
            'person_id': person_id,
            'price_paid': price_paid,
            'membership_type': two_letter_affiliation_code,
            'membership_start': membership_start(person_id, datetime_paid),
        },
    )

    update_affiliation(person_id, affiliation)
    db.commit()

    # MySQL doesn't support `returning` :(
    cursor.execute(
        '''
        select id, expires
          from people_memberships
         where id = %(membership_id)s
        ''',
        {'membership_id': cursor.lastrowid},
    )
    membership_id, date_expires = cursor.fetchone()
    return membership_id, date_expires


def add_waiver(person_id, datetime_signed):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        '''
        insert into people_waivers
               (person_id, date_signed, expires)
        values (%(person_id)s, %(datetime_signed)s,
                date_add(%(datetime_signed)s, interval 1 year))
        ''',
        {'person_id': person_id, 'datetime_signed': datetime_signed},
    )

    db.commit()

    # MySQL doesn't support `returning` :(
    cursor.execute(
        '''
        select id, date(expires)
          from people_waivers
         where id = %(waiver_id)s
        ''',
        {'waiver_id': cursor.lastrowid},
    )
    waiver_id, date_expires = cursor.fetchone()
    return waiver_id, date_expires


def already_added_waiver(person_id, date_signed):
    """ Return if this person already has a waiver on this date.

    We want to avoid processing the same waiver twice. Even if the participant
    signs the waiver twico in one day, it doesn't matter if we insert another
    record.
    """
    cursor = get_db().cursor()
    cursor.execute(
        '''
        select exists(
          select 1
            from people_waivers
           -- date_signed is actually a timestamp
           where person_id = %(person_id)s
             and date(date_signed) = date(%(date_signed)s)
        ) as already_inserted
        ''',
        {'person_id': person_id, 'date_signed': date_signed},
    )
    return bool(cursor.fetchone()[0])


def already_inserted_membership(person_id, date_effective):
    """ Return if a membership was already created for this day.

    We don't use date_inserted since we could have manually added in a
    membership with a different date.
    """
    cursor = get_db().cursor()
    cursor.execute(
        '''
        select exists(
          select 1
            from people_memberships
           where person_id = %(person_id)s
             and expires = date(date_add(%(date_effective)s, interval 1 year))
        ) as already_inserted
        ''',
        {'person_id': person_id, 'date_effective': date_effective},
    )
    return bool(cursor.fetchone()[0])


def person_to_update(primary_email, all_emails):
    """ Return the person which was most recently updated.

    In the future, we should employ automatic merging of accounts so
    that this logic isn't very necessary.
    """
    cursor = get_db().cursor()
    cursor.execute(
        '''
        select t.id
          from (select p.id,
                       nullif(
                         greatest(coalesce(max(pm.expires), from_unixtime(0)),
                                  coalesce(max(pw.expires), from_unixtime(0))),
                         from_unixtime(0)
                       ) as last_update
                  from people p
                       left join people_memberships  pm on p.id = pm.person_id
                       left join geardb_peopleemails pe on p.id = pe.person_id
                       left join people_waivers      pw on p.id = pw.person_id
                 where p.email            in %(all_emails)s
                    or pe.alternate_email in %(all_emails)s
                 group by p.id
               ) t
        -- Return accounts in the following order:
        -- 1. Any accounts that have an active membership/waiver
        -- 2. The most recent account matching any verified email
        -- (The plus symbol is how we express 'nulls last')
         order by +(t.last_update > date_sub(now(), interval 1 year)) desc,
                  +t.last_update desc;
        ''',
        {'primary_email': primary_email, 'all_emails': all_emails},
    )
    person = cursor.fetchone()
    return person and person[0]

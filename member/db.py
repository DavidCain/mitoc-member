from .extensions import mysql
from flask import _app_ctx_stack


def get_db():
    """ Opens a new connection if not already in current app context. """
    top = _app_ctx_stack.top
    if not hasattr(top, 'conn'):
        top.conn = mysql.connect()
    return top.conn


def commit():
    get_db().commit()


def get_affiliation(amount):
    """ There's no CyberSource field for affiliation, so deduce from cost. """
    # See enum on people_memberships.affiliation
    return {15: 'student', 20: 'affiliate', 25: 'general'}[int(amount)]


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
        insert into people (firstname, lastname, email, desk_credit, date_inserted)
        values (%(first)s, %(last)s, %(email)s, 0, now())
        ''', {'first': first, 'last': last, 'email': email}
    )
    return cursor.lastrowid


def add_membership(person_id, price_paid, datetime_paid):
    """ Add a membership payment for an existing MITOC member. """
    cursor = get_db().cursor()
    cursor.execute(
        '''
        insert into people_memberships
               (person_id, price_paid, membership_type, date_inserted, expires)
        values (%(person_id)s, %(price_paid)s, %(membership_type)s, now(),
                date(date_add(%(datetime_paid)s, interval 1 year)))
        ''', {'person_id': person_id,
              'price_paid': price_paid,
              'membership_type': get_affiliation(price_paid),
              'datetime_paid': datetime_paid}
    )
    return cursor.lastrowid


def add_waiver(person_id, datetime_signed):
    cursor = get_db().cursor()
    cursor.execute(
        '''
        insert into people_waivers
               (person_id, date_signed, expires)
        values (%(person_id)s, %(datetime_signed)s,
                date_add(%(datetime_signed)s, interval 1 year))
        ''', {'person_id': person_id,
              'datetime_signed': datetime_signed}
    )
    return cursor.lastrowid


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
        ''', {'person_id': person_id, 'date_signed': date_signed}
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
        ''', {'person_id': person_id, 'date_effective': date_effective}
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
                       left join people_memberships pm on p.id = pm.person_id
                       left join gear_peopleemails  pe on p.id = pe.person_id
                       left join people_waivers     pw on p.id = pw.person_id
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
        ''', {'primary_email': primary_email, 'all_emails': all_emails}
    )
    person = cursor.fetchone()
    return person and person[0]

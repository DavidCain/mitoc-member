from .extensions import mysql


def person_to_update(primary_email, all_emails):
    """ Return the person which was most recently updated.

    In the future, we should employ automatic merging of accounts so
    that this logic isn't very necessary.
    """
    cursor = mysql.connect().cursor()
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

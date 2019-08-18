import json
from datetime import datetime
from urllib.request import Request, urlopen

from member.trips_api import bearer_jwt


def other_verified_emails(email_address):
    """ Return other email addresses known to be owned by the same person.

    We do a good job of maintaining one account per person on mitoc-trips.
    In the authentication model, individual users maintain a list of verified
    email addresses that belong to them. As MIT students become alumni, people
    change jobs, or abandon old email addresses, they update their email addresses
    on the trips site. However, people only update their waivers or memberships
    once a year.

    So, when an unknown individual provides an email address for their
    membership payment, the MITOC Trips site is our best shot at identifying who
    they are. The site can give us a complete list of prior email addreses, which we
    can then attempt to match to their MITOC account (one or more of those addresses
    may be affiliated with the MITOC account).

    Since we don't want to give away members' email information freely, we sign
    each request with a secret key. The API endpoint will reject our request
    without a valid signature.
    """
    request = Request('https://mitoc-trips.mit.edu/data/verified_emails/', method='GET')
    request.add_header('Authorization', bearer_jwt(email=email_address))
    with urlopen(request) as response:
        data = json.loads(response.read())

    return (data['primary'], data['emails'])


def update_membership(email_address, membership_expires=None, waiver_expires=None):
    """ Inform mitoc-trips that a waiver or membership has been processed.

    MITOC Trips maintains its own cache of when a participant's waiver and/or
    membership will expire. Because this data changes rarely, it's more
    efficient to cache expiration dates locally. However, when this system receives
    a new waiver or membership, we should inform the system that the cache is now
    invalid, and that it should be updated.
    """
    request = Request('https://mitoc-trips.mit.edu/data/membership/', method='POST')

    payload = {'email': email_address}

    def format_date(dt):
        """ Format the date from a datetime OR date object in ISO-8601. """
        return datetime.strftime(dt, '%Y-%m-%d')  # isoformat() only works on date

    if membership_expires:
        payload['membership_expires'] = format_date(membership_expires)
    if waiver_expires:
        payload['waiver_expires'] = format_date(waiver_expires)

    request.add_header('Authorization', bearer_jwt(**payload))
    with urlopen(request) as response:
        return json.loads(response.read())

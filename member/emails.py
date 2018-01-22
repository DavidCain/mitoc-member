from datetime import datetime, timedelta
import json
from urllib.request import Request, urlopen

from flask import current_app
import jwt


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
    secret = current_app.config['MEMBERSHIP_SECRET_KEY']
    expires = datetime.utcnow() + timedelta(minutes=15)
    token = jwt.encode({'email': email_address, 'exp': expires}, secret)

    request = Request('https://mitoc-trips.mit.edu/data/verified_emails/')
    request.add_header('Authorization', 'Bearer: {}'.format(token))
    with urlopen(request) as response:
        data = json.loads(response.read())

    return (data['primary'], data['emails'])

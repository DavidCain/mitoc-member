from flask import current_app

import base64
import hashlib
import hmac
import json
from urllib.parse import urlencode
from urllib.request import urlopen


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
    email = email_address.encode('utf-8')
    secret = current_app.config['MEMBERSHIP_SECRET_KEY'].encode('utf-8')
    msg_hmac = hmac.new(secret, email, hashlib.sha256)
    signed = base64.b64encode(msg_hmac.digest())

    qs = urlencode({'email': email, 'signature': signed})
    url = 'https://mitoc-trips.mit.edu/data/verified_emails?{}'.format(qs)
    with urlopen(url) as response:
        data = json.loads(response.read())

    return (data['primary'], data['emails'])

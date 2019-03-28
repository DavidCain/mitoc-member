from datetime import datetime, timedelta

import jwt
from flask import current_app


def bearer_jwt(**kwargs):
    """ Express a JWT for use on mitoc-trips.mit.edu as a bearer token.

    The API there expects a token signed with a shared key - without this token,
    authorized routes will be denied access.
    """
    secret = current_app.config['MEMBERSHIP_SECRET_KEY']
    expires = datetime.utcnow() + timedelta(minutes=15)
    token = jwt.encode({**kwargs, 'exp': expires}, secret)
    return 'Bearer: {}'.format(token.decode('UTF-8'))

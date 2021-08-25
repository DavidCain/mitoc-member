from datetime import datetime, timedelta

import jwt
from flask import current_app


def bearer_jwt(**kwargs) -> str:
    """Express a JWT for use on mitoc-trips.mit.edu as a bearer token.

    The API there expects a token signed with a shared key - without this token,
    authorized routes will be denied access.
    """
    secret = current_app.config['MEMBERSHIP_SECRET_KEY']
    expires = datetime.utcnow() + timedelta(minutes=15)
    token: str = jwt.encode({**kwargs, 'exp': expires}, secret, algorithm='HS512')
    assert isinstance(token, str), "Unexpected token type. Install PyJWT 2?"

    return 'Bearer: ' + token  # Concatenate, since f-strings would tolerate `bytes`

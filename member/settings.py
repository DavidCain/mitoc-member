import os

VERIFY_CYBERSOURCE_SIGNATURE = (
    os.getenv('VERIFY_CYBERSOURCE_SIGNATURE', 'true') == 'true'
)

CYBERSOURCE_SECRET_KEY = os.getenv(
    'CYBERSOURCE_SECRET_KEY', 'Secret key used to sign CyberSource'
)

MEMBERSHIP_SECRET_KEY = os.getenv(
    'MEMBERSHIP_SECRET_KEY', 'secret shared with mitoc-trips'
)

MYSQL_DATABASE_DB = os.getenv('GEAR_DATABASE_NAME', 'geardb')
MYSQL_DATABASE_USER = os.getenv('GEAR_DATABASE_USER', 'ws')
MYSQL_DATABASE_PASSWORD = os.getenv('GEAR_DATABASE_PASSWORD', 'password')
MYSQL_DATABASE_HOST = os.getenv('GEAR_DATABASE_HOST', 'localhost')
MYSQL_DATABASE_PORT = int(os.getenv('GEAR_DATABASE_PORT', '3306'))

# Silences Werkzeug XHR deprecation warnings. Can be removed once we're on Flask 1.x
# See: https://github.com/pallets/flask/issues/2549
JSONIFY_PRETTYPRINT_REGULAR = False

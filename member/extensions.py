import os

from flaskext.mysql import MySQL
from raven.contrib.flask import Sentry

mysql = MySQL()

RAVEN_DSN = os.getenv('RAVEN_DSN')
sentry = Sentry(dsn=RAVEN_DSN) if RAVEN_DSN else None

import os

from flask import Flask
from raven.contrib.flask import Sentry

from member import public
from member.extensions import mysql


RAVEN_DSN = os.getenv('RAVEN_DSN')
sentry = Sentry(dsn=RAVEN_DSN) if RAVEN_DSN else None


def create_app():
    app = Flask(__name__)
    app.config.from_object('member.settings')
    app.register_blueprint(public.views.blueprint)

    mysql.init_app(app)
    if sentry:
        sentry.init_app(app)
    return app

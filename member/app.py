from flask import Flask

from member import db, public
from member.extensions import mysql, sentry


def create_app():
    app = Flask(__name__)
    app.config.from_object('member.settings')
    app.register_blueprint(public.views.blueprint)
    app.teardown_appcontext(db.close_db)

    mysql.init_app(app)
    if sentry:
        sentry.init_app(app)

    return app

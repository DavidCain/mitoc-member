from flask import Flask

from member import db, extensions, public


def create_app():
    app = Flask(__name__)
    app.config.from_object('member.settings')
    app.register_blueprint(public.views.blueprint)
    app.teardown_appcontext(db.close_db)

    _initialize_extensions(app)

    return app


def _initialize_extensions(app):
    extensions.mysql.init_app(app)
    if extensions.sentry:
        extensions.sentry.init_app(app)

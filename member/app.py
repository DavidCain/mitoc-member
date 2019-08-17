from flask import Flask, _app_ctx_stack

from member import public
from member.extensions import mysql, sentry


def create_app():
    app = Flask(__name__)
    app.config.from_object('member.settings')
    app.register_blueprint(public.views.blueprint)
    register_teardowns(app)

    mysql.init_app(app)
    if sentry:
        sentry.init_app(app)

    return app


def register_teardowns(app):
    @app.teardown_appcontext
    def close_db_connection(_exception):  # pylint: disable=unused-variable
        """Closes the database again at the end of the request."""
        top = _app_ctx_stack.top
        if hasattr(top, 'conn'):
            top.conn.close()

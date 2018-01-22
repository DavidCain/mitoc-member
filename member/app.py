from flask import Flask

from member import public
from member.extensions import mysql


def create_app():
    app = Flask(__name__)
    app.config.from_object('member.settings')
    app.register_blueprint(public.views.blueprint)

    mysql.init_app(app)
    return app

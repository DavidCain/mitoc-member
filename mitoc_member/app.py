from flask import Flask

from mitoc_member import public
from mitoc_member.extensions import mysql


def create_app():
    app = Flask(__name__)
    app.config.from_object('mitoc_member.settings')
    app.register_blueprint(public.views.blueprint)

    mysql.init_app(app)
    return app

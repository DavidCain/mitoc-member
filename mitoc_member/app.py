from flask import Flask

from mitoc_member import public


def create_app():
    app = Flask(__name__)
    app.config.from_object('mitoc_member.settings')
    app.register_blueprint(public.views.blueprint)

    return app

from flask import Blueprint, json

blueprint = Blueprint('public', __name__)


@blueprint.route("/membership", methods=["POST"])
def add_membership():
    return json.jsonify()


@blueprint.route("/waiver", methods=["POST"])
def add_waiver():
    return json.jsonify()

from datetime import datetime

from flask import Blueprint, current_app, json, request

from mitoc_member.emails import other_verified_emails
from mitoc_member.signature import SecureAcceptanceSigner

blueprint = Blueprint('public', __name__)


@blueprint.route("/membership", methods=["POST"])
def add_membership():
    """ Process a CyberSource transaction & create/update membership. """
    data = request.form
    if data['req_merchant_defined_data1'] != 'membership':
        return json.jsonify(), 204  # Some other payment, we don't care

    secret_key = current_app.config['MEMBERSHIP_SECRET_KEY']
    signature_check = SecureAcceptanceSigner(secret_key)
    if not signature_check.verify_request(data):
        return json.jsonify(), 401

    # From the given email, ask the trips database for all their verified emails
    email = data['req_merchant_defined_data3']  # NOT req_bill_to_email
    primary, all_emails = other_verified_emails(email)

    # If no membership exists, create one under the primary email

    # Translate cost amount to membership level
    amount = data['req_amount']

    # Add membership
    datetime_paid = datetime.strptime(data['signed_date_time'], "%Y-%m-%dT%H:%M:%SZ")

    # Consider firing off an alert about dupes
    return json.jsonify(), 201


@blueprint.route("/waiver", methods=["POST"])
def add_waiver():
    return json.jsonify()

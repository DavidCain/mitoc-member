from datetime import datetime

from flask import Blueprint, current_app, json, request

from mitoc_member.emails import other_verified_emails
from mitoc_member.signature import SecureAcceptanceSigner
from mitoc_member import db

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

    # Fetch membership, ideally for primary email, but otherwise most recent
    person_id = db.person_to_update(primary, all_emails)
    if person_id and db.already_inserted_membership(person_id):
        return json.jsonify(), 202  # Most likely already processed

    # If no membership exists, create one under the primary email
    if not person_id:
        first_name = data['req_bill_to_forename']
        last_name = data['req_bill_to_surname']
        person_id = db.add_person(first_name, last_name, primary)

    datetime_paid = datetime.strptime(data['signed_date_time'], "%Y-%m-%dT%H:%M:%SZ")
    db.add_membership(person_id, data['req_amount'], datetime_paid)

    # TODO: Consider firing off an alert if duplicate memberships were detected
    return json.jsonify(), 201


@blueprint.route("/waiver", methods=["POST"])
def add_waiver():
    """ Process a DocuSign waiver completion.

    Currently, MITOC memberships are all processed through RightSignature. """
    return json.jsonify()

from datetime import datetime

from flask import Blueprint, current_app, json, request

from member.envelopes import CompletedEnvelope
from member.emails import other_verified_emails
from member.signature import SecureAcceptanceSigner
from member import db

blueprint = Blueprint('public', __name__)


@blueprint.route("/members/membership", methods=["POST"])
def add_membership():
    """ Process a CyberSource transaction & create/update membership. """
    data = request.form
    if data['req_merchant_defined_data1'] != 'membership':
        return json.jsonify(), 204  # Some other payment, we don't care

    secret_key = current_app.config['MEMBERSHIP_SECRET_KEY']
    signature_check = SecureAcceptanceSigner(secret_key)
    try:
        signature_verified = signature_check.verify_request(data)
    except ValueError:
        signature_verified = False
    if not signature_verified:
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
    db.commit()

    # TODO: Consider firing off an alert if duplicate memberships were detected
    return json.jsonify(), 201


@blueprint.route("/members/waiver", methods=["POST"])
def add_waiver():
    """ Process a DocuSign waiver completion.

    NOTE: It's extremely important that there be some access control behind
    this route. It parses XML directly, so it must come from a trusted source
    (the xml library is vulnerable to the 'billion laughs' and quadratic blowup
    vulnerabilities). Obviously, this route also inserts rows into a database,
    so we should only be doing that based on verified information.

    DocuSign event notifications are signed with their X.509 certificate, which
    should be verified with NGINX, Apache, or similar before being forwarded to
    this route.
    """
    env = CompletedEnvelope(request.data)
    email, time_signed = env.releasor_email, env.time_signed

    primary, all_emails = other_verified_emails(email)
    person_id = db.person_to_update(primary, all_emails)
    if not person_id:
        return json.jsonify()
        # NOTE: We should create a person, assign them the affiliation given in the doc
        # (first_name and last_name are not currently implemented)
        person_id = db.add_person(env.first_name, env.last_name, primary)

    if not db.already_added_waiver(person_id, time_signed):
        db.add_waiver(person_id, time_signed)
    db.commit()

    return json.jsonify()

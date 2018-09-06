from datetime import datetime
from urllib.error import URLError

from flask import Blueprint, current_app, json, request

from member.envelopes import CompletedEnvelope
from member.emails import other_verified_emails, update_membership
from member.extensions import sentry
from member.utils import CYBERSOURCE_DT_FORMAT
from member.signature import signature_valid
from member import db

blueprint = Blueprint('public', __name__)


@blueprint.route("/members/membership", methods=["POST"])
def add_membership():
    """ Process a CyberSource transaction & create/update membership. """
    data = request.form
    if data['decision'] != 'ACCEPT':
        return json.jsonify(), 204  # Transaction canceled, declined, etc.
    if data['req_merchant_defined_data1'] != 'membership':
        return json.jsonify(), 204  # Some other payment, we don't care

    # If we lack the secret key to verify signatures, we can rely on the web
    # server itself to provide access control (and skip signature verification)
    if current_app.config['VERIFY_CYBERSOURCE_SIGNATURE']:
        secret_key = current_app.config['CYBERSOURCE_SECRET_KEY']
        if not signature_valid(data, secret_key):
            return json.jsonify(), 401

    # From the given email, ask the trips database for all their verified emails
    email = data['req_merchant_defined_data3']  # NOT req_bill_to_email
    primary, all_emails = other_verified_emails(email)

    # Identify datetime (in UTC) when the transaction was completed
    dt_paid = datetime.strptime(data['signed_date_time'], CYBERSOURCE_DT_FORMAT)

    # Fetch membership, ideally for primary email, but otherwise most recent
    person_id = db.person_to_update(primary, all_emails)
    if person_id and db.already_inserted_membership(person_id, dt_paid):
        return json.jsonify(), 202  # Most likely already processed

    # If no membership exists, create one under the primary email
    if not person_id:
        first_name = data['req_bill_to_forename']
        last_name = data['req_bill_to_surname']
        person_id = db.add_person(first_name, last_name, primary)

    mem_id, expires = db.add_membership(person_id, data['req_amount'], dt_paid)
    db.commit()

    try:
        update_membership(primary, membership_expires=expires)
    except URLError:
        if sentry:
            sentry.captureException()

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
    if not env.completed:
        return json.jsonify(), 204  # Still awaiting guardian's signature

    email, time_signed = env.releasor_email, env.time_signed

    primary, all_emails = other_verified_emails(email)
    person_id = db.person_to_update(primary, all_emails)
    if not person_id:
        person_id = db.add_person(env.first_name, env.last_name, primary)

    if db.already_added_waiver(person_id, time_signed):
        return json.jsonify(), 204  # Nothing more to do

    waiver_id, expires = db.add_waiver(person_id, time_signed)
    db.commit()

    try:
        update_membership(primary, waiver_expires=expires)
    except URLError:
        if sentry:
            sentry.captureException()

    return json.jsonify(), 201

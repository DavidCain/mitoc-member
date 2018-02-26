from datetime import datetime

from member import db
from member.emails import other_verified_emails


def update_membership(verified_payload):
    """ Accepts a signed & verified CyberSource payload & updates membership.

    This will also handle creating the user if needed.
    """
    data = verified_payload

    # From the given email, ask the trips database for all their verified emails
    email = data['req_merchant_defined_data3']  # NOT req_bill_to_email
    primary, all_emails = other_verified_emails(email)

    # Fetch membership, ideally for primary email, but otherwise most recent
    person_id = db.person_to_update(primary, all_emails)
    if person_id and db.already_inserted_membership(person_id):
        return  # Most likely already processed

    # If no membership exists, create one under the primary email
    if not person_id:
        first_name = data['req_bill_to_forename']
        last_name = data['req_bill_to_surname']
        person_id = db.add_person(first_name, last_name, primary)

    datetime_paid = datetime.strptime(data['signed_date_time'], "%Y-%m-%dT%H:%M:%SZ")
    db.add_membership(person_id, data['req_amount'], datetime_paid)

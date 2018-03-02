from datetime import datetime
import unittest
import unittest.mock

from member.app import create_app


class TestMembershipView(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.config['CYBERSOURCE_SECRET_KEY'] = 'secret-key'

    def test_non_membership_transactions_ignored(self):
        """ Any CyberSource transaction not for membership is ignored. """
        response = self.client.post('/members/membership', data={
            'req_merchant_defined_data1': 'rental',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
            'signature': 'xeOwZZ+8Ttm378U7zIssIt+DuP7NEsq/1pQz3bI5XuE='
        })
        self.assertEqual(response.status_code, 204)

    def test_no_signed_field_names(self):
        """ When 'signed_field_names' is absent, a 401 is returned. """
        response = self.client.post('/members/membership', data={
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
            'signature': 'OL+mhpby4+mpXLY7ZidQhs7MELu7+iRU6cIwr0M96m8='
        })
        self.assertEqual(response.status_code, 401)

    def test_invalid_signature(self):
        """ We 401 when signed names are present, but signature is invalid. """
        response = self.client.post('/members/membership', data={
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
            'signature': 'this-signature-is-invalid',
            'signed_field_names': ('req_merchant_defined_data1,'
                                   'req_merchant_defined_data3,'
                                   'auth_amount')
        })
        self.assertEqual(response.status_code, 401)

    @unittest.mock.patch('member.public.views.db')
    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_duplicate_requests_handled(self, verified_emails, db):
        """ Test idempotency of the membership route.

        When the same membership transaction is POSTed to the API, we don't
        create or update anything.
        """
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        # There's already a person_id in the database for this person,
        # and this particular membership record was already inserted
        db.person_to_update.return_value = 62
        db.already_inserted_membership.return_value = True

        # We submit a valid signature for a membership, but get a 202:
        # the membership has already been processed
        response = self.client.post('/members/membership', data={
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
            'signed_field_names': ('req_merchant_defined_data1,'
                                   'req_merchant_defined_data3,'
                                   'auth_amount'),
            'signature': 'OL+mhpby4+mpXLY7ZidQhs7MELu7+iRU6cIwr0M96m8=',
        })
        self.assertEqual(response.status_code, 202)

        db.add_person.assert_not_called()
        db.add_membership.assert_not_called()

    @unittest.mock.patch('member.public.views.db')
    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_update_membership(self, verified_emails, db):
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        # There's already a person_id in the database for this person,
        # but the record has not yet been processed
        db.person_to_update.return_value = 62
        db.already_inserted_membership.return_value = False

        payload = {
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
            'req_amount': '15.00',
            'signed_date_time': '2018-01-23T18:37:32Z',
            'signed_field_names': ('req_merchant_defined_data1,'
                                   'req_merchant_defined_data3,'
                                   'auth_amount,'
                                   'req_amount,'
                                   'signed_date_time'),
            'signature': '1kNDS/E4NSzoVHy0A+SGYRslFX2a7i9W95O12TdCbHA=',
        }
        response = self.client.post('/members/membership', data=payload)
        self.assertEqual(response.status_code, 201)

        # The person exists - so they should not be created
        db.add_person.assert_not_called()

        # Instead, they were updated
        datetime_paid = datetime.strptime(payload['signed_date_time'],
                                          "%Y-%m-%dT%H:%M:%SZ")
        db.add_membership.assert_called_with(62, '15.00', datetime_paid)

    @unittest.mock.patch('member.public.views.db')
    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_new_membership(self, verified_emails, db):
        """ We create a new person record when somebody is new to MITOC. """
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        db.person_to_update.return_value = None  # New to MITOC
        db.add_person.return_value = 128  # After creating, person_id returned

        payload = {
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'req_bill_to_forename': 'Tim',
            'req_bill_to_surname': 'Beaver',
            'auth_amount': '15.00',
            'req_amount': '15.00',
            'signed_date_time': '2018-01-24T21:48:32Z',
            'signed_field_names': ('req_merchant_defined_data1,'
                                   'req_merchant_defined_data3,'
                                   'req_bill_to_forename,'
                                   'req_bill_to_surname,'
                                   'auth_amount,'
                                   'req_amount,'
                                   'signed_date_time'),
            'signature': 'HVML3j2W675QMWfUN7AqXRsts1/LEnsN8yDGt0Yd/BY=',
        }
        response = self.client.post('/members/membership', data=payload)
        self.assertEqual(response.status_code, 201)

        # A new person record needs to be created
        db.add_person.assert_called_with(payload['req_bill_to_forename'],
                                         payload['req_bill_to_surname'],
                                         'mitoc-member@example.com')

        # The membership is then inserted for the new person
        datetime_paid = datetime.strptime(payload['signed_date_time'],
                                          "%Y-%m-%dT%H:%M:%SZ")
        db.add_membership.assert_called_with(128, '15.00', datetime_paid)

from datetime import datetime, timedelta
import unittest
import unittest.mock
from urllib.error import URLError

from member.app import create_app
from member.utils import CYBERSOURCE_DT_FORMAT
from member.signature import SecureAcceptanceSigner


def one_year_later():
    return datetime.now().date() + timedelta(days=365)


def cybersource_now():
    """ Return the current datetime formatted as CyberSource does. """
    return datetime.strftime(datetime.now(), CYBERSOURCE_DT_FORMAT)


class MembershipViewTests(unittest.TestCase):
    def setUp(self):
        self.patchers = [unittest.mock.patch('member.public.views.db'),
                         unittest.mock.patch('member.public.views.update_membership')]
        self.db, self.update_membership = [p.start() for p in self.patchers]

        self.app = create_app()
        self.client = self.app.test_client()
        self.app.config['CYBERSOURCE_SECRET_KEY'] = 'secret-key'
        self.signer = SecureAcceptanceSigner('secret-key')

    def configure_normal_update(self):
        """ Configure mocks to indicate a person already in the db.

        In this situation, the membership update has not yet been processed.
        """
        self.db.person_to_update.return_value = 62
        self.db.already_inserted_membership.return_value = False
        self.db.add_membership.return_value = (62, one_year_later())
        return 62

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()


class TestSignaturesInMembershipView(MembershipViewTests):
    """ Test the signature-handling aspects of the membership view. """
    def setUp(self):
        super().setUp()

        # A completely valid payload, with appropriate signature
        self.valid_payload = {
            'decision': 'ACCEPT',
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'signed_date_time': '2018-05-17T19:20:30Z',
            'auth_amount': '15.00',
            'req_amount': '15.00',
            'signed_field_names': (
                'decision,'
                'req_merchant_defined_data1,'
                'req_merchant_defined_data3,'
                'signed_date_time,'
                'auth_amount,'
                'req_amount'
            ),
            'signature': 'q+UdR3vWZcLyjoxozKh5O+NRkSMbFomsxGkz+RpsYAE='
        }

    def test_no_signed_field_names(self):
        """ When 'signed_field_names' is absent, a 401 is returned. """
        payload = self.valid_payload
        payload.pop('signed_field_names')

        response = self.client.post('/members/membership', data=payload)
        self.assertEqual(response.status_code, 401)

    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_valid_signature(self, verified_emails):
        """ When a valid signature is included, the route succeeds. """
        all_emails = ['mitoc-member@example.com']
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        self.configure_normal_update()

        response = self.client.post('/members/membership', data=self.valid_payload)
        self.assertEqual(response.status_code, 201)

    def test_invalid_signature(self):
        """ We 401 when signed names are present, but signature is invalid. """
        payload = self.valid_payload
        payload['signature'] = 'this-signature-is-invalid'
        response = self.client.post('/members/membership', data=payload)
        self.assertEqual(response.status_code, 401)

    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_mitoc_trips_api_down(self, verified_emails):
        """ If the MITOC Trips API is down, the route still succeeds. """
        email = ['mitoc-member@example.com']
        verified_emails.return_value = (email, [email])

        self.configure_normal_update()

        self.update_membership.side_effect = URLError("API is down!")

        response = self.client.post('/members/membership', data=self.valid_payload)
        self.assertEqual(response.status_code, 201)


class TestMembershipView(MembershipViewTests):
    """ Test behavior of membership view _not_ relating to signatures. """
    def post_signed_data(self, data):
        """ Generate a signature in the payload before posting.

        This utility method allows us to test logic without manually having
        to generate a valid signature.

        Additionally, if any important fields were omitted, use some sensible
        defaults.
        """
        payload = data.copy()

        # Everything that's not accepting a membership is ignored
        if 'decision' not in payload:
            payload['decision'] = 'ACCEPT'
        if 'req_merchant_defined_data1' not in payload:
            data['req_merchant_defined_data1'] = 'membership'

        # Timestamps must be present in order to not get a 400
        if 'signed_date_time' not in payload:
            payload['signed_date_time'] = cybersource_now()

        # Sign the form
        signed_field_names = [key for key in payload]
        payload['signed_field_names'] = ','.join(signed_field_names)
        payload['signature'] = self.signer.sign(payload, signed_field_names)

        return self.client.post('/members/membership', data=payload)

    def expect_no_processing(self):
        """ No attempts are made to modify the database. """
        # No further action is taken
        self.db.add_person.assert_not_called()
        self.db.add_membership.assert_not_called()
        self.update_membership.assert_not_called()

    def test_non_membership_transactions_ignored(self):
        """ Any CyberSource transaction not for membership is ignored. """
        response = self.post_signed_data({
            'req_merchant_defined_data1': 'rental',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00'
        })
        self.assertEqual(response.status_code, 204)

    def test_non_acceptance_ignored(self):
        """ If a transaction is anything but 'ACCEPT' it's ignored.

        (This corresponds to payments that were rejected, are in review, etc.)
        """
        response = self.post_signed_data({
            'decision': 'REVIEW',
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
        })
        self.assertEqual(response.status_code, 204)

        self.expect_no_processing()

    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_duplicate_requests_handled(self, verified_emails):
        """ Test idempotency of the membership route.

        When the same membership transaction is POSTed to the API, we don't
        create or update anything.
        """
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        # There's already a person_id in the database for this person,
        # and this particular membership record was already inserted
        self.db.person_to_update.return_value = 128
        self.db.already_inserted_membership.return_value = True

        # We submit a valid signature for a membership, but get a 202:
        # the membership has already been processed
        response = self.post_signed_data({
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'auth_amount': '15.00',
        })
        self.assertEqual(response.status_code, 202)

        self.expect_no_processing()

    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_update_membership(self, verified_emails):
        """ Updating an existing membership works. """
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        person_id = self.configure_normal_update()

        payload = {
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'signed_date_time': '2018-01-24T21:48:32Z',
            'auth_amount': '15.00',
            'req_amount': '15.00'
        }

        response = self.post_signed_data(payload)
        self.assertEqual(response.status_code, 201)

        # The person exists - so they should not be created
        self.db.add_person.assert_not_called()

        # Instead, they were updated
        datetime_paid = datetime.strptime(payload['signed_date_time'],
                                          CYBERSOURCE_DT_FORMAT)
        self.db.add_membership.assert_called_with(person_id, '15.00', datetime_paid)

        # MITOC Trips is notified of the updated membership
        self.update_membership.assert_called_with(
            'mitoc-member@example.com', membership_expires=one_year_later()
        )

    @unittest.mock.patch('member.public.views.other_verified_emails')
    def test_new_membership(self, verified_emails):
        """ We create a new person record when somebody is new to MITOC. """
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        self.db.person_to_update.return_value = None  # New to MITOC
        self.db.add_person.return_value = 128  # After creating, person_id returned
        self.db.add_membership.return_value = (128, one_year_later())

        payload = {
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'req_bill_to_forename': 'Tim',
            'req_bill_to_surname': 'Beaver',
            'auth_amount': '15.00',
            'req_amount': '15.00',
            'signed_date_time': '2018-01-24T21:48:32Z'
        }
        response = self.post_signed_data(data=payload)
        self.assertEqual(response.status_code, 201)

        # A new person record needs to be created
        self.db.add_person.assert_called_with(payload['req_bill_to_forename'],
                                              payload['req_bill_to_surname'],
                                              'mitoc-member@example.com')

        # The membership is then inserted for the new person
        datetime_paid = datetime.strptime(payload['signed_date_time'],
                                          CYBERSOURCE_DT_FORMAT)
        self.db.add_membership.assert_called_with(128, '15.00', datetime_paid)

        # MITOC Trips is notified of the new member
        self.update_membership.assert_called_with(
            'mitoc-member@example.com', membership_expires=one_year_later()
        )

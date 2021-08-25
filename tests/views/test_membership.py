import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from member import extensions
from member.app import create_app
from member.cybersource import CYBERSOURCE_DT_FORMAT
from member.public import views
from member.signature import SecureAcceptanceSigner

from ..utils import create_app_with_env_vars

DIR_PATH = Path(__file__).resolve().parent
DUMMY_RAVEN_DSN = 'https://aa11bb22cc33dd44ee55ff6601234560@sentry.io/104648'


def one_year_later():
    return datetime.now().date() + timedelta(days=365)


def cybersource_now():
    """Return the current datetime formatted as CyberSource does."""
    return datetime.strftime(datetime.now(), CYBERSOURCE_DT_FORMAT)


class MembershipViewTests(unittest.TestCase):
    # A completely valid payload, with appropriate signature, produced like so:
    # valid_payload['signature'] = self.signer.sign(
    #    valid_payload,
    #    valid_payload['signed_field_names'].split(',')
    # )
    valid_payload = {
        'decision': 'ACCEPT',
        'req_merchant_defined_data1': 'membership',
        'req_merchant_defined_data2': 'MU',
        'req_merchant_defined_data3': 'mitoc-member@example.com',
        'signed_date_time': '2018-05-17T19:20:30Z',
        'auth_amount': '15.00',
        'req_amount': '15.00',
        'signed_field_names': (
            'decision,'
            'req_merchant_defined_data1,'
            'req_merchant_defined_data2,'
            'req_merchant_defined_data3,'
            'signed_date_time,'
            'auth_amount,'
            'req_amount'
        ),
        'signature': '/PtadMBZdyJYtnnZbPa9udh/iIuTTAQoELEkUljpEnk=',
    }

    def setUp(self):
        self.patchers = [
            mock.patch.object(views, 'db'),
            mock.patch.object(views, 'update_membership'),
        ]
        self.db, self.update_membership = [p.start() for p in self.patchers]

        self.app = create_app()
        self.client = self.app.test_client()
        self.app.config['CYBERSOURCE_SECRET_KEY'] = 'secret-key'
        self.signer = SecureAcceptanceSigner('secret-key')

    def configure_normal_update(self):
        """Configure mocks to indicate a person already in the db.

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
    """Test the signature-handling aspects of the membership view."""

    def test_no_signed_field_names(self):
        """When 'signed_field_names' is absent, a 401 is returned."""
        payload = self.valid_payload.copy()
        payload.pop('signed_field_names')

        response = self.client.post('/members/membership', data=payload)
        self.assertEqual(response.status_code, 401)

    @mock.patch.object(views, 'other_verified_emails')
    def test_valid_signature(self, verified_emails):
        """When a valid signature is included, the route succeeds."""
        all_emails = ['mitoc-member@example.com']
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        self.configure_normal_update()

        response = self.client.post('/members/membership', data=self.valid_payload)
        self.assertEqual(response.status_code, 201)

    def test_invalid_signature(self):
        """We 401 when signed names are present, but signature is invalid."""
        payload = self.valid_payload.copy()
        payload['signature'] = 'this-signature-is-invalid'
        response = self.client.post('/members/membership', data=payload)
        self.assertEqual(response.status_code, 401)


class ApiDownTests(MembershipViewTests):
    def setUp(self):
        super().setUp()

        # Create a new app where Sentry is activated!
        # (We'll mock the object so that real API calls aren't attepmted)
        self.app = create_app_with_env_vars(
            {'RAVEN_DSN': DUMMY_RAVEN_DSN, 'CYBERSOURCE_SECRET_KEY': 'secret-key'}
        )
        # Ensure that our app's configuration came straight from the env var
        self.assertEqual(self.app.config['CYBERSOURCE_SECRET_KEY'], 'secret-key')
        self.client = self.app.test_client()

    @mock.patch.object(views, 'other_verified_emails')
    def test_mitoc_trips_api_down(self, verified_emails):
        """If the MITOC Trips API is down, the route still succeeds."""
        email = ['mitoc-member@example.com']
        verified_emails.return_value = (email, [email])

        self.configure_normal_update()

        self.update_membership.side_effect = URLError("API is down!")

        with mock.patch.object(extensions, 'sentry') as sentry:
            response = self.client.post('/members/membership', data=self.valid_payload)
            sentry.captureException.assert_called_once()

        self.assertTrue(response.is_json)
        self.assertEqual(response.status_code, 201)

    @mock.patch.object(views, 'other_verified_emails')
    def test_mitoc_trips_api_down_but_no_sentry(self, verified_emails):
        """If Sentry is not configured, the route still succeeds."""
        email = ['mitoc-member@example.com']
        verified_emails.return_value = (email, [email])

        self.configure_normal_update()

        self.update_membership.side_effect = URLError("API is down!")

        with mock.patch.object(views, 'extensions') as view_extensions:
            view_extensions.sentry = None
            response = self.client.post('/members/membership', data=self.valid_payload)

        self.assertTrue(response.is_json)
        self.assertEqual(response.status_code, 201)


class TestMembershipView(MembershipViewTests):
    """Test behavior of membership view _not_ relating to signatures."""

    def post_signed_data(self, data):
        """Generate a signature in the payload before posting.

        This utility method allows us to test logic without manually having
        to generate a valid signature.

        Additionally, if any important fields were omitted, use some sensible
        defaults.
        """
        payload = data.copy()

        # Sign the form
        signed_field_names = list(payload)
        payload['signed_field_names'] = ','.join(signed_field_names)
        payload['signature'] = self.signer.sign(payload, signed_field_names)

        return self.client.post('/members/membership', data=payload)

    def expect_no_processing(self):
        """No attempts are made to modify the database."""
        # No further action is taken
        self.db.add_person.assert_not_called()
        self.db.add_membership.assert_not_called()
        self.update_membership.assert_not_called()

    def test_non_membership_transactions_ignored(self):
        """Any CyberSource transaction not for membership is ignored."""
        response = self.post_signed_data(
            {
                'decision': 'ACCEPT',
                'req_merchant_defined_data1': 'rental',
                'req_merchant_defined_data3': 'mitoc-member@example.com',
                'auth_amount': '15.00',
                'signed_date_time': cybersource_now(),
            }
        )
        self.assertEqual(response.status_code, 204)

    def test_non_acceptance_ignored(self):
        """If a transaction is anything but 'ACCEPT' it's ignored.

        (This corresponds to payments that were rejected, are in review, etc.)
        """
        response = self.post_signed_data(
            {
                'decision': 'REVIEW',
                'req_merchant_defined_data1': 'membership',
                'req_merchant_defined_data2': 'MU',
                'req_merchant_defined_data3': 'mitoc-member@example.com',
                'auth_amount': '15.00',
                'signed_date_time': cybersource_now(),
            }
        )
        self.assertEqual(response.status_code, 204)

        self.expect_no_processing()

    @mock.patch.object(views, 'other_verified_emails')
    def test_duplicate_requests_handled(self, verified_emails):
        """Test idempotency of the membership route.

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
        response = self.post_signed_data(
            {
                'decision': 'ACCEPT',
                'req_merchant_defined_data1': 'membership',
                'req_merchant_defined_data2': 'MU',
                'req_merchant_defined_data3': 'mitoc-member@example.com',
                'auth_amount': '15.00',
                'signed_date_time': cybersource_now(),
            }
        )
        self.assertEqual(response.status_code, 202)

        self.expect_no_processing()

    @mock.patch.object(views, 'other_verified_emails')
    def test_update_membership(self, verified_emails):
        """Updating an existing membership works."""
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        person_id = self.configure_normal_update()

        payload = {
            'decision': 'ACCEPT',
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data2': 'MU',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'signed_date_time': '2018-01-24T21:48:32Z',
            'auth_amount': '15.00',
            'req_amount': '15.00',
        }

        response = self.post_signed_data(payload)
        self.assertEqual(response.status_code, 201)

        # The person exists - so they should not be created
        self.db.add_person.assert_not_called()

        # Instead, they were updated
        datetime_paid = datetime.strptime(
            payload['signed_date_time'], CYBERSOURCE_DT_FORMAT
        )
        self.db.add_membership.assert_called_with(
            person_id, '15.00', datetime_paid, 'MU'
        )

        # MITOC Trips is notified of the updated membership
        self.update_membership.assert_called_with(
            'mitoc-member@example.com', membership_expires=one_year_later()
        )

    @mock.patch.object(views, 'other_verified_emails')
    def test_new_membership(self, verified_emails):
        """We create a new person record when somebody is new to MITOC."""
        # The Trips web site gives all emails that we use to look up the user
        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        verified_emails.return_value = ('mitoc-member@example.com', all_emails)

        self.db.person_to_update.return_value = None  # New to MITOC
        self.db.add_person.return_value = 128  # After creating, person_id returned
        self.db.add_membership.return_value = (128, one_year_later())

        payload = {
            'decision': 'ACCEPT',
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data2': 'MU',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'req_bill_to_forename': 'Tim',
            'req_bill_to_surname': 'Beaver',
            'auth_amount': '15.00',
            'req_amount': '15.00',
            'signed_date_time': '2018-01-24T21:48:32Z',
        }
        response = self.post_signed_data(data=payload)
        self.assertEqual(response.status_code, 201)

        # A new person record needs to be created
        self.db.add_person.assert_called_with(
            payload['req_bill_to_forename'],
            payload['req_bill_to_surname'],
            'mitoc-member@example.com',
        )

        # The membership is then inserted for the new person
        datetime_paid = datetime.strptime(
            payload['signed_date_time'], CYBERSOURCE_DT_FORMAT
        )
        self.db.add_membership.assert_called_with(128, '15.00', datetime_paid, 'MU')

        # MITOC Trips is notified of the new member
        self.update_membership.assert_called_with(
            'mitoc-member@example.com', membership_expires=one_year_later()
        )


class TestMembershipWithoutSignatureVerificationView(MembershipViewTests):
    """Test processing a membership _without_ verifying the signature.

    We support this behavior in the first place since MITOC does not actually
    have access to the secret key that could be used to verify signatures (with
    this key, we could do some other things that MIT does not want us to be
    able to do -- and they own the account).

    Thankfully, we're able to employ other security measures to validate the
    source of the data, even if we can't validate contents' signature.
    """

    def setUp(self):
        super().setUp()
        self.app.config['VERIFY_CYBERSOURCE_SIGNATURE'] = False

    def test_bad_signature_still_works(self):
        """A valid payload with a bad signature still works."""
        payload = {
            'decision': 'ACCEPT',
            'req_merchant_defined_data1': 'membership',
            'req_merchant_defined_data2': 'MU',
            'req_merchant_defined_data3': 'mitoc-member@example.com',
            'signed_date_time': '2018-01-24T21:48:32Z',
            'auth_amount': '15.00',
            'req_amount': '15.00',
            # The signed fields name are correctly referenced, but we have a bad signature!
            'signed_field_names': ','.join(
                [
                    'decision'
                    'req_merchant_defined_data1'
                    'req_merchant_defined_data2'
                    'req_merchant_defined_data3'
                    'signed_date_time'
                    'auth_amount'
                    'req_amount'
                ]
            ),
            'signature': 'this-is-not-actually-valid!',
        }

        person_id = self.configure_normal_update()  # Make it as if this person exists

        all_emails = ('mitoc-member@example.com', 'same-person@example.com')
        with mock.patch.object(views, 'other_verified_emails') as verified_emails:
            verified_emails.return_value = ('mitoc-member@example.com', all_emails)
            response = self.client.post('/members/membership', data=payload)

        # We successfully processed the membership update!
        self.assertEqual(response.status_code, 201)
        datetime_paid = datetime.strptime(
            payload['signed_date_time'], CYBERSOURCE_DT_FORMAT
        )
        self.db.add_membership.assert_called_with(
            person_id, '15.00', datetime_paid, 'MU'
        )

        # MITOC Trips is notified of the updated membership
        self.update_membership.assert_called_with(
            'mitoc-member@example.com', membership_expires=one_year_later()
        )

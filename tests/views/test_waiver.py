import unittest
from contextlib import contextmanager
from datetime import date, datetime, timezone
from importlib import reload
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from member import extensions
from member.app import create_app
from member.envelopes import CompletedEnvelope
from member.public import views

from ..utils import create_app_with_env_vars

DIR_PATH = Path(__file__).resolve().parent.parent
DUMMY_RAVEN_DSN = 'https://aa11bb22cc33dd44ee55ff6601234560@sentry.io/104648'


class WaiverTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

        self.client = self.app.test_client()

        # Read in a completed waiver to use as test data.
        waiver_path = DIR_PATH / 'completed_waiver.xml'
        with waiver_path.open() as waiver:
            self._waiver_data = waiver.read()
        # Value from the XML!
        self.TIME_SIGNED = datetime(
            2018, 11, 10, 23, 41, 6, 937000, tzinfo=timezone.utc
        )

        # Fixture-like data we'll use across methods
        self.VALID_UNTIL = date(2019, 11, 20)
        self.person_id = 37
        self.waiver_id = 42

    @contextmanager
    def _first_waiver(self, primary_email, all_emails):
        """Mock all the database calls to simulate a first-time waiver signing."""
        # No need to mock an envelope, since we submit valid envelopes!
        with mock.patch.object(views, 'other_verified_emails') as verified_emails:
            verified_emails.return_value = (primary_email, all_emails)
            with mock.patch.object(views, 'db') as db:
                db.person_to_update.return_value = None  # Not in db!
                db.already_added_waiver.return_value = False
                db.add_person.return_value = self.person_id
                db.add_waiver.return_value = (self.waiver_id, self.VALID_UNTIL)
                yield db, verified_emails

    @staticmethod
    @contextmanager
    def _mocked_env():
        """Mock an envelope, so we might simulate its various public methods."""
        mocked_envelope = mock.Mock(spec=CompletedEnvelope)

        def verify_but_return_mock(data):
            """Ensure that the data is a valid envelope, but ignore it & return a mock."""
            # This will raise an exception if the data is not a valid envelope!
            CompletedEnvelope(data)  # Will r
            return mocked_envelope

        with mock.patch.object(views, 'CompletedEnvelope', autospec=True) as env:
            env.side_effect = verify_but_return_mock
            yield mocked_envelope


# TODO: Rather than mocking out `CompletedEnvelope`, do two things:
# 1. Build a small collection of valid XML waivers in different states
# 2. Expand coverage in `test_envelope` to handle these various envelopes
# 3. Support full end-to-end testing here
class TestWaiverView(WaiverTests):
    """Test behavior of the waiver-processing view.

    NOTE: Currently, this route directly hits database methods.
    In a future world, it will instead hit the geardb API.
    """

    def test_post_not_yet_completed(self):
        """Waivers awaiting a guardian's signature should not be processed."""
        # Disable Sentry initialization to get around a frustrating deprecation warning
        # that is raised when using Raven with `contextmanager`
        # See: issue 1296 on raven-python
        with mock.patch.dict('os.environ', clear=True):
            reload(extensions)  # Sentry is configured on import!
            app = create_app()
        client = app.test_client()

        with self._mocked_env() as env:
            env.completed = False
            resp = client.post('/members/waiver', data=self._waiver_data)
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(resp.is_json)

    @mock.patch.object(views, 'update_membership')
    def test_completed_waiver_not_in_db(self, update_membership):
        """Test behavior on a completed waiver for somebody not in our db!"""

        all_emails = ['tim@mit.edu', 'tim@csail.mit.edu']
        with self._first_waiver('tim@mit.edu', all_emails) as (db, verified_emails):
            resp = self.client.post('/members/waiver', data=self._waiver_data)

        verified_emails.assert_called_once_with('tim@mit.edu')  # (from the XML)

        # Because Tim was not in the database, we added him!
        db.person_to_update.assert_called_once_with('tim@mit.edu', all_emails)
        db.add_person.assert_called_once_with('Tim', 'Beaver', 'tim@mit.edu')

        # We checked if we'd already inserted Tim, then we add his waiver!
        db.already_added_waiver.assert_called_once_with(
            self.person_id, self.TIME_SIGNED
        )
        db.add_waiver.assert_called_once_with(self.person_id, self.TIME_SIGNED)

        db.update_affiliation.assert_called_once_with(self.person_id, 'Non-affiliate')

        # Finally, we let MITOC Trips know that Tim's account was updated
        update_membership.assert_called_once_with(
            'tim@mit.edu', waiver_expires=self.VALID_UNTIL
        )

        self.assertTrue(resp.is_json)
        self.assertEqual(resp.status_code, 201)

    def test_already_added_waiver(self):
        """If the waiver is already present in the database, we don't re-submit."""
        # No need to mock an envelope, since we submit valid envelopes!
        with mock.patch.object(views, 'other_verified_emails') as verified_emails:
            verified_emails.return_value = ('tim@mit.edu', ['tim@mit.edu'])
            with mock.patch.object(views, 'db') as db:
                db.person_to_update.return_value = 37
                db.already_added_waiver.return_value = True
                resp = self.client.post('/members/waiver', data=self._waiver_data)

        self.assertTrue(resp.is_json)
        self.assertEqual(resp.status_code, 204)

        db.add_person.assert_not_called()
        db.add_waiver.assert_not_called()


class ApiDownTests(WaiverTests):
    def setUp(self):
        super().setUp()
        self.app = create_app_with_env_vars({'RAVEN_DSN': DUMMY_RAVEN_DSN})
        self.client = self.app.test_client()

    @mock.patch.object(views, 'update_membership')
    def test_mitoc_trips_api_down(self, update_membership):
        """If the MITOC Trips API is down, the route still succeeds."""
        update_membership.side_effect = URLError("API is down!")

        all_emails = ['tim@mit.edu']
        with self._first_waiver('tim@mit.edu', all_emails) as (db, verified_emails):
            with mock.patch.object(extensions, 'sentry') as sentry:
                resp = self.client.post('/members/waiver', data=self._waiver_data)

        # This request goes through all the usual steps!
        verified_emails.assert_called_once_with('tim@mit.edu')  # (from the XML)
        db.add_person.assert_called_once_with('Tim', 'Beaver', 'tim@mit.edu')
        db.add_waiver.assert_called_once_with(self.person_id, self.TIME_SIGNED)
        db.update_affiliation.assert_called_once_with(self.person_id, 'Non-affiliate')

        # We still return a 201, even though informing MITOC Trips failed
        sentry.captureException.assert_called_once()
        self.assertTrue(resp.is_json)
        self.assertEqual(resp.status_code, 201)

    @mock.patch.object(views, 'update_membership')
    def test_mitoc_trips_api_down_but_no_sentry(self, update_membership):
        """If Sentry is not configured, the route still succeeds."""
        update_membership.side_effect = URLError("API is down!")

        all_emails = ['tim@mit.edu']
        with self._first_waiver('tim@mit.edu', all_emails) as (db, verified_emails):
            with mock.patch.object(views, 'extensions') as view_extensions:
                view_extensions.sentry = None
                resp = self.client.post('/members/waiver', data=self._waiver_data)

        # This request goes through all the usual steps!
        verified_emails.assert_called_once_with('tim@mit.edu')  # (from the XML)
        db.add_person.assert_called_once_with('Tim', 'Beaver', 'tim@mit.edu')
        db.add_waiver.assert_called_once_with(self.person_id, self.TIME_SIGNED)
        db.update_affiliation.assert_called_once_with(self.person_id, 'Non-affiliate')

        self.assertTrue(resp.is_json)
        self.assertEqual(resp.status_code, 201)

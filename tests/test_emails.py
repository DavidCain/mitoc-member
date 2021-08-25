import unittest
from contextlib import contextmanager
from datetime import datetime
from http.client import HTTPResponse
from unittest import mock

import jwt

from member.app import create_app
from member.emails import other_verified_emails, update_membership


class UrlopenHelpers(unittest.TestCase):
    """Provide some helpers to mocking `urlopen`.

    This service aims to be as small as possible, so we don't have `requests`.
    We just instead use the standard library!
    """

    def setUp(self):
        self.urlopen_patcher = unittest.mock.patch('member.emails.urlopen')
        self.urlopen = self.urlopen_patcher.start()

        self.app = create_app()
        self.app.config['MEMBERSHIP_SECRET_KEY'] = 'secret-key'

    def tearDown(self):
        self.urlopen_patcher.stop()

    @contextmanager
    def expect_request(self, expected_url, expected_payload, method='POST'):
        """Expect a single request to the URL, with payload & signed JWT.

        Yields a mocked response that the caller can use to tweak as they see fit.
        """
        response = mock.MagicMock(spec=HTTPResponse)

        with self.app.app_context():
            self.urlopen.side_effect = self._inspect(
                expected_url, expected_payload, method, response
            )
            yield response

        # `_inspect()` will make sure called args were correct.
        # However, we need to make sure it was called at least once!
        self.urlopen.assert_called_once()

    def _inspect(self, expected_url, expected_payload, method, response=None):
        """Ensure that the request to `mitoc-trips` is properly formed."""

        @contextmanager
        def inspect(request):
            self.assertEqual(request.method, method)
            self.assertEqual(request.full_url, expected_url)

            authorization = request.get_header('Authorization')
            self.assertTrue(authorization.startswith('Bearer: '))
            _, token = authorization.split()
            payload = jwt.decode(
                token,
                self.app.config['MEMBERSHIP_SECRET_KEY'],
                algorithms=['HS512', 'HS256'],
            )
            payload.pop('exp')  # This claim changes dynamically, we needn't test here
            self.assertEqual(payload, expected_payload)

            yield response or mock.MagicMock(spec=HTTPResponse)

        return inspect


class UpdateMembershipTests(UrlopenHelpers, unittest.TestCase):
    def test_update_membership(self):
        """When updating just a membership, we send that via JWT."""
        expires = datetime(2018, 9, 24).date()
        with self.expect_request(
            'https://mitoc-trips.mit.edu/data/membership/',
            {'email': 'tim@mit.edu', 'membership_expires': '2018-09-24'},
        ) as response:
            response.read.return_value = '{}'
            ret = update_membership('tim@mit.edu', membership_expires=expires)
        self.assertEqual(ret, {})

    def test_update_waiver(self):
        """When updating just a waiver, we send that via JWT."""
        expires = datetime(2017, 2, 28).date()
        with self.expect_request(
            'https://mitoc-trips.mit.edu/data/membership/',
            {'email': 'tim@mit.edu', 'waiver_expires': '2017-02-28'},
        ) as response:
            response.read.return_value = '{}'
            ret = update_membership('tim@mit.edu', waiver_expires=expires)
        self.assertEqual(ret, {})


class OtherVerifiedEmailsTests(UrlopenHelpers, unittest.TestCase):
    def test_fetch_verified_emails(self):
        with self.expect_request(
            'https://mitoc-trips.mit.edu/data/verified_emails/',
            {'email': 'tim@mit.edu'},
            method='GET',
        ) as response:
            response.read.return_value = '{"primary": "tim@mit.edu", "emails": ["tim@mit.edu", "tim@csail.mit.edu"]}'
            primary, all_emails = other_verified_emails('tim@mit.edu')

        self.assertEqual(primary, 'tim@mit.edu')
        self.assertEqual(all_emails, ['tim@mit.edu', 'tim@csail.mit.edu'])

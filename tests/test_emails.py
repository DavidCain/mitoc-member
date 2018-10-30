from contextlib import contextmanager
from datetime import datetime
import unittest

import jwt

from member.app import create_app
from member.emails import update_membership


class UpdateMembershipTests(unittest.TestCase):
    def setUp(self):
        self.urlopen_patcher = unittest.mock.patch('member.emails.urlopen')
        self.urlopen = self.urlopen_patcher.start()

        self.app = create_app()
        self.app.config['MEMBERSHIP_SECRET_KEY'] = 'secret-key'

    def tearDown(self):
        self.urlopen_patcher.stop()

    def inspect_request(self, expected_payload):
        """ Ensure that the request to `mitoc-trips` is properly formed. """
        @contextmanager
        def inspect(request):
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.full_url,
                             'https://mitoc-trips.mit.edu/data/membership/')

            authorization = request.get_header('Authorization')
            self.assertTrue(authorization.startswith('Bearer: '))
            _, token = authorization.split()
            payload = jwt.decode(token, self.app.config['MEMBERSHIP_SECRET_KEY'],
                                 algorithms=['HS512', 'HS256'])
            payload.pop('exp')  # This claim changes dynamically, we needn't test here
            self.assertEqual(payload, expected_payload)

            # The response object returns an empty JSON object
            response = unittest.mock.MagicMock()
            response.read.return_value = '{}'
            yield response
        return inspect

    def test_update_membership(self):
        """ When updating just a membership, we send that via JWT. """
        expires = datetime(2018, 9, 24).date()
        self.urlopen.side_effect = self.inspect_request({
            'email': 'tim@mit.edu',
            'membership_expires': '2018-09-24'
        })
        with self.app.app_context():
            update_membership('tim@mit.edu', membership_expires=expires)

    def test_update_waiver(self):
        """ When updating just a waiver, we send that via JWT. """
        expires = datetime(2017, 2, 28).date()
        self.urlopen.side_effect = self.inspect_request({
            'email': 'tim@mit.edu',
            'waiver_expires': '2017-02-28'
        })
        with self.app.app_context():
            update_membership('tim@mit.edu', waiver_expires=expires)

from datetime import datetime, timedelta

import unittest
import unittest.mock

from member import db


class TestDbMethods(unittest.TestCase):
    def test_affiliation(self):
        """ Test mapping of amounts paid to membership values. """
        self.assertEqual(db.get_affiliation(15.0), 'student')
        self.assertEqual(db.get_affiliation(20.0), 'affiliate')
        self.assertEqual(db.get_affiliation(25.0), 'general')

    @unittest.mock.patch('member.db.current_membership_expires')
    def test_new_member_expiration(self, current_membership_expires):
        """ New memberships start exactly when they were paid. """
        current_membership_expires.return_value = None
        datetime_paid = datetime(2018, 6, 6, 12, 47)
        self.assertEqual(datetime_paid, db.membership_start(37, datetime_paid))

    @unittest.mock.patch('member.db.datetime')
    @unittest.mock.patch('member.db.current_membership_expires')
    def test_renewed_near_end(self, current_membership_expires, mock_dt):
        """ Renewing at the end of a membership adds 12 full months. """
        # It's early January, and our membership expires in two weeks
        datetime_paid = datetime(2018, 1, 1, 12, 47)
        mock_dt.utcnow = unittest.mock.Mock(return_value=datetime(2018, 1, 1))
        membership_expires_on = datetime(2018, 1, 15, 3, 52)
        current_membership_expires.return_value = membership_expires_on

        # The resulting membership lasts one year, starting after the last one
        self.assertEqual(membership_expires_on,
                         db.membership_start(37, datetime_paid))

    @unittest.mock.patch('member.db.datetime')
    @unittest.mock.patch('member.db.current_membership_expires')
    def test_renewed_very_early(self, current_membership_expires, mock_dt):
        """ Renewing too early adds 12 months from the date renewed. """
        # In January, we're renewing a membership that expires in June
        datetime_paid = datetime(2018, 1, 1, 12, 47)
        mock_dt.utcnow = unittest.mock.Mock(return_value=datetime(2018, 1, 1))
        current_membership_expires.return_value = datetime(2018, 6, 6, 12, 14)

        # Our resulting membership will only be valid until next January
        self.assertEqual(datetime_paid, db.membership_start(37, datetime_paid))

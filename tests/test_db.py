from datetime import date, datetime

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
        """ New memberships start on the date of payment in Boston. """
        current_membership_expires.return_value = None
        test_cases = [
            # Normal case: It's the same day in both EST and UTC
            (datetime(2018, 5, 2, 6, 13), date(2018, 5, 2)),

            # UTC -5 in February
            (datetime(2018, 2, 2, 5, 57), date(2018, 2, 2)),
            (datetime(2018, 2, 2, 4, 57), date(2018, 2, 1)),

            # UTC -4 when DST is observed in the summer
            (datetime(2018, 6, 2, 4, 57), date(2018, 6, 2)),
            (datetime(2018, 6, 2, 3, 57), date(2018, 6, 1)),
        ]

        for datetime_paid, expected in test_cases:
            self.assertEqual(expected, db.membership_start(37, datetime_paid))

    @unittest.mock.patch('member.db.current_membership_expires')
    def test_renewed_near_end(self, current_membership_expires):
        """ Renewing at the end of a membership adds 12 full months. """
        # It's early January, and our membership expires in two weeks
        datetime_paid = datetime(2018, 1, 1, 12, 47)
        membership_expires_on = date(2018, 1, 15)
        current_membership_expires.return_value = membership_expires_on

        # The resulting membership lasts one year, starting after the last one
        self.assertEqual(membership_expires_on,
                         db.membership_start(37, datetime_paid))

    @unittest.mock.patch('member.db.current_membership_expires')
    def test_renewed_very_early(self, current_membership_expires):
        """ Renewing too early adds 12 months from the date renewed. """
        # In January, we're renewing a membership that expires in June
        datetime_paid = datetime(2018, 1, 1, 12, 47)
        date_paid_EST = date(2018, 1, 1)

        current_membership_expires.return_value = date(2018, 6, 6)

        # Our resulting membership will only be valid until next January
        self.assertEqual(date_paid_EST, db.membership_start(37, datetime_paid))

import unittest

from member import db


class TestDbMethods(unittest.TestCase):
    def test_affiliation(self):
        """ Test mapping of amounts paid to membership values. """
        self.assertEqual(db.get_affiliation(15.0), 'student')
        self.assertEqual(db.get_affiliation(20.0), 'affiliate')
        self.assertEqual(db.get_affiliation(25.0), 'general')

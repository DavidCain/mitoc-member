import unittest

from member import signature


class TestSecureAcceptanceSigner(unittest.TestCase):
    def setUp(self):
        self.signer = signature.SecureAcceptanceSigner('secret-key')

    def test_signing_order(self):
        """ The order of signed fields changes the result. """
        name_first = self.signer.sign({'name': 'Dennis', 'age': 37}, ['name', 'age'])
        self.assertEqual(name_first, b'PAXsnH+BAC5pqZRq+0sDHsqQq5UJ/E1quZgIn5Xv2gA=')
        age_first = self.signer.sign({'name': 'Dennis', 'age': 37}, ['age', 'name'])
        self.assertEqual(age_first, b'gey89FkFpKWsyqwicl2ffjyXDzroaoEvLqluIKO6qls=')

    def test_verify(self):
        """ Ensure that verification of a standard CyberSource POST works. """
        post_data = {
            'signature': '6wI69NZPgm2GtiAEFbnKHnBnsYhqybRaQ8hyXCTKcxM=',
            'signed_field_names': 'name,email',
            'name': 'Dennis',
            'email': 'dennis@example.com',
        }
        self.assertTrue(self.signer.verify_request(post_data))

    def test_verify_but_no_field_names(self):
        """ Any POST without the signed field names cannot be verified. """
        post_data = {'signature': b'gey89FkFpKWsyqwicl2ffjyXDzroaoEvLqluIKO6qls='}
        with self.assertRaises(ValueError):
            self.signer.verify_request(post_data)

import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from member import envelopes

dir_path = Path(__file__).resolve().parent


def load_envelope(filename='completed_waiver.xml'):
    example_xml = dir_path / filename
    return envelopes.CompletedEnvelope(example_xml.open().read())


class TestNameSplitting(unittest.TestCase):
    @staticmethod
    @contextmanager
    def username(value):
        releasor_name = 'member.envelopes.CompletedEnvelope.releasor_name'
        with mock.patch(releasor_name, new_callable=mock.PropertyMock) as releasor:
            releasor.return_value = value
            yield load_envelope()

    def test_mononyms(self):
        """ If a user omits a last name, assume it's just a first name. """
        with self.username('Cher') as env:
            self.assertEqual(env.first_name, 'Cher')
            self.assertEqual(env.last_name, '')

    def test_multiple_last_names(self):
        """ Multiple names after initial space are treated as last name. """
        with self.username('Gabriel José de la Concordia García Márquez') as env:
            long_surname = 'José de la Concordia García Márquez'
            self.assertEqual(env.first_name, 'Gabriel')
            self.assertEqual(env.last_name, long_surname)

    def test_firstname_lastname(self):
        """ Simplest case: first & last name, separated by a space. """
        with self.username('John Smith') as env:
            self.assertEqual(env.first_name, 'John')
            self.assertEqual(env.last_name, 'Smith')

    def test_extra_spaces(self):
        """ Superfluous spacing between names doesn't matter. """
        with self.username('Timothy   Toomanyspaces') as env:
            self.assertEqual(env.first_name, 'Timothy')
            self.assertEqual(env.last_name, 'Toomanyspaces')


class TestExpectedDocumentType(unittest.TestCase):
    def test_root_element_okay(self):  # pylint: disable=no-self-use
        """ No errors occur when initializing the right root element type. """
        valid_xml = '''<?xml version="1.0" encoding="utf-8" ?>
            <DocuSignEnvelopeInformation xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                                         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                                         xmlns="http://www.docusign.net/API/3.0">
              <EnvelopeStatus></EnvelopeStatus>
            </DocuSignEnvelopeInformation>
        '''
        envelopes.CompletedEnvelope(valid_xml)

    def test_early_failure(self):
        """ Fail early when passed the wrong XML. """
        bad_xml = '''<?xml version="1.0" encoding="utf-8" ?>
            <WrongRootElement>
            <UserName>Bob</UserName>
            </WrongRootElement>
        '''
        with self.assertRaises(ValueError):
            envelopes.CompletedEnvelope(bad_xml)


class TestWaiverParser(unittest.TestCase):
    def setUp(self):
        self.env = load_envelope()
        self.assertTrue(self.env.completed)

    def test_tab_status(self):
        with self.assertRaises(ValueError):
            self.env.tab_status("This tab does not exist")

    def test_time_signed_incomplete_envelope(self):
        # TODO: Don't mock, actually load a (valid) incomplete envelope
        def mock_awaiting_guardian(hierarchy):
            assert hierarchy == ['EnvelopeStatus', 'Status']
            return 'Waiting for Others'

        incomplete_env = load_envelope()
        with mock.patch.object(incomplete_env, 'get_val') as get_val:
            get_val.side_effect = mock_awaiting_guardian

            with self.assertRaises(ValueError):
                incomplete_env.time_signed  # pylint:disable=pointless-statement

    def test_time_signed(self):
        """ The time signed is parsed & converted to UTC. """
        utc_time_signed = datetime(2018, 11, 10, 23, 41, 6, 937000, tzinfo=timezone.utc)

        self.assertEqual(self.env.time_signed, utc_time_signed)

    @mock.patch('member.envelopes.CompletedEnvelope._get_hours_offset')
    def test_offset(self, hours_offset):
        """ The offset is applied in hours from UTC. """
        time_signed = datetime(2018, 11, 10, 18, 41, 6, 937000)

        hours_offset.return_value = '0'
        self.assertEqual(time_signed, self.env.time_signed.replace(tzinfo=None))

        # Offsets work in both directions
        hours_offset.return_value = '+2'
        self.assertEqual(
            datetime(2018, 11, 10, 16, 41, 6, 937000),
            self.env.time_signed.replace(tzinfo=None),
        )
        hours_offset.return_value = '-5'
        self.assertEqual(
            datetime(2018, 11, 10, 23, 41, 6, 937000),
            self.env.time_signed.replace(tzinfo=None),
        )

    def test_releasor_email(self):
        """ The releasor's email is parsed out. """
        self.assertEqual(self.env.releasor_email, 'tim@mit.edu')

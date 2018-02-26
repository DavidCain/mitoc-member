from contextlib import contextmanager
from datetime import datetime, timezone
import unittest
from unittest.mock import patch, PropertyMock
from pathlib import Path

from member import envelopes

dir_path = Path(__file__).resolve().parent


class EnvelopeLoader:
    def load_envelope(self, filename='completed_waiver.xml'):
        example_xml = dir_path / filename
        self.env = envelopes.CompletedEnvelope(example_xml.open().read())


class TestNameSplitting(EnvelopeLoader, unittest.TestCase):
    @contextmanager
    def username(self, value):
        releasor_name = 'member.envelopes.CompletedEnvelope.releasor_name'
        with patch(releasor_name, new_callable=PropertyMock) as releasor:
            releasor.return_value = value
            self.load_envelope()
            yield releasor

    def test_mononyms(self):
        """ If a user omits a last name, assume it's just a first name. """
        with self.username('Cher'):
            self.assertEqual(self.env.first_name, 'Cher')
            self.assertEqual(self.env.last_name, '')

    def test_multiple_last_names(self):
        """ Multiple names after initial space are treated as last name. """
        with self.username('Gabriel José de la Concordia García Márquez'):
            long_surname = 'José de la Concordia García Márquez'
            self.assertEqual(self.env.first_name, 'Gabriel')
            self.assertEqual(self.env.last_name, long_surname)

    def test_firstname_lastname(self):
        """ Simplest case: first & last name, separated by a space. """
        with self.username('John Smith'):
            self.assertEqual(self.env.first_name, 'John')
            self.assertEqual(self.env.last_name, 'Smith')

    def test_extra_spaces(self):
        """ Superfluous spacing between names doesn't matter. """
        with self.username('Timothy   Toomanyspaces'):
            self.assertEqual(self.env.first_name, 'Timothy')
            self.assertEqual(self.env.last_name, 'Toomanyspaces')


class TestExpectedDocumentType(unittest.TestCase):
    def test_root_element_okay(self):
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


class TestWaiverParser(EnvelopeLoader, unittest.TestCase):
    def setUp(self):
        self.load_envelope()
        self.assertTrue(self.env.completed)

    def test_time_signed(self):
        """ The time signed is parsed & converted to UTC. """
        utc_time_signed = datetime(2018, 2, 22, 0, 29, 7, 147000, tzinfo=timezone.utc)
        self.assertEqual(self.env.time_signed, utc_time_signed)

    @patch('member.envelopes.CompletedEnvelope._get_hours_offset')
    def test_offset(self, hours_offset):
        """ The offset is applied in hours from UTC. """
        time_signed = datetime(2018, 2, 21, 16, 29, 7, 147000)

        hours_offset.return_value = '0'
        self.assertEqual(time_signed, self.env.time_signed.replace(tzinfo=None))

        # Offsets work in both directions
        hours_offset.return_value = '+2'
        self.assertEqual(datetime(2018, 2, 21, 14, 29, 7, 147000),
                         self.env.time_signed.replace(tzinfo=None))
        hours_offset.return_value = '-5'
        self.assertEqual(datetime(2018, 2, 21, 21, 29, 7, 147000),
                         self.env.time_signed.replace(tzinfo=None))

    def test_releasor_email(self):
        """ The releasor's email is parsed out. """
        self.assertEqual(self.env.releasor_email, 'tim@mit.edu')

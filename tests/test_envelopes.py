from datetime import datetime, timezone, timedelta
import unittest
import unittest.mock
from pathlib import Path

from member import envelopes

dir_path = Path(__file__).resolve().parent


class TestWaiverParser(unittest.TestCase):
    def setUp(self):
        example_xml = dir_path / 'completed_waiver.xml'
        self.env = envelopes.CompletedEnvelope(example_xml.open().read())

    def test_time_signed(self):
        """ The time signed is parsed & converted to UTC. """
        utc_time_signed = datetime(2018, 2, 22, 0, 29, 7, 147000, tzinfo=timezone.utc)
        self.assertEqual(self.env.time_signed, utc_time_signed)

    @unittest.mock.patch('member.envelopes.CompletedEnvelope._get_hours_offset')
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

    @unittest.mock.patch('member.envelopes.CompletedEnvelope.get_val')
    def test_fallback_on_utc_now(self, get_val):
        """ If we fail to parse the time signed, we fall back on current time.

        In most cases, we can assume that the time we receive a completed envelope
        is pretty close to when the envelope was actually completed.
        """
        get_val.return_value = 'Some invalid time'
        now_diff = datetime.utcnow() - self.env.time_signed
        self.assertLess(abs(now_diff), timedelta(seconds=1))
        get_val.assert_called()

    def test_releasor_email(self):
        """ The releasor's email is parsed out. """
        self.assertEqual(self.env.releasor_email, 'tim@mit.edu')

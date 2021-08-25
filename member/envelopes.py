""" Parse the XML payload delivered when a DocuSign envelope is completed.

Envelopes are delivered to endpoints via the eventNotification setting -
this utility module parses out the MITOC member's information.
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from mitoc_const import affiliations


class DocuSignDocumentHelpers:
    """Generic helpers for use in parsing any DocuSign XML document."""

    ns = {'docu': "http://www.docusign.net/API/3.0"}
    recipient_status = ['EnvelopeStatus', 'RecipientStatuses', 'RecipientStatus']

    def __init__(self, xml_contents):
        self.root = ET.fromstring(xml_contents)

    def get_element(self, hierarchy, findall=False):
        """Return a single element from an array of XPath selectors."""
        # (This method exists to ease the pain of namespaces with ElementTree)
        xpath = '/'.join('docu:{}'.format(tag) for tag in hierarchy)
        if findall:
            return self.root.findall(xpath, self.ns)
        return self.root.find(xpath, self.ns)

    def get_val(self, hierarchy):
        """Return the value in a single element."""
        return self.get_element(hierarchy).text.strip()

    def _get_hours_offset(self):
        return self.get_val(['TimeZoneOffset'])

    def _to_utc(self, datetime_string):
        """Convert datetimes from the document to UTC based on the supplied TZ."""
        hours_offset = int(self._get_hours_offset())
        # DocuSign seems to perhaps be transitioning over datetime formats?
        # It sometimes gives datetimes with microseconds, sometimes without...
        # (First observed datetimes without microseconds in September of 2018)
        try:
            ts = datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            ts = datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S.%f")

        utc_datetime = ts - timedelta(hours=hours_offset)
        return utc_datetime.replace(tzinfo=timezone.utc)


class CompletedEnvelope(DocuSignDocumentHelpers):
    """Navigate a DocuSignEnvelopeInformation resource (completed waiver)."""

    def __init__(self, xml_contents):
        """Error out early if it's the unexpected document type."""
        super().__init__(xml_contents)
        tag = '{%s}DocuSignEnvelopeInformation' % self.ns['docu']
        if self.root.tag != tag:
            raise ValueError("Expected {} as root element".format(tag))

    def _first_and_last(self):
        """A tuple that always contains the last name, and sometimes the last.

        If there's no spacing given in the name, we just assume that the user
        only reported their first name, and no last name.
        """
        return self.releasor_name.split(None, 1)

    @property
    def first_name(self):
        """First name of the MITOC member this waiver is for."""
        return self._first_and_last()[0]

    @property
    def last_name(self):
        """Last name of the MITOC member this waiver is for."""
        try:
            return self._first_and_last()[1]
        except IndexError:  # No space given, we don't know the last name
            return ''

    @property
    def completed(self):
        """Return if all recipients have completed this envelope.

        (It's possible for a user to have completed their part, but the waiver
        is still awaiting a guardian's signature).
        """
        return self.get_val(['EnvelopeStatus', 'Status']) == 'Completed'

    @property
    def time_signed(self):
        """Return the timestamp when the document was signed."""
        if not self.completed:
            raise ValueError("Incompleted documents are not signed!")
        time_signed = self.get_val(['EnvelopeStatus', 'Completed'])
        return self._to_utc(time_signed)

    def _all_tab_statuses(self):
        """Yield the label and value for all tab statuses in the document.

        This method is complicated by the fact that:
        - a self-closing tab actually has None as its value for .text
        - ET elements are somehow _falsy_ - we must explicitly compare to None
        """
        selector = self.recipient_status + ['TabStatuses', 'TabStatus']
        for tab in self.get_element(selector, findall=True):
            label = tab.find('docu:TabLabel', self.ns).text.strip()
            tab_value = tab.find('docu:TabValue', self.ns)
            value = None if tab_value is None else tab_value.text
            yield label, (value and value.strip())

    def tab_status(self, desired_label):
        """Return the value for a specific tab status.

        ElementTree has rudimentary support for XPath, so we use a simple
        iterable instead.
        """
        for label, value in self._all_tab_statuses():
            if label == desired_label:
                return value
        raise ValueError("Missing {}!".format(desired_label))

    @property
    def releasor_email(self):
        """The email of the person who signed the release."""
        return self.tab_status("Releasor's Email")

    @property
    def releasor_name(self):
        """The name of the person who signed the release."""
        return self.tab_status("Releasor's Name")

    @property
    def affiliation(self):
        """The member's stated affiliation to MIT."""
        selector = self.recipient_status + [
            'FormData',
            'xfdf',
            'fields',
            "field[@name='Affiliation']",
            'value',
        ]
        stated_affiliation = self.get_element(selector).text
        assert stated_affiliation in {aff.VALUE for aff in affiliations.ALL}
        return stated_affiliation

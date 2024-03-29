"""
Based off of cybersource.signature from django-oscar-cybersource
"""
import base64
import hashlib
import hmac
from typing import Iterable


def signature_valid(data, secret_key: str) -> bool:
    signature_check = SecureAcceptanceSigner(secret_key)
    try:
        return signature_check.verify_request(data)
    except ValueError:
        return False


class SecureAcceptanceSigner:
    secret_key: str

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def sign(self, data, signed_fields: Iterable[str]):
        key = self.secret_key.encode('utf-8')
        msg_raw = self._build_message(data, signed_fields).encode('utf-8')
        msg_hmac = hmac.new(key, msg_raw, hashlib.sha256)
        return base64.b64encode(msg_hmac.digest())

    def verify_request(self, post_data) -> bool:
        """Ensure the signature is valid so this request can be trusted."""
        signed_field_names = post_data.get('signed_field_names')
        if not signed_field_names:
            raise ValueError("Request has no fields to verify")
        signed_field_names = signed_field_names.split(',')
        signature_given = post_data['signature'].encode('utf-8')
        signature_calc = self.sign(post_data, signed_field_names)
        return signature_given == signature_calc

    @staticmethod
    def _build_message(data, signed_fields) -> str:
        return ','.join(f"{f}={data.get(f, '')}" for f in signed_fields)

import unittest
from unittest import mock

from flask import Flask

from member import app


class WsgiTest(unittest.TestCase):
    def test_exposes_app_in_application_var(self):
        """ The WSGI script expects an application available. """
        with mock.patch.object(app, 'create_app', wraps=app.create_app) as create_app:
            from member import wsgi  # pylint: disable=import-outside-toplevel
        create_app.assert_called_once()
        self.assertTrue(isinstance(wsgi.application, Flask))
        self.assertTrue(hasattr(wsgi.application, 'wsgi_app'))

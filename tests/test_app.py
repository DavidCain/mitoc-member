import os
import unittest
from importlib import reload
from unittest import mock

from raven.contrib.flask import Sentry

from member import app, extensions

DUMMY_RAVEN_DSN = 'https://aa11bb22cc33dd44ee55ff6601234560@sentry.io/104648'


class AppInitializationTests(unittest.TestCase):
    def test_sentry_conditionally_loaded(self):
        """ Sentry is only initialized when `RAVEN_DSN` is provided. """
        with mock.patch.dict('os.environ', {'RAVEN_DSN': DUMMY_RAVEN_DSN}):
            # Reload the extensions module so that extensions.sentry is redefined!
            reload(extensions)
        sentry = extensions.sentry

        # We initialized a Sentry instance!
        self.assertTrue(isinstance(sentry, Sentry))

        # Make sure that Sentry is initialized (but don't actually mock away the instantiation!)
        with mock.patch.object(sentry, 'init_app', wraps=sentry.init_app) as init_app:
            created_app = app.create_app()

        init_app.assert_called_once_with(created_app)

    def test_sentry_not_loaded(self):
        """ Sentry is only initialized when `RAVEN_DSN` is provided. """

        # Mock an environment with no variables at all, load extensions
        with mock.patch.dict('os.environ', {}):
            self.assertNotIn('RAVEN_DSN', os.environ)
            reload(extensions)  # Reload so extensions initialize from empty env vars

        self.assertIsNone(extensions.sentry)

        # We can successfully create the app, despite a Sentry object never being created.
        with mock.patch.object(Sentry, '__init__') as sentry_class:
            app.create_app()
        sentry_class.assert_not_called()

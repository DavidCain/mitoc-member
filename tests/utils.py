from importlib import reload
from unittest import mock

from member import extensions, settings
from member.app import create_app


def create_app_with_env_vars(desired_env_vars):
    """ Create an application with the given environment variables! """
    # NOTE: We avoid using the context manager pattern for patching
    # since `raven-python` will raise deprecation warnings! See raven-python #1296
    patch = mock.patch.dict('os.environ', desired_env_vars, clear=True)
    patch.start()

    reload_affected_modules()
    app = create_app()

    patch.stop()

    # Now that we're done mocking the environment variables, reload settings & extensions
    # (This will prevent persisting changes across multiple test runs)
    reload_affected_modules()
    return app


def reload_affected_modules():
    """ Reload any modules that are affected by toying with env vars.

    This is useful for both:
    1. Re-loading to pull in *new* values after settings env vars
    2. Restoring to their previous state before mucking with env vars
    """
    reload(settings)  # Application settings are used to populate `app.config`
    reload(extensions)  # Sentry is configured on import & reads values from env vars

import pytest

from seo_app import create_app
from seo_app.config import TestConfig


@pytest.fixture
def app():
    application = create_app(TestConfig)
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()

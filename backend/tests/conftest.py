"""Legacy business-flow tests run as one explicit authenticated test user."""
from uuid import UUID
import pytest
from app.main import app
from app.auth import current_user
TEST_USER = UUID('11111111-1111-4111-8111-111111111111')

@pytest.fixture(autouse=True)
def authenticated_business_tests(request):
    if request.module.__name__.endswith('test_auth'):
        yield
        return
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)

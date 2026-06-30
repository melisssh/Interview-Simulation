import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.routers import auth


@pytest.fixture(autouse=True)
def clear_rate_limit_store():
    """Reset in-memory rate limit store before and after each test.
    Prevents test-order-dependent failures caused by shared IP in TestClient.
    Production rate limiting is unaffected.
    """
    auth._rate_store.clear()
    yield
    auth._rate_store.clear()

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

# Import the FastAPI app
from app.main import app
from app.core.deps import get_current_user
from app.core.supabase_client import supabase

# Mock Supabase client
@pytest.fixture(autouse=True)
def mock_supabase(mocker):
    # Mock the global supabase client returned by supabase()
    mock_sb = MagicMock()
    mocker.patch("app.core.supabase_client.supabase", return_value=mock_sb)
    # Also patch anywhere else it might be directly imported if needed, but the codebase uses supabase() getter.
    mocker.patch("app.crud.crud_batch.supabase", return_value=mock_sb)
    mocker.patch("app.crud.crud_class.supabase", return_value=mock_sb)
    mocker.patch("app.crud.crud_package.supabase", return_value=mock_sb)
    mocker.patch("app.crud.crud_material.supabase", return_value=mock_sb)
    mocker.patch("app.crud.crud_curriculum.supabase", return_value=mock_sb)
    mocker.patch("app.crud.crud_testimonial.supabase", return_value=mock_sb)
    return mock_sb

@pytest.fixture
def test_client():
    # Use TestClient for synchronous API testing
    with TestClient(app) as client:
        yield client

# Helper to override authentication
def override_get_current_user_admin():
    return {
        "id": "admin-id-123",
        "email": "admin@test.com",
        "role": "admin",
        "full_name": "Admin User"
    }

def override_get_current_user_normal():
    return {
        "id": "user-id-123",
        "email": "user@test.com",
        "role": "user",
        "full_name": "Normal User"
    }

def override_get_current_user_superadmin():
    return {
        "id": "superadmin-id-123",
        "email": "superadmin@test.com",
        "role": "superadmin",
        "full_name": "Super Admin"
    }

@pytest.fixture
def auth_client_superadmin(test_client):
    app.dependency_overrides[get_current_user] = override_get_current_user_superadmin
    yield test_client
    app.dependency_overrides = {}

@pytest.fixture
def auth_client_admin(test_client):
    app.dependency_overrides[get_current_user] = override_get_current_user_admin
    yield test_client
    app.dependency_overrides = {}

@pytest.fixture
def auth_client_user(test_client):
    app.dependency_overrides[get_current_user] = override_get_current_user_normal
    yield test_client
    app.dependency_overrides = {}


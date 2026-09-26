from unittest.mock import patch


def test_public_settings_returns_maintenance_defaults(test_client, mock_supabase):
    execute = (
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute
    )
    execute.return_value.data = []

    response = test_client.get(
        "/settings?keys=maintenance_mode&keys=maintenance_message"
    )

    assert response.status_code == 200
    assert response.json() == {
        "maintenance_mode": "false",
        "maintenance_message": (
            "Situs sedang dalam maintenance. Silakan coba lagi nanti."
        ),
    }


def test_public_settings_reject_private_key(test_client, mock_supabase):
    response = test_client.get("/settings?keys=checkout_bank_account")

    assert response.status_code in (400, 403)
    mock_supabase.table.assert_not_called()


def test_admin_settings_returns_env_fallback(auth_client_admin, mock_supabase):
    execute = (
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute
    )
    execute.return_value.data = []

    response = auth_client_admin.get("/admin/settings?keys=checkout_bank_name")

    assert response.status_code == 200
    assert response.json()["checkout_bank_name"]


def test_admin_settings_requires_authentication(test_client):
    response = test_client.get("/admin/settings?keys=checkout_bank_name")

    assert response.status_code == 401


def test_setting_write_validates_boolean(auth_client_admin, mock_supabase):
    response = auth_client_admin.put(
        "/settings/maintenance_mode", json={"value": "yes"}
    )

    assert response.status_code == 400
    mock_supabase.table.assert_not_called()


def test_setting_write_validates_checkout_values(auth_client_admin, mock_supabase):
    blank_response = auth_client_admin.put(
        "/settings/checkout_bank_name", json={"value": "   "}
    )
    invalid_url_response = auth_client_admin.put(
        "/settings/checkout_group_link",
        json={"value": "not-a-url"},
    )

    assert blank_response.status_code == 400
    assert invalid_url_response.status_code == 400
    mock_supabase.table.assert_not_called()


def test_allowed_setting_write_is_single_upsert(auth_client_admin, mock_supabase):
    mock_supabase.table.return_value.upsert.return_value.execute.return_value.data = [
        {"key": "maintenance_mode", "value": "true"}
    ]

    response = auth_client_admin.put(
        "/settings/maintenance_mode", json={"value": "true"}
    )

    assert response.status_code == 200
    mock_supabase.table.return_value.select.assert_not_called()
    mock_supabase.table.return_value.upsert.assert_called_once_with(
        {"key": "maintenance_mode", "value": "true"}, on_conflict="key"
    )


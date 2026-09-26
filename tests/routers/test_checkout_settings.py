from types import SimpleNamespace
from unittest.mock import patch


def _set_setting_rows(mock_supabase, rows):
    execute = (
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute
    )
    execute.return_value.data = rows


def test_checkout_info_prefers_database_values(auth_client_user, mock_supabase):
    _set_setting_rows(
        mock_supabase,
        [
            {"key": "checkout_bank_name", "value": "Bank DB"},
            {"key": "checkout_bank_account", "value": "123"},
            {"key": "checkout_bank_holder", "value": "Holder DB"},
            {"key": "checkout_group_link", "value": "https://example.com/group"},
        ],
    )

    response = auth_client_user.get("/checkout/info")

    assert response.status_code == 200
    assert response.json() == {
        "bank_name": "Bank DB",
        "bank_account": "123",
        "bank_holder": "Holder DB",
        "group_link": "https://example.com/group",
    }


def test_checkout_info_prefers_database_value_and_falls_back_to_env(
    auth_client_user, mock_supabase
):
    _set_setting_rows(mock_supabase, [])
    env_settings = SimpleNamespace(
        BANK_NAME="Bank Env",
        BANK_ACCOUNT="456",
        BANK_HOLDER="Holder Env",
        GROUP_LINK="https://example.com/env-group",
    )

    with patch("app.services.app_settings.get_settings", return_value=env_settings):
        response = auth_client_user.get("/checkout/info")

    assert response.status_code == 200
    assert response.json() == {
        "bank_name": "Bank Env",
        "bank_account": "456",
        "bank_holder": "Holder Env",
        "group_link": "https://example.com/env-group",
    }


def test_checkout_info_rejects_missing_payment_configuration(
    auth_client_user, mock_supabase
):
    _set_setting_rows(mock_supabase, [])
    env_settings = SimpleNamespace(
        BANK_NAME="",
        BANK_ACCOUNT="",
        BANK_HOLDER="",
        GROUP_LINK="",
    )

    with patch("app.services.app_settings.get_settings", return_value=env_settings):
        response = auth_client_user.get("/checkout/info")

    assert response.status_code == 503
    assert response.json()["detail"] == "Informasi pembayaran belum dikonfigurasi"


def test_payment_upload_intent_is_blocked_for_participant_during_maintenance(
    auth_client_user, mock_supabase
):
    _set_setting_rows(mock_supabase, [{"key": "maintenance_mode", "value": "true"}])
    with patch("app.routers.orders.crud_order") as crud:
        crud.create_payment_upload_intent.return_value = {
            "signed_url": "https://example.com/upload",
            "path": "user-1/proof.jpg",
            "expires_at": "2026-09-26T00:00:00Z",
            "max_size_bytes": 2_000_000,
        }
        response = auth_client_user.post(
            "/orders/upload-intent",
            json={"content_type": "image/jpeg", "size_bytes": 100},
        )

    assert response.status_code == 503
    crud.create_payment_upload_intent.assert_not_called()


def test_order_creation_is_blocked_for_participant_during_maintenance(
    auth_client_user, mock_supabase
):
    _set_setting_rows(mock_supabase, [{"key": "maintenance_mode", "value": "true"}])
    with patch("app.routers.orders.crud_order") as crud:
        crud.create_order_transactional.return_value = {
            "id": "order-1",
            "user_id": "user-id-123",
            "items": [],
            "total": 100,
            "status": "pending",
        }
        response = auth_client_user.post(
            "/orders",
            json={
                "items": [{"item_id": "class-1", "item_type": "class", "qty": 1}],
                "proof_path": "user-1/proof.jpg",
            },
        )

    assert response.status_code == 503
    crud.create_order_transactional.assert_not_called()


def test_staff_can_upload_during_maintenance(auth_client_admin, mock_supabase):
    _set_setting_rows(mock_supabase, [{"key": "maintenance_mode", "value": "true"}])
    with patch("app.routers.orders.crud_order") as crud:
        crud.create_payment_upload_intent.return_value = {
            "signed_url": "https://example.com/upload",
            "path": "admin/proof.jpg",
            "expires_at": "2026-09-26T00:00:00Z",
            "max_size_bytes": 2_000_000,
        }
        response = auth_client_admin.post(
            "/orders/upload-intent",
            json={"content_type": "image/jpeg", "size_bytes": 100},
        )

    assert response.status_code == 201
    crud.create_payment_upload_intent.assert_called_once_with(
        "admin-id-123", "image/jpeg", 100
    )


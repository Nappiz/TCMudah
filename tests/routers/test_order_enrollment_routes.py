from unittest.mock import patch


def test_new_order_response_exposes_automatic_fulfillment(auth_client_user):
    order = {
        "id": "order-1",
        "user_id": "user-id-123",
        "items": [],
        "total": 0,
        "status": "pending",
        "fulfillment_mode": "automatic",
    }
    with patch("app.routers.orders.crud_order") as crud:
        crud.create_order_transactional.return_value = order
        response = auth_client_user.post(
            "/orders",
            json={
                "items": [{"item_id": "class-1", "item_type": "class", "qty": 1}],
                "proof_path": "user-id-123/proof.png",
            },
        )

    assert response.status_code == 201
    assert response.json()["fulfillment_mode"] == "automatic"


def test_order_rejects_multiple_quantities_for_one_participant(auth_client_user):
    with patch("app.routers.orders.crud_order") as crud:
        response = auth_client_user.post(
            "/orders",
            json={
                "items": [{"item_id": "class-1", "item_type": "class", "qty": 2}],
                "proof_path": "user-id-123/proof.png",
            },
        )

    assert response.status_code == 422
    crud.create_order_transactional.assert_not_called()


def test_unfulfillable_approval_returns_conflict_to_admin(auth_client_admin):
    with patch("app.routers.orders.crud_order") as crud:
        crud.update_order_status.side_effect = Exception(
            "Snapshot paket tidak lengkap: database detail should stay private"
        )
        response = auth_client_admin.patch(
            "/admin/orders/order-1/status", json={"status": "approved"}
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Snapshot paket tidak lengkap"


def test_duplicate_package_class_returns_conflict_to_admin(auth_client_admin):
    with patch("app.routers.orders.crud_order") as crud:
        crud.update_order_status.side_effect = Exception(
            "Snapshot paket berisi kelas duplikat: database detail should stay private"
        )
        response = auth_client_admin.patch(
            "/admin/orders/order-1/status", json={"status": "approved"}
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Snapshot paket berisi kelas duplikat"


def test_status_response_preserves_fulfillment_mode(auth_client_admin):
    with patch("app.routers.orders.crud_order") as crud:
        crud.update_order_status.return_value = {
            "id": "order-1",
            "user_id": "user-id-123",
            "items": [],
            "total": 0,
            "status": "approved",
            "fulfillment_mode": "legacy_manual",
        }
        response = auth_client_admin.patch(
            "/admin/orders/order-1/status", json={"status": "approved"}
        )

    assert response.status_code == 200
    assert response.json()["fulfillment_mode"] == "legacy_manual"

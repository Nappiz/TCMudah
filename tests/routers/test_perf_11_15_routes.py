from unittest.mock import patch


class UniqueViolation(Exception):
    code = "23505"


def test_material_access_denial_is_mapped_to_403(auth_client_user):
    with patch("app.routers.materials.crud_material") as crud:
        crud.get_authorized_materials.side_effect = Exception(
            "Tidak punya akses ke kelas ini"
        )
        response = auth_client_user.get("/materials?class_id=class-1")

    assert response.status_code == 403
    assert response.json()["detail"] == "Tidak punya akses ke kelas ini"


def test_feedback_submission_is_one_service_call(auth_client_user):
    row = {
        "id": "feedback-1",
        "class_id": "class-1",
        "text": "Materinya sangat membantu",
        "rating": 5,
    }
    with patch("app.routers.feedback.crud_feedback") as crud:
        crud.submit_feedback.return_value = row
        response = auth_client_user.post(
            "/feedback",
            json={
                "class_id": "class-1",
                "message": "Materinya sangat membantu",
                "rating": 5,
            },
        )

    assert response.status_code == 200
    crud.submit_feedback.assert_called_once_with(
        "user-id-123", "class-1", False, "Materinya sangat membantu", 5
    )


def test_payment_upload_intent_rejects_oversized_file(auth_client_user):
    response = auth_client_user.post(
        "/orders/upload-intent",
        json={"content_type": "image/jpeg", "size_bytes": 2_000_001},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Ukuran bukti pembayaran terlalu besar"


def test_payment_proof_redirect_is_private_and_not_cacheable(auth_client_admin):
    with patch("app.routers.orders.crud_order") as crud:
        crud.get_order_proof_path.return_value = "user-1/proof.jpg"
        crud.create_payment_proof_read_url.return_value = (
            "https://storage.example/read?token=signed"
        )
        response = auth_client_admin.get(
            "/admin/orders/order-1/proof", follow_redirects=False
        )

    assert response.status_code == 302
    assert response.headers["location"] == (
        "https://storage.example/read?token=signed"
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_settings_batch_get_is_one_query(test_client, mock_supabase):
    execute = (
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute
    )
    execute.return_value.data = [
        {"key": "maintenance_mode", "value": "true"},
        {"key": "maintenance_message", "value": "Pause"},
    ]

    response = test_client.get(
        "/settings?keys=maintenance_mode&keys=maintenance_message"
    )

    assert response.status_code == 200
    assert response.json() == {
        "maintenance_mode": "true",
        "maintenance_message": "Pause",
    }
    mock_supabase.table.assert_called_once_with("app_settings")


def test_setting_write_is_single_upsert(auth_client_admin, mock_supabase):
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


def test_shortlink_uniqueness_is_enforced_by_database(auth_client_admin):
    with patch("app.routers.shortlinks.crud_shortlink") as crud:
        crud.create_shortlink.side_effect = UniqueViolation()
        response = auth_client_admin.post(
            "/admin/shortlinks",
            json={
                "slug": "Docs",
                "url": "https://example.com",
                "active": True,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Slug sudah dipakai"
    crud.create_shortlink.assert_called_once()
    crud.check_slug_exists.assert_not_called()


def test_registration_relies_on_unique_insert_without_precheck(test_client):
    with (
        patch("app.routers.auth.hash_password", return_value="hash"),
        patch("app.routers.auth.crud_user") as crud,
    ):
        crud.create_user.side_effect = UniqueViolation()
        response = test_client.post(
            "/auth/register",
            json={
                "email": "USER@EXAMPLE.COM",
                "password": "secret123",
                "full_name": "Test User",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email sudah terdaftar"
    crud.get_user_by_email.assert_not_called()
    crud.create_user.assert_called_once_with(
        "user@example.com", "hash", "Test User", None
    )

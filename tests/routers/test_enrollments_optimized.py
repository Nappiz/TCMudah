from unittest.mock import patch


BOOTSTRAP = {
    "participants": [
        {"id": "user-id-123", "full_name": "User", "email": "user@test.com"}
    ],
    "classes": [{"id": "class-1", "title": "Class 1"}],
    "packages": [{"id": "package-1", "title": "Package 1", "class_ids": ["class-1"]}],
    "selected_user": {"id": "user-id-123", "full_name": "User", "email": "user@test.com"},
    "active_class_ids": ["class-1"],
    "next_cursor": None,
    "has_more": False,
}


def test_enrollment_bootstrap_returns_one_use_case_payload(auth_client_admin):
    with patch("app.routers.enrollments.crud_enrollment") as crud:
        crud.get_enrollment_bootstrap.return_value = BOOTSTRAP

        response = auth_client_admin.get("/admin/enrollments/bootstrap?limit=50")

        assert response.status_code == 200
        assert response.json()["active_class_ids"] == ["class-1"]
        crud.get_enrollment_bootstrap.assert_called_once_with(None, "", 50, None)


def test_enrollment_candidates_are_role_protected(auth_client_user):
    with patch("app.routers.enrollments.crud_enrollment") as crud:
        response = auth_client_user.get("/admin/enrollments/candidates")

        assert response.status_code == 403
        crud.get_enrollment_candidates.assert_not_called()


def test_active_class_ids_returns_minimal_projection(auth_client_admin):
    with patch("app.routers.enrollments.crud_enrollment") as crud:
        crud.get_active_class_ids.return_value = ["class-1", "class-2"]

        response = auth_client_admin.get(
            "/admin/enrollments/active-class-ids?user_id=user-id-123"
        )

        assert response.status_code == 200
        assert response.json() == {"class_ids": ["class-1", "class-2"]}
        crud.get_active_class_ids.assert_called_once_with("user-id-123")


def test_set_enrollments_delegates_to_one_transactional_service(auth_client_admin):
    with patch("app.routers.enrollments.crud_enrollment") as crud:
        crud.set_user_enrollments.return_value = []

        response = auth_client_admin.post(
            "/admin/enrollments/set",
            json={"user_id": "user-id-123", "class_ids": []},
        )

        assert response.status_code == 200
        assert response.json() == []
        crud.set_user_enrollments.assert_called_once_with(
            "user-id-123", [], "admin-id-123"
        )

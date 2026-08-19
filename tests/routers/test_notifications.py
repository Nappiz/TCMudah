"""
Unit tests for app.routers.notifications.

Target: app.routers.notifications
"""

import pytest
from unittest.mock import patch

class TestNotificationsRouter:
    @pytest.fixture
    def mock_crud(self):
        with patch("app.routers.notifications.get_notifications_summary") as mock_crud:
            yield mock_crud

    def test_get_summary_success(self, auth_client_admin, mock_crud):
        """Admin should be able to get notifications summary."""
        mock_crud.return_value = {
            "new_orders": 2,
            "new_users": 5,
            "new_feedbacks": 1
        }
        
        response = auth_client_admin.get("/admin/notifications/summary")
        
        assert response.status_code == 200
        assert response.json() == {
            "new_orders": 2,
            "new_users": 5,
            "new_feedbacks": 1
        }
        mock_crud.assert_called_once_with(
            last_seen_users=None,
            last_seen_feedbacks=None
        )

    def test_get_summary_with_params(self, auth_client_superadmin, mock_crud):
        """Superadmin should be able to get summary with query params."""
        mock_crud.return_value = {
            "new_orders": 1,
            "new_users": 0,
            "new_feedbacks": 0
        }
        
        response = auth_client_superadmin.get(
            "/admin/notifications/summary?last_seen_users=date1&last_seen_feedbacks=date2"
        )
        
        assert response.status_code == 200
        mock_crud.assert_called_once_with(
            last_seen_users="date1",
            last_seen_feedbacks="date2"
        )

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ],
        ids=["admin_success", "superadmin_success", "user_forbidden"]
    )
    def test_get_summary_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Verify role-based access for notifications summary."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.return_value = {
            "new_orders": 0,
            "new_users": 0,
            "new_feedbacks": 0
        }
        
        response = client.get("/admin/notifications/summary")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.assert_called_once()
        else:
            mock_crud.assert_not_called()

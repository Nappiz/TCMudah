from unittest.mock import patch


def dashboard_payload():
    return {
        "stats": {
            "total_users": 4,
            "superadmin": 1,
            "admin": 1,
            "mentor": 1,
            "peserta": 1,
            "new_users_30d": 1,
            "total_curriculum": 2,
            "total_testimonials": 3,
            "visible_testimonials": 2,
            "hidden_testimonials": 1,
            "total_mentors": 1,
            "visible_mentors": 1,
            "total_classes": 2,
            "visible_classes": 2,
            "class_per_mentor": 2,
            "total_orders": 2,
            "pending_orders": 1,
            "approved_orders": 1,
            "rejected_orders": 0,
            "expired_orders": 0,
            "revenue_approved": 100000,
            "revenue_30d": 100000,
            "participants_active": 1,
            "aov": 100000,
            "approval_rate": 50,
            "order_series": [{"key": "2026-09-20", "value": 2}],
            "revenue_series": [{"key": "2026-09-20", "value": 100000}],
        },
        "period": {
            "total_orders": 2,
            "pending_orders": 1,
            "approved_orders": 1,
            "rejected_orders": 0,
            "expired_orders": 0,
            "revenue_approved": 100000,
            "aov": 100000,
            "approval_rate": 50,
            "class_revenue": 100000,
            "package_revenue": 0,
            "top_classes": [
                {"id": "class-1", "title": "Class 1", "count": 1, "revenue": 100000}
            ],
        },
        "pending_latest": [],
        "recent_orders": [],
    }


def test_dashboard_overview_uses_one_aggregate_service(auth_client_admin):
    with patch("app.routers.dashboard.crud_dashboard") as crud:
        crud.get_dashboard_overview.return_value = dashboard_payload()

        response = auth_client_admin.get(
            "/admin/dashboard/overview?start_date=2026-09-01&end_date=2026-09-20&days=14"
        )

        assert response.status_code == 200
        assert response.json()["stats"]["new_users_30d"] == 1
        crud.get_dashboard_overview.assert_called_once_with(
            "2026-09-01T00:00:00+00:00",
            "2026-09-21T00:00:00+00:00",
            14,
        )


def test_dashboard_rejects_inverted_date_range(auth_client_admin):
    response = auth_client_admin.get(
        "/admin/dashboard/overview?start_date=2026-09-20&end_date=2026-09-01"
    )
    assert response.status_code == 400


def test_dashboard_is_role_protected(auth_client_user):
    response = auth_client_user.get("/admin/dashboard/overview")
    assert response.status_code == 403

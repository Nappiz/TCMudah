from unittest.mock import patch


def test_admin_feedback_is_paginated_in_one_service_call(auth_client_admin):
    with patch("app.routers.feedback.crud_feedback") as crud:
        crud.get_admin_feedbacks.return_value = (
            1,
            [
                {
                    "id": "feedback-1",
                    "class_id": "class-1",
                    "text": "Bagus sekali",
                    "rating": 5,
                    "class_title": "Class 1",
                }
            ],
        )
        response = auth_client_admin.get(
            "/admin/feedback?page=2&limit=20&class_id=class-1"
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    crud.get_admin_feedbacks.assert_called_once_with(
        limit=20, offset=20, class_id="class-1"
    )


def test_admin_shortlinks_is_paginated_and_searchable(auth_client_admin):
    with patch("app.routers.shortlinks.crud_shortlink") as crud:
        crud.get_admin_shortlinks.return_value = (0, [])
        response = auth_client_admin.get(
            "/admin/shortlinks?page=3&limit=10&search=docs"
        )

    assert response.status_code == 200
    assert response.json() == {"total": 0, "data": []}
    crud.get_admin_shortlinks.assert_called_once_with(
        limit=10, offset=20, search="docs"
    )

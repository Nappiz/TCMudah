from unittest.mock import MagicMock

from app.crud.crud_feedback import get_admin_feedbacks
from app.crud.crud_shortlink import get_admin_shortlinks


def test_feedback_page_is_one_joined_rpc(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(
        data={"total": 2, "data": [{"id": "feedback-1"}]}
    )

    total, data = get_admin_feedbacks(20, 20, "class-1")

    assert total == 2
    assert data[0]["id"] == "feedback-1"
    mock_supabase.rpc.assert_called_once_with(
        "admin_paginated_feedbacks",
        {"p_limit": 20, "p_offset": 20, "p_class_id": "class-1"},
    )


def test_shortlink_page_is_one_search_rpc(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(
        data={"total": 1, "data": [{"id": "shortlink-1"}]}
    )

    total, data = get_admin_shortlinks(20, 0, "docs")

    assert total == 1
    assert data[0]["id"] == "shortlink-1"
    mock_supabase.rpc.assert_called_once_with(
        "admin_paginated_shortlinks",
        {"p_limit": 20, "p_offset": 0, "p_search": "docs"},
    )

"""Unit tests for the single-RPC notification summary read path."""

from unittest.mock import MagicMock

from app.crud.crud_notifications import get_notifications_summary


def test_get_notifications_summary_uses_one_rpc(mock_supabase):
    response = MagicMock()
    response.data = {"new_orders": 5, "new_users": 0, "new_feedbacks": 0}
    mock_supabase.rpc.return_value.execute.return_value = response

    result = get_notifications_summary()

    assert result == {"new_orders": 5, "new_users": 0, "new_feedbacks": 0}
    mock_supabase.rpc.assert_called_once_with(
        "admin_notification_summary",
        {"p_last_seen_users": None, "p_last_seen_feedbacks": None},
    )
    mock_supabase.table.assert_not_called()


def test_get_notifications_summary_forwards_timestamps(mock_supabase):
    response = MagicMock()
    response.data = {"new_orders": 2, "new_users": 10, "new_feedbacks": 3}
    mock_supabase.rpc.return_value.execute.return_value = response

    result = get_notifications_summary(
        last_seen_users="2023-01-01T00:00:00+00:00",
        last_seen_feedbacks="2023-01-02T00:00:00+00:00",
    )

    assert result == {"new_orders": 2, "new_users": 10, "new_feedbacks": 3}
    mock_supabase.rpc.assert_called_once_with(
        "admin_notification_summary",
        {
            "p_last_seen_users": "2023-01-01T00:00:00+00:00",
            "p_last_seen_feedbacks": "2023-01-02T00:00:00+00:00",
        },
    )

from unittest.mock import MagicMock

from app.crud.crud_dashboard import get_dashboard_overview


def test_dashboard_overview_uses_single_rpc(mock_supabase):
    response = MagicMock()
    response.data = {"stats": {}, "period": {}, "pending_latest": [], "recent_orders": []}
    mock_supabase.rpc.return_value.execute.return_value = response

    result = get_dashboard_overview("start", "end", 14)

    assert result["pending_latest"] == []
    mock_supabase.rpc.assert_called_once_with(
        "admin_dashboard_overview",
        {"p_start_at": "start", "p_end_at": "end", "p_days": 14},
    )
    mock_supabase.table.assert_not_called()

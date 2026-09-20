from unittest.mock import MagicMock

from app.crud.crud_user import get_paginated_users


def test_paginated_users_uses_single_rpc(mock_supabase):
    response = MagicMock()
    response.data = {
        "total": 1,
        "data": [
            {
                "id": "u1",
                "email": "user@example.com",
                "full_name": "User",
                "nim": None,
                "role": "peserta",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
    }
    mock_supabase.rpc.return_value.execute.return_value = response

    total, rows = get_paginated_users(20, 0, "user", "peserta")

    assert total == 1
    assert rows[0]["id"] == "u1"
    mock_supabase.rpc.assert_called_once_with(
        "admin_paginated_users",
        {"p_limit": 20, "p_offset": 0, "p_search": "user", "p_role": "peserta"},
    )
    mock_supabase.table.assert_not_called()


def test_paginated_users_clamps_unbounded_requests(mock_supabase):
    response = MagicMock()
    response.data = {"total": 0, "data": []}
    mock_supabase.rpc.return_value.execute.return_value = response

    get_paginated_users(10_000, -5)

    mock_supabase.rpc.assert_called_once_with(
        "admin_paginated_users",
        {"p_limit": 100, "p_offset": 0, "p_search": None, "p_role": None},
    )

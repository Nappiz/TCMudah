from unittest.mock import MagicMock

from app.crud.crud_catalog import get_public_catalog


def test_catalog_uses_one_rpc(mock_supabase):
    payload = {
        "active_batch_id": None,
        "mentors": [],
        "curriculum": [],
        "classes": [],
        "packages": [],
    }
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(data=payload)

    assert get_public_catalog() == payload
    mock_supabase.rpc.assert_called_once_with("get_public_catalog", {})
    mock_supabase.table.assert_not_called()

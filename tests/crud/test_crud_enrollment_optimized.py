from unittest.mock import MagicMock

from app.crud.crud_enrollment import (
    get_active_class_ids,
    get_enrollment_bootstrap,
    get_enrollment_candidates,
    set_package_enrollments,
    set_user_enrollments,
)


def test_bootstrap_uses_single_rpc_and_encodes_cursor(mock_supabase):
    response = MagicMock()
    response.data = {
        "participants": [],
        "classes": [],
        "packages": [],
        "selected_user": None,
        "active_class_ids": [],
        "has_more": True,
        "next_after_name": "user",
        "next_after_id": "00000000-0000-0000-0000-000000000001",
    }
    mock_supabase.rpc.return_value.execute.return_value = response

    result = get_enrollment_bootstrap(limit=50)

    assert result["next_cursor"]
    assert "next_after_name" not in result
    mock_supabase.rpc.assert_called_once()
    mock_supabase.table.assert_not_called()


def test_candidates_decode_opaque_cursor(mock_supabase):
    first_response = MagicMock()
    first_response.data = {
        "participants": [],
        "has_more": True,
        "next_after_name": "user",
        "next_after_id": "00000000-0000-0000-0000-000000000001",
    }
    second_response = MagicMock()
    second_response.data = {
        "participants": [],
        "has_more": False,
        "next_after_name": None,
        "next_after_id": None,
    }
    mock_supabase.rpc.return_value.execute.side_effect = [first_response, second_response]

    cursor = get_enrollment_candidates()["next_cursor"]
    get_enrollment_candidates(cursor=cursor)

    _, second_call = mock_supabase.rpc.call_args_list
    assert second_call.args[1]["p_after_name"] == "user"
    assert second_call.args[1]["p_after_id"] == "00000000-0000-0000-0000-000000000001"


def test_active_class_ids_selects_only_required_column(mock_supabase):
    chain = mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = MagicMock(data=[{"class_id": "class-1"}])

    assert get_active_class_ids("user-1") == ["class-1"]
    mock_supabase.table.assert_called_once_with("enrollments")
    mock_supabase.table.return_value.select.assert_called_once_with("class_id")


def test_set_user_enrollments_is_one_transactional_rpc(mock_supabase):
    response = MagicMock(data=[])
    mock_supabase.rpc.return_value.execute.return_value = response

    assert set_user_enrollments("user-1", [], "admin-1") == []
    mock_supabase.rpc.assert_called_once_with(
        "admin_set_user_enrollments",
        {
            "p_user_id": "user-1",
            "p_class_ids": [],
            "p_assigned_by": "admin-1",
        },
    )
    mock_supabase.table.assert_not_called()


def test_set_package_enrollments_is_one_transactional_rpc(mock_supabase):
    response = MagicMock(data=[])
    mock_supabase.rpc.return_value.execute.return_value = response

    assert set_package_enrollments("user-1", "package-1", "admin-1") == []
    mock_supabase.rpc.assert_called_once_with(
        "admin_set_package_enrollments",
        {
            "p_user_id": "user-1",
            "p_package_id": "package-1",
            "p_assigned_by": "admin-1",
        },
    )

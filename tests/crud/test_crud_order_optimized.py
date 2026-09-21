from unittest.mock import MagicMock

from app.crud.crud_order import (
    create_order_transactional,
    get_paginated_orders,
    update_order_status,
)


def test_create_order_uses_single_transactional_rpc(mock_supabase):
    response = MagicMock(
        data={
            "id": "order-1",
            "user_id": "user-1",
            "items": [],
            "total": 0,
            "status": "pending",
        }
    )
    mock_supabase.rpc.return_value.execute.return_value = response

    result = create_order_transactional(
        "user-1",
        [{"item_id": "class-1", "item_type": "class", "qty": 1}],
        "user-1/proof.jpg",
        "User",
        None,
    )

    assert result["id"] == "order-1"
    mock_supabase.rpc.assert_called_once_with(
        "create_order_transactional",
        {
            "p_user_id": "user-1",
            "p_items": [
                {"item_id": "class-1", "item_type": "class", "qty": 1}
            ],
            "p_proof_path": "user-1/proof.jpg",
            "p_proof_bucket": "payments",
            "p_sender_name": "User",
            "p_note": None,
        },
    )
    mock_supabase.table.assert_not_called()


def test_order_page_combines_count_data_and_titles_in_one_rpc(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(
        data={"total": 1, "data": [{"id": "order-1", "items": []}]}
    )

    total, data = get_paginated_orders(20, 0, "user", "pending")

    assert total == 1
    assert data[0]["id"] == "order-1"
    mock_supabase.rpc.assert_called_once_with(
        "admin_paginated_orders",
        {
            "p_limit": 20,
            "p_offset": 0,
            "p_search": "user",
            "p_status": "pending",
        },
    )


def test_status_update_uses_returning_rpc_without_followup_select(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(
        data={"id": "order-1", "status": "approved"}
    )

    assert update_order_status("order-1", "approved")["status"] == "approved"
    mock_supabase.rpc.assert_called_once_with(
        "admin_update_order_status",
        {"p_order_id": "order-1", "p_status": "approved"},
    )
    mock_supabase.table.assert_not_called()

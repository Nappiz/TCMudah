from app.crud.crud_class import delete_class, get_all_classes
from app.crud.crud_package import delete_package, get_all_packages


def test_delete_class_uses_atomic_archive_rpc(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value.data = {"id": "class-1"}

    assert delete_class("class-1") == {"id": "class-1"}
    mock_supabase.rpc.assert_called_once_with(
        "admin_archive_class", {"p_class_id": "class-1"}
    )
    mock_supabase.table.assert_not_called()


def test_delete_package_archives_without_deleting_purchase_history(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value.data = {"id": "package-1"}

    assert delete_package("package-1") == {"id": "package-1"}
    mock_supabase.rpc.assert_called_once_with(
        "admin_archive_package", {"p_package_id": "package-1"}
    )
    mock_supabase.table.assert_not_called()


def test_admin_class_list_filters_archived_rows(mock_supabase):
    query = mock_supabase.table.return_value.select.return_value.order.return_value
    query.is_.return_value.execute.return_value.data = [{"id": "class-1"}]

    assert get_all_classes(batch_id="all") == [{"id": "class-1"}]
    query.is_.assert_called_once_with("archived_at", "null")


def test_admin_package_list_filters_archived_rows(mock_supabase):
    query = mock_supabase.table.return_value.select.return_value.order.return_value
    query.is_.return_value.execute.return_value.data = [{"id": "package-1"}]

    assert get_all_packages(batch_id="all") == [{"id": "package-1"}]
    query.is_.assert_called_once_with("archived_at", "null")

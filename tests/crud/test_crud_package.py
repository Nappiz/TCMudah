"""
Unit tests for app.crud.crud_package.

Target: app.crud.crud_package

Skenario:
1. Happy path: Mendapatkan semua package, package by id, create, update, delete.
2. Filter Logic: Verifikasi filter batch_id.
3. Behavioral Verification: Menganalisa parameter pemanggilan CRUD.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.crud.crud_package import (
    get_public_packages,
    get_all_packages,
    get_package_by_id,
    create_package,
    update_package,
    delete_package,
)

class TestCrudPackage:

    @pytest.fixture
    def mock_active_batch(self):
        """Mock fungsi get_active_batch_id_cached dari crud_package"""
        with patch("app.crud.crud_package.get_active_batch_id_cached") as mock_get_batch:
            mock_get_batch.return_value = "b1"
            yield mock_get_batch

    # ═══════════════════════════════════════════
    # Happy Path & Filtering
    # ═══════════════════════════════════════════

    def test_get_public_packages_with_active_batch(self, mock_supabase, mock_active_batch):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq1 = mock_select.eq.return_value
        mock_order = mock_eq1.order.return_value
        mock_eq2 = mock_order.eq.return_value
        
        mock_eq2.execute.return_value.data = [
            {"id": "p1", "title": "Package 1", "visible": True, "batch_id": "b1"}
        ]
        
        packages = get_public_packages()
        
        assert len(packages) == 1
        assert packages[0]["id"] == "p1"
        
        mock_active_batch.assert_called_once()
        mock_supabase.table.assert_called_once_with("packages")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("visible", True)
        mock_eq1.order.assert_called_once_with("created_at", desc=True)
        mock_order.eq.assert_called_once_with("batch_id", "b1")

    @pytest.mark.parametrize(
        "batch_id_arg, expected_batch_filter",
        [
            (None, "b1"),
            ("all", None),
            ("b2", "b2"),
        ]
    )
    def test_get_all_packages_filters(self, mock_supabase, mock_active_batch, batch_id_arg, expected_batch_filter):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_order = mock_select.order.return_value
        
        if expected_batch_filter:
            mock_eq = mock_order.eq.return_value
            mock_eq.execute.return_value.data = [{"id": "p1"}]
        else:
            mock_order.execute.return_value.data = [{"id": "p1"}]
            
        packages = get_all_packages(batch_id=batch_id_arg)
        
        assert len(packages) == 1
        
        if expected_batch_filter:
            mock_order.eq.assert_called_once_with("batch_id", expected_batch_filter)
        else:
            mock_order.eq.assert_not_called()

    # ═══════════════════════════════════════════
    # Mutations (Create, Update, Delete)
    # ═══════════════════════════════════════════

    def test_create_package_injects_batch(self, mock_supabase, mock_active_batch):
        mock_table = mock_supabase.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.data = [{"id": "new-package"}]
        
        pkg = create_package({"title": "New"})
        
        assert pkg["id"] == "new-package"
        mock_table.insert.assert_called_once_with({"title": "New", "batch_id": "b1"})

    def test_create_package_preserves_batch(self, mock_supabase, mock_active_batch):
        mock_table = mock_supabase.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.data = [{"id": "new-package"}]
        
        pkg = create_package({"title": "New", "batch_id": "custom-b"})
        
        assert pkg["id"] == "new-package"
        mock_table.insert.assert_called_once_with({"title": "New", "batch_id": "custom-b"})

    def test_update_package(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_update = mock_table.update.return_value
        mock_eq = mock_update.eq.return_value
        mock_eq.execute.return_value.data = [{"id": "p1"}]
        
        pkg = update_package("p1", {"title": "Updated Pkg"})
        
        assert pkg["id"] == "p1"
        mock_table.update.assert_called_once_with({"title": "Updated Pkg"})
        mock_update.eq.assert_called_once_with("id", "p1")
        
    def test_delete_package(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_delete = mock_table.delete.return_value
        mock_eq = mock_delete.eq.return_value
        mock_eq.execute.return_value.data = [{"id": "p1"}]
        
        res = delete_package("p1")
        
        assert res == [{"id": "p1"}]
        mock_table.delete.assert_called_once()
        mock_delete.eq.assert_called_once_with("id", "p1")

"""
Unit tests for app.crud.crud_class.

Target: app.crud.crud_class

Skenario:
1. Happy path: Mendapatkan semua kelas (public/admin), mendapatkan by id/ids, create, update, delete.
2. Filter Logic: Verifikasi filter batch_id (active batch injection).
3. Behavioral Verification: Memastikan query supabase terpanggil dengan parameter yang tepat.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.crud.crud_class import (
    get_public_classes,
    get_all_classes,
    get_class_by_id,
    get_classes_by_ids,
    create_class,
    update_class,
    delete_class,
)

class TestCrudClass:
    
    @pytest.fixture
    def mock_active_batch(self):
        """Mock fungsi get_active_batch_id_cached dari crud_class"""
        with patch("app.crud.crud_class.get_active_batch_id_cached") as mock_get_batch:
            mock_get_batch.return_value = "b1"
            yield mock_get_batch

    # ═══════════════════════════════════════════
    # Happy Path & Filter Logic
    # ═══════════════════════════════════════════

    def test_get_public_classes_with_active_batch(self, mock_supabase, mock_active_batch):
        """Memastikan get_public_classes mengambil kelas public dengan filter batch aktif."""
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq1 = mock_select.eq.return_value
        mock_order = mock_eq1.order.return_value
        mock_eq2 = mock_order.eq.return_value
        
        mock_eq2.execute.return_value.data = [
            {"id": "c1", "title": "Class 1", "visible": True, "batch_id": "b1"}
        ]
        
        classes = get_public_classes()
        
        assert len(classes) == 1
        assert classes[0]["id"] == "c1"
        
        # Behavioral Verification
        mock_active_batch.assert_called_once()
        mock_supabase.table.assert_called_once_with("classes")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("visible", True)
        mock_eq1.order.assert_called_once_with("created_at", desc=True)
        mock_order.eq.assert_called_once_with("batch_id", "b1")

    @pytest.mark.parametrize(
        "batch_id_arg, expected_batch_filter",
        [
            (None, "b1"),       # b1 is from mock_active_batch
            ("all", None),      # "all" should skip batch_id filter
            ("b2", "b2"),       # specific batch_id
        ],
        ids=["default_active_batch", "all_batches", "specific_batch"]
    )
    def test_get_all_classes_filters(self, mock_supabase, mock_active_batch, batch_id_arg, expected_batch_filter):
        """Memastikan filter batch_id bekerja dengan benar pada get_all_classes."""
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_order = mock_select.order.return_value
        
        # Depending on whether there is an eq filter after order
        if expected_batch_filter:
            mock_eq = mock_order.eq.return_value
            mock_eq.execute.return_value.data = [{"id": "c1"}, {"id": "c2"}]
        else:
            mock_order.execute.return_value.data = [{"id": "c1"}, {"id": "c2"}]
            
        classes = get_all_classes(batch_id=batch_id_arg)
        
        assert len(classes) == 2
        mock_supabase.table.assert_called_once_with("classes")
        mock_table.select.assert_called_once_with("*")
        mock_select.order.assert_called_once_with("created_at", desc=True)
        
        if expected_batch_filter:
            mock_order.eq.assert_called_once_with("batch_id", expected_batch_filter)
        else:
            # ensure eq is not called on the query object
            mock_order.eq.assert_not_called()

    def test_get_class_by_id(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_limit = mock_eq.limit.return_value
        mock_limit.execute.return_value.data = [{"id": "c1"}]
        
        cls = get_class_by_id("c1")
        
        assert cls is not None
        assert cls["id"] == "c1"
        mock_select.eq.assert_called_once_with("id", "c1")
        mock_eq.limit.assert_called_once_with(1)

    def test_get_classes_by_ids(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_in = mock_select.in_.return_value
        mock_in.execute.return_value.data = [{"id": "c1"}, {"id": "c2"}]
        
        cids = ["c1", "c2"]
        classes = get_classes_by_ids(cids)
        
        assert len(classes) == 2
        mock_select.in_.assert_called_once_with("id", cids)

    def test_get_classes_by_ids_empty(self, mock_supabase):
        """Jika list id kosong, langsung kembalikan list kosong tanpa query."""
        classes = get_classes_by_ids([])
        assert classes == []
        mock_supabase.table.assert_not_called()

    # ═══════════════════════════════════════════
    # Mutations (Create, Update, Delete)
    # ═══════════════════════════════════════════

    def test_create_class_injects_batch(self, mock_supabase, mock_active_batch):
        """Memastikan create_class menyuntikkan active_batch_id jika tidak diberikan."""
        mock_table = mock_supabase.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.data = [{"id": "new-class", "batch_id": "b1"}]
        
        cls = create_class({"title": "New"})
        
        assert cls["id"] == "new-class"
        mock_table.insert.assert_called_once_with({"title": "New", "batch_id": "b1"})

    def test_create_class_preserves_batch(self, mock_supabase, mock_active_batch):
        """Memastikan create_class TIDAK menimpa batch_id jika sudah ada di payload."""
        mock_table = mock_supabase.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.data = [{"id": "new-class", "batch_id": "custom-b"}]
        
        cls = create_class({"title": "New", "batch_id": "custom-b"})
        
        assert cls["id"] == "new-class"
        mock_table.insert.assert_called_once_with({"title": "New", "batch_id": "custom-b"})

    def test_update_class(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_update = mock_table.update.return_value
        mock_eq = mock_update.eq.return_value
        mock_eq.execute.return_value.data = [{"id": "c1", "title": "Updated"}]
        
        cls = update_class("c1", {"title": "Updated"})
        
        assert cls["id"] == "c1"
        mock_table.update.assert_called_once_with({"title": "Updated"})
        mock_update.eq.assert_called_once_with("id", "c1")
        
    def test_delete_class(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_delete = mock_table.delete.return_value
        mock_eq = mock_delete.eq.return_value
        mock_eq.execute.return_value.data = [{"id": "c1"}]
        
        res = delete_class("c1")
        
        assert res == [{"id": "c1"}]
        mock_table.delete.assert_called_once()
        mock_delete.eq.assert_called_once_with("id", "c1")

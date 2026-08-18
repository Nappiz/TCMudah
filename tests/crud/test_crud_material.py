"""
Unit tests for app.crud.crud_material.

Target: app.crud.crud_material

Skenario:
1. Happy path: Mendapatkan materials untuk admin dan user, mengecek enrollment, membuat, update, delete material.
2. Behavioral Verification: Menganalisa parameter pemanggilan CRUD dengan assert_called_once_with.
"""

import pytest
from unittest.mock import MagicMock

from app.crud.crud_material import (
    get_admin_materials,
    create_material,
    get_material_by_id,
    update_material,
    delete_material,
    get_user_materials,
    check_user_enrollment,
)

class TestCrudMaterial:

    # ═══════════════════════════════════════════
    # Happy Path & Filtering
    # ═══════════════════════════════════════════

    def test_get_admin_materials(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_order = mock_eq.order.return_value
        
        mock_order.execute.return_value.data = [{"id": "m1"}]
        
        res = get_admin_materials("c1")
        
        assert len(res) == 1
        mock_supabase.table.assert_called_once_with("class_materials")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("class_id", "c1")
        mock_eq.order.assert_called_once_with("created_at", desc=True)

    def test_get_user_materials(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq1 = mock_select.eq.return_value
        mock_eq2 = mock_eq1.eq.return_value
        mock_order = mock_eq2.order.return_value
        
        mock_order.execute.return_value.data = [{"id": "m1"}]
        
        res = get_user_materials("c1")
        
        assert len(res) == 1
        mock_supabase.table.assert_called_once_with("class_materials")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("class_id", "c1")
        mock_eq1.eq.assert_called_once_with("visible", True)
        mock_eq2.order.assert_called_once_with("created_at", desc=True)

    @pytest.mark.parametrize(
        "mock_db_return, expected_result",
        [
            ([{"id": "enr1"}], True),
            ([], False)
        ],
        ids=["enrolled", "not_enrolled"]
    )
    def test_check_user_enrollment(self, mock_supabase, mock_db_return, expected_result):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq1 = mock_select.eq.return_value
        mock_eq2 = mock_eq1.eq.return_value
        mock_eq3 = mock_eq2.eq.return_value
        mock_limit = mock_eq3.limit.return_value
        
        mock_limit.execute.return_value.data = mock_db_return
        
        res = check_user_enrollment("user1", "c1")
        
        assert res is expected_result
        mock_supabase.table.assert_called_once_with("enrollments")
        mock_table.select.assert_called_once_with("id")
        mock_select.eq.assert_called_once_with("user_id", "user1")
        mock_eq1.eq.assert_called_once_with("class_id", "c1")
        mock_eq2.eq.assert_called_once_with("active", True)
        mock_eq3.limit.assert_called_once_with(1)

    # ═══════════════════════════════════════════
    # Mutations (Create, Update, Delete)
    # ═══════════════════════════════════════════

    def test_create_material(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.data = [{"id": "new-mat"}]
        
        res = create_material({"title": "Mat 1"})
        
        assert res["id"] == "new-mat"
        mock_supabase.table.assert_called_once_with("class_materials")
        mock_table.insert.assert_called_once_with({"title": "Mat 1"})

    def test_get_material_by_id(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_limit = mock_eq.limit.return_value
        
        mock_limit.execute.return_value.data = [{"id": "m1"}]
        
        res = get_material_by_id("m1")
        
        assert res["id"] == "m1"
        mock_supabase.table.assert_called_once_with("class_materials")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("id", "m1")
        mock_eq.limit.assert_called_once_with(1)

    def test_update_material(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_update = mock_table.update.return_value
        mock_eq = mock_update.eq.return_value
        
        mock_eq.execute.return_value.data = [{"id": "m1"}]
        
        res = update_material("m1", {"title": "Updated"})
        
        assert res["id"] == "m1"
        mock_supabase.table.assert_called_once_with("class_materials")
        mock_table.update.assert_called_once_with({"title": "Updated"})
        mock_update.eq.assert_called_once_with("id", "m1")

    def test_delete_material(self, mock_supabase):
        mock_table = mock_supabase.table.return_value
        mock_delete = mock_table.delete.return_value
        mock_eq = mock_delete.eq.return_value
        
        mock_eq.execute.return_value.data = [{"id": "m1"}]
        
        res = delete_material("m1")
        
        assert res == [{"id": "m1"}]
        mock_supabase.table.assert_called_once_with("class_materials")
        mock_table.delete.assert_called_once()
        mock_delete.eq.assert_called_once_with("id", "m1")

"""
Unit tests for app.crud.crud_batch.

Target: app.crud.crud_batch

Skenario:
1. Happy path: Mendapatkan semua batch, batch aktif, membuat batch (aktif/tidak), update, delete.
2. Filter Logic: Verifikasi efek pembuatan batch aktif (deaktivasi batch lain).
3. Caching: Memastikan caching `get_active_batch_id_cached` bekerja dengan baik.
4. Behavioral Verification: Memastikan method mock dipanggil dengan argumen yang tepat.
"""

import pytest
from unittest.mock import MagicMock, call
import time

from app.crud.crud_batch import (
    get_all_batches,
    get_active_batch,
    create_batch,
    update_batch,
    delete_batch,
    get_active_batch_id_cached,
    invalidate_active_batch_cache,
    CACHE_TTL
)

class TestCrudBatch:
    
    @pytest.fixture(autouse=True)
    def setup_cache(self):
        """Reset cache state before each test."""
        invalidate_active_batch_cache()
        yield
        invalidate_active_batch_cache()

    # ═══════════════════════════════════════════
    # Happy Path
    # ═══════════════════════════════════════════

    def test_get_all_batches_success(self, mock_supabase):
        """Memastikan get_all_batches mengembalikan list of batches dan dieksekusi dengan query yang benar."""
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_order = mock_select.order.return_value
        
        mock_order.execute.return_value.data = [
            {"id": "b1", "name": "Batch 1", "is_active": True},
            {"id": "b2", "name": "Batch 2", "is_active": False},
        ]

        result = get_all_batches()

        assert len(result) == 2
        assert result[0]["id"] == "b1"
        
        # Behavioral Verification
        mock_supabase.table.assert_called_once_with("batches")
        mock_table.select.assert_called_once_with("*")
        mock_select.order.assert_called_once_with("created_at", desc=True)
        mock_order.execute.assert_called_once()

    def test_get_active_batch_success(self, mock_supabase):
        """Memastikan get_active_batch mengembalikan batch yang sedang aktif."""
        mock_table = mock_supabase.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_order = mock_eq.order.return_value
        mock_limit = mock_order.limit.return_value
        
        mock_limit.execute.return_value.data = [
            {"id": "b1", "name": "Batch 1", "is_active": True}
        ]

        result = get_active_batch()

        assert result is not None
        assert result["id"] == "b1"
        
        # Behavioral Verification
        mock_supabase.table.assert_called_once_with("batches")
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("is_active", True)
        mock_eq.order.assert_called_once_with("created_at", desc=True)
        mock_order.limit.assert_called_once_with(1)

    # ═══════════════════════════════════════════
    # Negative Path & Edge Cases
    # ═══════════════════════════════════════════

    def test_get_active_batch_not_found(self, mock_supabase):
        """Memastikan mengembalikan None jika tidak ada batch aktif."""
        mock_supabase.table().select().eq().order().limit().execute.return_value.data = []
        result = get_active_batch()
        assert result is None

    # ═══════════════════════════════════════════
    # Logical & Filter Verification (Create/Update)
    # ═══════════════════════════════════════════

    @pytest.mark.parametrize(
        "is_active, expected_deactivate_calls",
        [
            (True, 1),
            (False, 0),
        ],
        ids=["create_active_deactivates_others", "create_inactive_does_not_deactivate"]
    )
    def test_create_batch_logic(self, mock_supabase, is_active, expected_deactivate_calls):
        """Memastikan jika is_active=True, maka melakukan update batch lain menjadi False."""
        mock_table = mock_supabase.table.return_value
        
        # Setup insert mock
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.data = [{"id": "new-batch", "name": "New", "is_active": is_active}]
        
        # Setup update mock (for deactivation)
        mock_update = mock_table.update.return_value
        mock_neq = mock_update.neq.return_value
        
        new_data = {"name": "New", "is_active": is_active}
        result = create_batch(new_data)
        
        assert result["id"] == "new-batch"
        
        # Verify insert
        mock_table.insert.assert_called_once_with(new_data)
        
        # Verify conditional deactivation
        if expected_deactivate_calls > 0:
            mock_table.update.assert_called_once_with({"is_active": False})
            mock_update.neq.assert_called_once_with("id", "00000000-0000-0000-0000-000000000000")
            mock_neq.execute.assert_called_once()
        else:
            mock_table.update.assert_not_called()

    def test_update_batch_deactivates_others(self, mock_supabase):
        """Jika update is_active=True, batch lain harus dinonaktifkan selain bid yang sedang diupdate."""
        mock_table = mock_supabase.table.return_value
        
        # Mock for updating the actual batch
        mock_update = mock_table.update.return_value
        mock_eq = mock_update.eq.return_value
        mock_eq.execute.return_value.data = [{"id": "b1", "name": "Updated", "is_active": True}]
        
        # Mock for deactivating others (using neq)
        mock_neq = mock_update.neq.return_value
        
        update_data = {"name": "Updated", "is_active": True}
        result = update_batch("b1", update_data)
        
        assert result["id"] == "b1"
        
        # Behavioral Verification
        assert mock_table.update.call_count == 2
        # First update call: deactivate others
        assert call({"is_active": False}) in mock_table.update.mock_calls
        mock_update.neq.assert_called_once_with("id", "b1")
        # Second update call: update actual batch
        assert call(update_data) in mock_table.update.mock_calls
        mock_update.eq.assert_called_once_with("id", "b1")

    def test_delete_batch(self, mock_supabase):
        """Memastikan delete dipanggil dengan parameter yang benar."""
        mock_table = mock_supabase.table.return_value
        mock_delete = mock_table.delete.return_value
        mock_eq = mock_delete.eq.return_value
        mock_eq.execute.return_value.data = [{"id": "b1"}]

        result = delete_batch("b1")

        assert result == [{"id": "b1"}]
        mock_supabase.table.assert_called_once_with("batches")
        mock_table.delete.assert_called_once()
        mock_delete.eq.assert_called_once_with("id", "b1")
        mock_eq.execute.assert_called_once()

    # ═══════════════════════════════════════════
    # Caching Mechanism
    # ═══════════════════════════════════════════

    def test_get_active_batch_id_cached_mechanism(self, mock_supabase, mocker):
        """Memastikan cache tidak melakukan query ke db jika belum expire."""
        # Mock time untuk mengontrol umur cache
        mock_time = mocker.patch("app.crud.crud_batch.time.time")
        mock_time.return_value = 1000.0
        
        mock_limit = mock_supabase.table().select().eq().order().limit()
        mock_limit.execute.return_value.data = [{"id": "b1"}]
        
        # Call 1: Miss (queries DB)
        bid = get_active_batch_id_cached()
        assert bid == "b1"
        assert mock_limit.execute.call_count == 1
        
        # Call 2: Hit (time + 10s < 60s TTL), no DB query
        mock_time.return_value = 1010.0
        bid2 = get_active_batch_id_cached()
        assert bid2 == "b1"
        assert mock_limit.execute.call_count == 1
        
        # Call 3: Expired (time + 61s > 60s TTL), queries DB again
        mock_time.return_value = 1061.0
        bid3 = get_active_batch_id_cached()
        assert bid3 == "b1"
        assert mock_limit.execute.call_count == 2

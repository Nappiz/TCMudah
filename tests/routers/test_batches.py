"""
Unit tests for app.routers.batches.

Target: app.routers.batches

Skenario:
1. Happy path: Mendapatkan semua batch, batch aktif, create, update, delete batch dengan auth yang sesuai.
2. Negative Path: Batch tidak ditemukan (404), error saat create/update/delete.
3. Authorization (Role Based):
   - Admin/Superadmin bisa create, update.
   - Superadmin bisa delete.
   - User biasa akan ditolak (403 Forbidden).
"""

import pytest
from unittest.mock import MagicMock, patch

class TestBatchesRouter:
    
    @pytest.fixture
    def mock_crud(self):
        """
        Fixture untuk melakukan mocking terpusat pada crud_batch
        yang digunakan oleh router batches.
        """
        with patch("app.routers.batches.crud_batch") as mock_crud:
            yield mock_crud

    # ═══════════════════════════════════════════
    # Happy Path - Public / Unauthenticated
    # ═══════════════════════════════════════════

    def test_get_batches(self, test_client, mock_crud):
        """Mendapatkan daftar semua batch."""
        mock_crud.get_all_batches.return_value = [{"id": "b1", "name": "B1", "is_active": True}]
        
        response = test_client.get("/batches")
        
        assert response.status_code == 200
        assert response.json()[0]["name"] == "B1"
        mock_crud.get_all_batches.assert_called_once()

    def test_get_active_batch(self, test_client, mock_crud):
        """Mendapatkan batch yang aktif."""
        mock_crud.get_active_batch.return_value = {"id": "b1", "name": "Active", "is_active": True}
        
        response = test_client.get("/batches/active")
        
        assert response.status_code == 200
        assert response.json()["name"] == "Active"
        mock_crud.get_active_batch.assert_called_once()

    # ═══════════════════════════════════════════
    # Negative Path - Not Found
    # ═══════════════════════════════════════════

    def test_get_active_batch_not_found(self, test_client, mock_crud):
        """Mendapatkan 404 jika tidak ada batch aktif."""
        mock_crud.get_active_batch.return_value = None
        
        response = test_client.get("/batches/active")
        
        assert response.status_code == 404
        mock_crud.get_active_batch.assert_called_once()

    def test_delete_batch_not_found(self, auth_client_superadmin, mock_crud):
        """Mendapatkan 404 saat menghapus batch yang tidak ada."""
        mock_crud.delete_batch.return_value = None
        
        response = auth_client_superadmin.delete("/admin/batches/b1")
        
        assert response.status_code == 404
        mock_crud.delete_batch.assert_called_once_with("b1")

    # ═══════════════════════════════════════════
    # Authorization & Roles (Parametrized)
    # ═══════════════════════════════════════════

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ],
        ids=["create_admin_success", "create_superadmin_success", "create_user_forbidden"]
    )
    def test_create_batch_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses pembuatan batch berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.create_batch.return_value = {"id": "new-batch", "name": "New", "is_active": True}
        
        payload = {"name": "New", "is_active": True}
        response = client.post("/admin/batches", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.json()["id"] == "new-batch"
            mock_crud.create_batch.assert_called_once()
        else:
            mock_crud.create_batch.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ],
        ids=["update_admin_success", "update_superadmin_success", "update_user_forbidden"]
    )
    def test_update_batch_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses update batch berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.update_batch.return_value = {"id": "b1", "name": "Updated", "is_active": True}
        
        payload = {"name": "Updated"}
        response = client.patch("/admin/batches/b1", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.update_batch.assert_called_once()
        else:
            mock_crud.update_batch.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_superadmin", 200),
            ("auth_client_admin", 403),
            ("auth_client_user", 403),
        ],
        ids=["delete_superadmin_success", "delete_admin_forbidden", "delete_user_forbidden"]
    )
    def test_delete_batch_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses delete batch (Hanya superadmin)."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.delete_batch.return_value = [{"id": "b1"}]
        
        response = client.delete("/admin/batches/b1")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.json() == {"ok": True}
            mock_crud.delete_batch.assert_called_once_with("b1")
        else:
            mock_crud.delete_batch.assert_not_called()

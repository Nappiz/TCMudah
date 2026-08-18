"""
Unit tests for app.routers.materials.

Target: app.routers.materials

Skenario:
1. Happy path: Mendapatkan semua materials admin, create, update, delete.
2. Authorization: Hanya admin/superadmin yang bisa mengelola data material.
"""

import pytest
from unittest.mock import patch

class TestMaterialsRouter:
    
    @pytest.fixture
    def mock_crud(self):
        """Fixture untuk melakukan mocking terpusat pada crud_material."""
        with patch("app.routers.materials.crud_material") as mock_crud:
            yield mock_crud

    # ═══════════════════════════════════════════
    # Happy Path & Authorization (Parametrized)
    # ═══════════════════════════════════════════

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_get_admin_materials_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses read-all berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.get_admin_materials.return_value = [{"id": "m1", "class_id": "c1", "title": "M1", "url": "url", "visible": True, "type": "video"}]
        
        response = client.get("/admin/materials?class_id=c1")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.get_admin_materials.assert_called_once_with("c1")
        else:
            mock_crud.get_admin_materials.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_create_material_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses create berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.create_material.return_value = {"id": "m2", "class_id": "c1", "title": "M2", "url": "url", "visible": True, "type": "video"}
        
        payload = {"title": "M2", "class_id": "c1", "type": "video", "url": "url"}
        response = client.post("/admin/materials", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.create_material.assert_called_once()
        else:
            mock_crud.create_material.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_update_material_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses update berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.update_material.return_value = {"id": "m1", "class_id": "c1", "title": "Updated", "url": "url", "visible": True, "type": "video"}
        
        payload = {"title": "Updated"}
        response = client.patch("/admin/materials/m1", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.update_material.assert_called_once_with("m1", payload)
        else:
            mock_crud.update_material.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_delete_material_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses delete berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.delete_material.return_value = [{"id": "m1"}]
        
        response = client.delete("/admin/materials/m1")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.json() == {"ok": True}
            mock_crud.delete_material.assert_called_once_with("m1")
        else:
            mock_crud.delete_material.assert_not_called()

    # ═══════════════════════════════════════════
    # Negative Path (404)
    # ═══════════════════════════════════════════

    def test_delete_material_not_found(self, auth_client_admin, mock_crud):
        """Menguji behaviour jika menghapus material yang tidak ada."""
        mock_crud.delete_material.return_value = None
        response = auth_client_admin.delete("/admin/materials/m1")
        assert response.status_code == 404
        mock_crud.delete_material.assert_called_once_with("m1")

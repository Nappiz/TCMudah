"""
Unit tests for app.routers.packages.

Target: app.routers.packages

Skenario:
1. Happy path: Mendapatkan semua package, membuat, mengupdate, menghapus.
2. Authorization: Hanya admin/superadmin yang bisa mengelola data paket.
"""

import pytest
from unittest.mock import patch

class TestPackagesRouter:
    
    @pytest.fixture
    def mock_crud(self):
        """Fixture untuk melakukan mocking terpusat pada crud_package."""
        with patch("app.routers.packages.crud_package") as mock_crud:
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
    def test_get_all_packages_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses read-all berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.get_all_packages.return_value = [{"id": "p1", "title": "P1", "description": "Desc", "class_ids": ["c1"], "price": 100, "visible": True}]
        
        response = client.get("/admin/packages")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.get_all_packages.assert_called_once()
        else:
            mock_crud.get_all_packages.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_create_package_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses create berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.create_package.return_value = {"id": "p2", "title": "P2", "description": "Desc", "class_ids": ["c1"], "price": 100, "visible": True}
        
        payload = {"title": "P2", "description": "desc", "class_ids": ["c1"], "price": 100}
        response = client.post("/admin/packages", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.create_package.assert_called_once()
        else:
            mock_crud.create_package.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_update_package_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses update berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.update_package.return_value = {"id": "p1", "title": "Updated", "description": "Desc", "class_ids": ["c1"], "price": 100, "visible": True}
        
        payload = {"title": "Updated"}
        response = client.patch("/admin/packages/p1", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.update_package.assert_called_once_with("p1", payload)
        else:
            mock_crud.update_package.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_delete_package_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses delete berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.delete_package.return_value = [{"id": "p1"}]
        
        response = client.delete("/admin/packages/p1")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.json() == {"ok": True}
            mock_crud.delete_package.assert_called_once_with("p1")
        else:
            mock_crud.delete_package.assert_not_called()

    # ═══════════════════════════════════════════
    # Negative Path (404)
    # ═══════════════════════════════════════════

    def test_delete_package_not_found(self, auth_client_admin, mock_crud):
        """Menguji behaviour jika menghapus package yang tidak ada."""
        mock_crud.delete_package.return_value = None
        response = auth_client_admin.delete("/admin/packages/p1")
        assert response.status_code == 404
        mock_crud.delete_package.assert_called_once_with("p1")

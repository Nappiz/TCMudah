"""
Unit tests for app.routers.classes.

Target: app.routers.classes

Skenario:
1. Happy path: Mendapatkan semua kelas, membuat, mengupdate, menghapus.
2. Authorization: Hanya admin/superadmin yang bisa mengelola (CRUD) data kelas.
3. Behavioral Verification: Menganalisa parameter pemanggilan CRUD.
"""

import pytest
from unittest.mock import patch

class TestClassesRouter:
    
    @pytest.fixture
    def mock_crud(self):
        """Fixture untuk melakukan mocking terpusat pada crud_class."""
        with patch("app.routers.classes.crud_class") as mock_crud:
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
    def test_get_all_classes_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses read-all berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.get_all_classes.return_value = [{"id": "c1", "title": "C1", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 0, "visible": True}]
        
        response = client.get("/admin/classes")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.get_all_classes.assert_called_once()
        else:
            mock_crud.get_all_classes.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_create_class_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses create berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.create_class.return_value = {"id": "c2", "title": "C2", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 100, "visible": True}
        
        payload = {"title": "C2", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 100}
        response = client.post("/admin/classes", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.create_class.assert_called_once()
        else:
            mock_crud.create_class.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_update_class_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses update berdasarkan role."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.update_class.return_value = {"id": "c1", "title": "Updated", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 0, "visible": True}
        
        payload = {"title": "Updated"}
        response = client.patch("/admin/classes/c1", json=payload)
        
        assert response.status_code == expected_status
        if expected_status == 200:
            mock_crud.update_class.assert_called_once_with("c1", payload)
        else:
            mock_crud.update_class.assert_not_called()

    @pytest.mark.parametrize(
        "client_fixture, expected_status",
        [
            ("auth_client_admin", 200),
            ("auth_client_superadmin", 200),
            ("auth_client_user", 403),
        ]
    )
    def test_delete_class_authorization(self, request, client_fixture, expected_status, mock_crud):
        """Menguji akses delete berdasarkan role (admin/superadmin)."""
        client = request.getfixturevalue(client_fixture)
        mock_crud.delete_class.return_value = [{"id": "c1"}]
        
        response = client.delete("/admin/classes/c1")
        
        assert response.status_code == expected_status
        if expected_status == 200:
            assert response.json() == {"ok": True}
            mock_crud.delete_class.assert_called_once_with("c1")
        else:
            mock_crud.delete_class.assert_not_called()

    # ═══════════════════════════════════════════
    # Negative Path (404)
    # ═══════════════════════════════════════════

    def test_delete_class_not_found(self, auth_client_admin, mock_crud):
        """Menguji behaviour jika menghapus class yang tidak ada."""
        mock_crud.delete_class.return_value = None
        response = auth_client_admin.delete("/admin/classes/c1")
        assert response.status_code == 404
        mock_crud.delete_class.assert_called_once_with("c1")

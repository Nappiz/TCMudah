from unittest.mock import patch

def test_get_all_packages_admin(auth_client_admin):
    with patch("app.routers.packages.crud_package.get_all_packages") as mock_get_all:
        mock_get_all.return_value = [{"id": "p1", "title": "P1", "description": "Desc", "class_ids": ["c1"], "price": 100, "visible": True}]
        
        response = auth_client_admin.get("/admin/packages")
        assert response.status_code == 200

def test_create_package_admin(auth_client_admin):
    with patch("app.routers.packages.crud_package.create_package") as mock_create:
        mock_create.return_value = {"id": "p2", "title": "P2", "description": "Desc", "class_ids": ["c1"], "price": 100, "visible": True}
        
        payload = {"title": "P2", "description": "desc", "class_ids": ["c1"], "price": 100}
        response = auth_client_admin.post("/admin/packages", json=payload)
        assert response.status_code == 200

def test_update_package_admin(auth_client_admin):
    with patch("app.routers.packages.crud_package.update_package") as mock_update:
        with patch("app.routers.packages.crud_package.get_package_by_id") as mock_get:
            mock_update.return_value = {"id": "p1", "title": "Updated", "description": "Desc", "class_ids": ["c1"], "price": 100, "visible": True}
            
            payload = {"title": "Updated"}
            response = auth_client_admin.patch("/admin/packages/p1", json=payload)
            assert response.status_code == 200

def test_delete_package_admin(auth_client_admin):
    with patch("app.routers.packages.crud_package.delete_package") as mock_delete:
        mock_delete.return_value = [{"id": "p1"}]
        
        response = auth_client_admin.delete("/admin/packages/p1")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

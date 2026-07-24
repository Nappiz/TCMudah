from unittest.mock import patch

def test_get_admin_materials(auth_client_admin):
    with patch("app.routers.materials.crud_material.get_admin_materials") as mock_get:
        mock_get.return_value = [{"id": "m1", "class_id": "c1", "title": "M1", "url": "url", "visible": True, "type": "video"}]
        
        response = auth_client_admin.get("/admin/materials?class_id=c1")
        assert response.status_code == 200

def test_create_material_admin(auth_client_admin):
    with patch("app.routers.materials.crud_material.create_material") as mock_create:
        mock_create.return_value = {"id": "m2", "class_id": "c1", "title": "M2", "url": "url", "visible": True, "type": "video"}
        
        payload = {"title": "M2", "class_id": "c1", "type": "video", "url": "url"}
        response = auth_client_admin.post("/admin/materials", json=payload)
        assert response.status_code == 200

def test_update_material_admin(auth_client_admin):
    with patch("app.routers.materials.crud_material.update_material") as mock_update:
        mock_update.return_value = {"id": "m1", "class_id": "c1", "title": "Updated", "url": "url", "visible": True, "type": "video"}
        
        payload = {"title": "Updated"}
        response = auth_client_admin.patch("/admin/materials/m1", json=payload)
        assert response.status_code == 200

def test_delete_material_admin(auth_client_admin):
    with patch("app.routers.materials.crud_material.delete_material") as mock_delete:
        mock_delete.return_value = [{"id": "m1"}]
        
        response = auth_client_admin.delete("/admin/materials/m1")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

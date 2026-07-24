from unittest.mock import patch

def test_get_all_classes_admin(auth_client_admin):
    with patch("app.routers.classes.crud_class.get_all_classes") as mock_get_all:
        mock_get_all.return_value = [{"id": "c1", "title": "C1", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 0, "visible": True}]
        
        response = auth_client_admin.get("/admin/classes")
        assert response.status_code == 200

def test_create_class_admin(auth_client_admin):
    with patch("app.routers.classes.crud_class.create_class") as mock_create:
        mock_create.return_value = {"id": "c2", "title": "C2", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 100, "visible": True}
        
        payload = {"title": "C2", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 100}
        response = auth_client_admin.post("/admin/classes", json=payload)
        assert response.status_code == 200

def test_update_class_admin(auth_client_admin):
    with patch("app.routers.classes.crud_class.update_class") as mock_update:
        mock_update.return_value = {"id": "c1", "title": "Updated", "description": "Desc", "mentor_ids": ["m1"], "curriculum_ids": ["c1"], "price": 0, "visible": True}
        
        payload = {"title": "Updated"}
        response = auth_client_admin.patch("/admin/classes/c1", json=payload)
        assert response.status_code == 200

def test_delete_class_admin(auth_client_admin):
    with patch("app.routers.classes.crud_class.delete_class") as mock_delete:
        mock_delete.return_value = [{"id": "c1"}]
        
        response = auth_client_admin.delete("/admin/classes/c1")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

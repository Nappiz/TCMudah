from unittest.mock import patch

def test_get_batches(test_client):
    with patch("app.routers.batches.crud_batch.get_all_batches") as mock_get_all:
        mock_get_all.return_value = [{"id": "b1", "name": "B1", "is_active": True}]
        
        response = test_client.get("/batches")
        assert response.status_code == 200
        assert response.json()[0]["name"] == "B1"

def test_get_active_batch(test_client):
    with patch("app.routers.batches.crud_batch.get_active_batch") as mock_get_active:
        mock_get_active.return_value = {"id": "b1", "name": "Active", "is_active": True}
        
        response = test_client.get("/batches/active")
        assert response.status_code == 200
        assert response.json()["name"] == "Active"

def test_get_active_batch_not_found(test_client):
    with patch("app.routers.batches.crud_batch.get_active_batch") as mock_get_active:
        mock_get_active.return_value = None
        
        response = test_client.get("/batches/active")
        assert response.status_code == 404

def test_create_batch_admin(auth_client_admin):
    with patch("app.routers.batches.crud_batch.create_batch") as mock_create:
        mock_create.return_value = {"id": "new-batch", "name": "New", "is_active": True}
        
        payload = {"name": "New", "is_active": True}
        response = auth_client_admin.post("/admin/batches", json=payload)
        
        assert response.status_code == 200
        assert response.json()["id"] == "new-batch"
        
def test_create_batch_normal_user(auth_client_user):
    payload = {"name": "New", "is_active": True}
    response = auth_client_user.post("/admin/batches", json=payload)
    assert response.status_code == 403

def test_update_batch_admin(auth_client_admin):
    with patch("app.routers.batches.crud_batch.update_batch") as mock_update:
        mock_update.return_value = {"id": "b1", "name": "Updated", "is_active": True}
        
        payload = {"name": "Updated"}
        response = auth_client_admin.patch("/admin/batches/b1", json=payload)
        assert response.status_code == 200

def test_delete_batch_admin(auth_client_superadmin):
    with patch("app.routers.batches.crud_batch.delete_batch") as mock_delete:
        mock_delete.return_value = [{"id": "b1"}]
        
        response = auth_client_superadmin.delete("/admin/batches/b1")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

def test_delete_batch_admin_not_found(auth_client_superadmin):
    with patch("app.routers.batches.crud_batch.delete_batch") as mock_delete:
        mock_delete.return_value = None
        response = auth_client_superadmin.delete("/admin/batches/b1")
        assert response.status_code == 404

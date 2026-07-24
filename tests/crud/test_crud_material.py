from app.crud.crud_material import (
    get_admin_materials,
    create_material,
    get_material_by_id,
    update_material,
    delete_material,
    get_user_materials,
    check_user_enrollment,
)

def test_get_admin_materials(mock_supabase):
    mock_supabase.table().select().eq().order().execute.return_value.data = [{"id": "m1"}]
    res = get_admin_materials("c1")
    assert len(res) == 1
    mock_supabase.table().select().eq.assert_called_with("class_id", "c1")

def test_create_material(mock_supabase):
    mock_supabase.table().insert().execute.return_value.data = [{"id": "new-mat"}]
    res = create_material({"title": "Mat 1"})
    assert res["id"] == "new-mat"

def test_get_material_by_id(mock_supabase):
    mock_supabase.table().select().eq().limit().execute.return_value.data = [{"id": "m1"}]
    res = get_material_by_id("m1")
    assert res["id"] == "m1"

def test_update_material(mock_supabase):
    mock_supabase.table().update().eq().execute.return_value.data = [{"id": "m1"}]
    res = update_material("m1", {"title": "Updated"})
    assert res["id"] == "m1"

def test_delete_material(mock_supabase):
    mock_supabase.table().delete().eq().execute.return_value.data = [{"id": "m1"}]
    res = delete_material("m1")
    assert res == [{"id": "m1"}]

def test_get_user_materials(mock_supabase):
    mock_supabase.table().select().eq().eq().order().execute.return_value.data = [{"id": "m1"}]
    res = get_user_materials("c1")
    assert len(res) == 1
    mock_supabase.table().select().eq().eq.assert_called_with("visible", True)

def test_check_user_enrollment(mock_supabase):
    mock_supabase.table().select().eq().eq().eq().limit().execute.return_value.data = [{"id": "enr1"}]
    res = check_user_enrollment("user1", "c1")
    assert res is True
    
def test_check_user_enrollment_false(mock_supabase):
    mock_supabase.table().select().eq().eq().eq().limit().execute.return_value.data = []
    res = check_user_enrollment("user1", "c1")
    assert res is False

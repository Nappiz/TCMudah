from app.crud.crud_package import (
    get_public_packages,
    get_all_packages,
    get_package_by_id,
    create_package,
    update_package,
    delete_package,
)

def test_get_public_packages(mock_supabase):
    # Mock active batch ID retrieval
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [{"id": "b1"}]
    # Mock packages retrieval
    mock_supabase.table().select().eq().order().eq().execute.return_value.data = [
        {"id": "p1", "title": "Package 1", "visible": True, "batch_id": "b1"}
    ]
    
    packages = get_public_packages()
    assert len(packages) == 1
    assert packages[0]["id"] == "p1"

def test_get_all_packages(mock_supabase):
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [{"id": "b1"}]
    mock_supabase.table().select().order().eq().execute.return_value.data = [
        {"id": "p1"}, {"id": "p2"}
    ]
    
    packages = get_all_packages()
    assert len(packages) == 2

def test_create_package(mock_supabase):
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [{"id": "b1"}]
    mock_supabase.table().insert().execute.return_value.data = [{"id": "new-package"}]
    
    pkg = create_package({"title": "New Pkg"})
    assert pkg["id"] == "new-package"
    mock_supabase.table().insert.assert_called_with({"title": "New Pkg", "batch_id": "b1"})

def test_update_package(mock_supabase):
    mock_supabase.table().update().eq().execute.return_value.data = [{"id": "p1"}]
    pkg = update_package("p1", {"title": "Updated Pkg"})
    assert pkg["id"] == "p1"
    
def test_delete_package(mock_supabase):
    mock_supabase.table().delete().eq().execute.return_value.data = [{"id": "p1"}]
    res = delete_package("p1")
    assert res == [{"id": "p1"}]

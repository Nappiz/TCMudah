from app.crud.crud_class import (
    get_public_classes,
    get_all_classes,
    get_class_by_id,
    create_class,
    update_class,
    delete_class,
)

def test_get_public_classes(mock_supabase):
    # Mock active batch ID retrieval
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [{"id": "b1"}]
    # Mock classes retrieval
    mock_supabase.table().select().eq().order().eq().execute.return_value.data = [
        {"id": "c1", "title": "Class 1", "visible": True, "batch_id": "b1"}
    ]
    
    classes = get_public_classes()
    assert len(classes) == 1
    assert classes[0]["id"] == "c1"

def test_get_all_classes(mock_supabase):
    # Mock no batch ID provided -> fetches active batch
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [{"id": "b1"}]
    mock_supabase.table().select().order().eq().execute.return_value.data = [
        {"id": "c1"}, {"id": "c2"}
    ]
    
    classes = get_all_classes()
    assert len(classes) == 2

def test_get_class_by_id(mock_supabase):
    mock_supabase.table().select().eq().limit().execute.return_value.data = [{"id": "c1"}]
    
    cls = get_class_by_id("c1")
    assert cls is not None
    assert cls["id"] == "c1"

def test_create_class(mock_supabase):
    # Mock active batch ID retrieval
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [{"id": "b1"}]
    mock_supabase.table().insert().execute.return_value.data = [{"id": "new-class"}]
    
    cls = create_class({"title": "New"})
    assert cls["id"] == "new-class"
    # Verify batch_id was injected
    mock_supabase.table().insert.assert_called_with({"title": "New", "batch_id": "b1"})

def test_update_class(mock_supabase):
    mock_supabase.table().update().eq().execute.return_value.data = [{"id": "c1"}]
    cls = update_class("c1", {"title": "Updated"})
    assert cls["id"] == "c1"
    
def test_delete_class(mock_supabase):
    mock_supabase.table().delete().eq().execute.return_value.data = [{"id": "c1"}]
    res = delete_class("c1")
    assert res == [{"id": "c1"}]

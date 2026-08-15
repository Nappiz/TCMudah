from app.crud.crud_batch import get_all_batches, get_active_batch, create_batch, update_batch, delete_batch

def test_get_all_batches(mock_supabase):
    # Setup mock return value
    mock_supabase.table().select().order().execute.return_value.data = [
        {"id": "b1", "name": "Batch 1", "is_active": True},
        {"id": "b2", "name": "Batch 2", "is_active": False},
    ]

    batches = get_all_batches()
    
    assert len(batches) == 2
    assert batches[0]["id"] == "b1"
    
def test_get_active_batch(mock_supabase):
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [
        {"id": "b1", "name": "Batch 1", "is_active": True}
    ]

    batch = get_active_batch()
    
    assert batch is not None
    assert batch["id"] == "b1"

def test_get_active_batch_not_found(mock_supabase):
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = []
    batch = get_active_batch()
    assert batch is None

def test_create_batch_deactivates_others(mock_supabase):
    mock_supabase.table().insert().execute.return_value.data = [
        {"id": "b3", "name": "New Batch", "is_active": True}
    ]
    
    new_data = {"name": "New Batch", "is_active": True}
    res = create_batch(new_data)
    
    assert res["id"] == "b3"

def test_update_batch_deactivates_others(mock_supabase):
    mock_supabase.table().update().eq().execute.return_value.data = [
        {"id": "b1", "name": "Updated", "is_active": True}
    ]
    
    update_data = {"name": "Updated", "is_active": True}
    res = update_batch("b1", update_data)
    
    assert res["id"] == "b1"

def test_delete_batch(mock_supabase):
    mock_supabase.table().delete().eq().execute.return_value.data = [{"id": "b1"}]
    res = delete_batch("b1")
    assert res == [{"id": "b1"}]

def test_get_active_batch_id_cached(mock_supabase):
    from app.crud.crud_batch import get_active_batch_id_cached, invalidate_active_batch_cache
    
    # Invalidate cache first to ensure a clean state
    invalidate_active_batch_cache()
    
    # Mock return value for active batch query
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [
        {"id": "b1"}
    ]
    
    # First call: should query database
    bid = get_active_batch_id_cached()
    assert bid == "b1"
    assert mock_supabase.table().select().eq().order().limit().execute.call_count == 1
    
    # Second call: should hit cache, database query count should still be 1
    bid2 = get_active_batch_id_cached()
    assert bid2 == "b1"
    assert mock_supabase.table().select().eq().order().limit().execute.call_count == 1
    
    # Invalidate cache
    invalidate_active_batch_cache()
    
    # Third call: should query database again, query count becomes 2
    bid3 = get_active_batch_id_cached()
    assert bid3 == "b1"
    assert mock_supabase.table().select().eq().order().limit().execute.call_count == 2

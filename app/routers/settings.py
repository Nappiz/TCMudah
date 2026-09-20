from fastapi import APIRouter, Depends
from typing import List

from app.schemas import schemas
from app.core.deps import require_roles
from app.core.supabase_client import supabase

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/{key}", response_model=schemas.AppSettingOut)
def get_setting(key: str):
    sb = supabase()
    res = sb.table("app_settings").select("key,value").eq("key", key).limit(1).execute()
    
    if not res.data:
        return schemas.AppSettingOut(key=key, value="false")
        
    return res.data[0]

@router.put("/{key}", response_model=schemas.AppSettingOut, dependencies=[Depends(require_roles("superadmin", "admin"))])
def update_setting(key: str, payload: schemas.AppSettingUpdate):
    sb = supabase()
    
    # Check if exists
    res = sb.table("app_settings").select("key").eq("key", key).execute()
    if res.data:
        # Update
        updated = sb.table("app_settings").update({"value": payload.value}).eq("key", key).execute()
        return updated.data[0]
    else:
        # Insert
        inserted = sb.table("app_settings").insert({"key": key, "value": payload.value}).execute()
        return inserted.data[0]

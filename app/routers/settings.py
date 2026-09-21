from fastapi import APIRouter, Depends, Query
from typing import List

from app.schemas import schemas
from app.core.deps import require_roles
from app.core.supabase_client import supabase

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("")
def get_settings(keys: list[str] = Query(..., min_length=1, max_length=20)):
    normalized = list(dict.fromkeys(key.strip() for key in keys if key.strip()))
    if not normalized:
        return {}
    response = (
        supabase()
        .table("app_settings")
        .select("key,value")
        .in_("key", normalized)
        .execute()
    )
    return {row["key"]: row["value"] for row in (response.data or [])}

@router.get("/{key}", response_model=schemas.AppSettingOut)
def get_setting(key: str):
    sb = supabase()
    res = sb.table("app_settings").select("key,value").eq("key", key).limit(1).execute()
    
    if not res.data:
        return schemas.AppSettingOut(key=key, value="false")
        
    return res.data[0]

@router.put("/{key}", response_model=schemas.AppSettingOut, dependencies=[Depends(require_roles("superadmin", "admin"))])
def update_setting(key: str, payload: schemas.AppSettingUpdate):
    result = (
        supabase()
        .table("app_settings")
        .upsert({"key": key, "value": payload.value}, on_conflict="key")
        .execute()
    )
    return result.data[0]

from fastapi import APIRouter, Depends, Query

from app.schemas import schemas
from app.core.deps import require_roles
from app.core.supabase_client import supabase
from app.errors.exceptions import BadRequestError
from app.services.app_settings import (
    ADMIN_SETTING_KEYS,
    PUBLIC_SETTING_KEYS,
    effective_admin_values,
    effective_public_values,
    validate_setting_value,
)

router = APIRouter(prefix="/settings", tags=["settings"])
admin_router = APIRouter(prefix="/admin/settings", tags=["settings"])

@router.get("")
def get_settings(keys: list[str] = Query(..., min_length=1, max_length=20)):
    normalized = list(dict.fromkeys(key.strip() for key in keys if key.strip()))
    if not normalized:
        return {}
    if any(key not in PUBLIC_SETTING_KEYS for key in normalized):
        raise BadRequestError(detail="Setting tidak tersedia untuk publik")
    return effective_public_values(normalized)

@router.get("/{key}", response_model=schemas.AppSettingOut)
def get_setting(key: str):
    if key not in PUBLIC_SETTING_KEYS:
        raise BadRequestError(detail="Setting tidak tersedia untuk publik")
    return schemas.AppSettingOut(
        key=key,
        value=effective_public_values([key]).get(key, "false"),
    )

@router.put("/{key}", response_model=schemas.AppSettingOut, dependencies=[Depends(require_roles("superadmin", "admin"))])
def update_setting(key: str, payload: schemas.AppSettingUpdate):
    value = validate_setting_value(key, payload.value)
    result = (
        supabase()
        .table("app_settings")
        .upsert({"key": key, "value": value}, on_conflict="key")
        .execute()
    )
    return result.data[0]


@admin_router.get("", dependencies=[Depends(require_roles("superadmin", "admin"))])
def get_admin_settings(keys: list[str] = Query(..., min_length=1, max_length=20)):
    normalized = list(dict.fromkeys(key.strip() for key in keys if key.strip()))
    if not normalized:
        return {}
    if any(key not in ADMIN_SETTING_KEYS for key in normalized):
        raise BadRequestError(detail="Setting tidak tersedia")
    return effective_admin_values(normalized)

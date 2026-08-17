from fastapi import APIRouter, Depends
from app.errors.exceptions import ForbiddenError, NotFoundError

from app.schemas.schemas import UserOut, UpdateRoleIn
from app.core.deps import get_current_user, require_roles
from app.crud import crud_user

router = APIRouter(prefix="/admin/users", tags=["users"])

@router.get(
    "",
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_users(page: int = 1, limit: int = 20, search: str = "", role: str = "", current=Depends(get_current_user)):
    offset = (page - 1) * limit
    total, data = crud_user.get_paginated_users(limit=limit, offset=offset, search=search, role_filter=role)
    return {
        "total": total,
        "data": [
            {
                "id": u["id"],
                "email": u["email"],
                "full_name": u["full_name"],
                "nim": u.get("nim"),
                "role": u["role"],
            }
            for u in data
        ]
    }

@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_user_role(user_id: str, data: UpdateRoleIn, current=Depends(get_current_user)):
    if user_id == current["id"]:
        raise ForbiddenError(detail="Tidak boleh mengubah role akun sendiri")
        
    target = crud_user.get_user_by_id(user_id)
    if not target:
        raise NotFoundError(detail="User tidak ditemukan")
        
    if target["role"] == "superadmin" and current["role"] != "superadmin":
        raise ForbiddenError(detail="Tidak boleh mengubah akun superadmin")
    if data.role == "superadmin" and current["role"] != "superadmin":
        raise ForbiddenError(detail="Hanya superadmin yang dapat mengatur role superadmin")
        
    user = crud_user.update_user_role(user_id, data.role)
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

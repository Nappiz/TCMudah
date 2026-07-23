from fastapi import APIRouter, Depends, HTTPException
from app.schemas.schemas import UserOut, UpdateRoleIn
from app.core.deps import get_current_user, require_roles
from app.crud import crud_user

router = APIRouter(prefix="/admin/users", tags=["users"])

@router.get(
    "",
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_users(current=Depends(get_current_user)):
    data = crud_user.get_all_users()
    me_id = current["id"]
    top = [u for u in data if u["id"] == me_id]
    rest = [u for u in data if u["id"] != me_id]
    combined = top + rest
    return [
        {
            "id": u["id"],
            "email": u["email"],
            "full_name": u["full_name"],
            "nim": u.get("nim"),
            "role": u["role"],
        }
        for u in combined
    ]

@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_user_role(user_id: str, data: UpdateRoleIn, current=Depends(get_current_user)):
    if user_id == current["id"]:
        raise HTTPException(status_code=403, detail="Tidak boleh mengubah role akun sendiri")
        
    target = crud_user.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
        
    if target["role"] == "superadmin" and current["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Tidak boleh mengubah akun superadmin")
    if data.role == "superadmin" and current["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mengatur role superadmin")
        
    user = crud_user.update_user_role(user_id, data.role)
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

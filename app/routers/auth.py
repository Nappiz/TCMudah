from fastapi import APIRouter, Depends, Response
from app.errors.exceptions import BadRequestError

from app.schemas.schemas import RegisterIn, LoginIn, UserOut
from app.core.auth import hash_password, verify_password, create_access_token, set_jwt_cookie, clear_jwt_cookie
from app.core.deps import get_current_user
from app.crud import crud_user
from app.core.supabase_client import supabase

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn):
    exists = crud_user.get_user_by_email(data.email)
    if exists:
        raise BadRequestError(detail="Email sudah terdaftar")

    if len(data.password.encode("utf-8")) > 72:
        raise BadRequestError(detail="Password cannot be longer than 72 bytes")

    ph = hash_password(data.password)
    user = crud_user.create_user(data.email, ph, data.full_name, data.nim)
    
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

@router.post("/login", response_model=UserOut)
def login(data: LoginIn, resp: Response):
    user = crud_user.get_user_by_email(data.email)
    if not user:
        raise BadRequestError(detail="Email atau password salah")

    if not verify_password(data.password, user["password_hash"]):
        raise BadRequestError(detail="Email atau password salah")

    token = create_access_token(user["id"], user["role"], user["email"], user["full_name"], user.get("nim"))
    set_jwt_cookie(resp, token)

    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

@router.post("/logout")
def logout(resp: Response):
    clear_jwt_cookie(resp)
    return {"ok": True}

router_me = APIRouter(prefix="/me", tags=["me"])

@router_me.get("", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

@router_me.get("/has-access")
def me_has_access(user=Depends(get_current_user)):
    sb = supabase()
    res = (
        sb.table("orders")
        .select("id")
        .eq("user_id", user["id"])
        .eq("status", "approved")
        .limit(1)
        .execute()
    )
    return {"has_access": bool(res.data)}

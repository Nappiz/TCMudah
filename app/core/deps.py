from fastapi import Depends, Cookie, HTTPException, status
import jwt
from .config import get_settings
from .supabase_client import supabase

settings = get_settings()

async def get_current_user(tcmudah_token: str | None = Cookie(default=None)):
    if not tcmudah_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(tcmudah_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        uid = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sb = supabase()
    res = sb.table("users").select("*").eq("id", uid).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="User not found")
    return res.data[0]

def require_roles(*roles: str):
    async def checker(user=Depends(get_current_user)):
        if user["role"] in roles or user["role"] == "superadmin":
            return user
        raise HTTPException(status_code=403, detail="Forbidden")
    return checker

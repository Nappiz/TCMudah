from fastapi import Depends, Cookie, status
from app.errors.exceptions import ForbiddenError, UnauthorizedError

import jwt
from .config import get_settings
from .supabase_client import supabase

settings = get_settings()

async def get_current_user(tcmudah_token: str | None = Cookie(default=None)):
    if not tcmudah_token:
        raise UnauthorizedError(detail="Not authenticated")
    try:
        payload = jwt.decode(tcmudah_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        return {
            "id": payload.get("sub"),
            "role": payload.get("role"),
            "email": payload.get("email"),
            "full_name": payload.get("full_name"),
            "nim": payload.get("nim"),
        }
    except jwt.PyJWTError:
        raise UnauthorizedError(detail="Invalid token")

def require_roles(*roles: str):
    async def checker(user=Depends(get_current_user)):
        if user["role"] in roles or user["role"] == "superadmin":
            return user
        raise ForbiddenError(detail="Forbidden")
    return checker

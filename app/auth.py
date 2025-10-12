from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Response
from passlib.hash import bcrypt as passlib_bcrypt  # <-- gunakan hash class langsung
from .config import get_settings

settings = get_settings()
COOKIE_NAME = "tcmudah_token"

# ===== Password helpers =====
def hash_password(pw: str) -> str:
    # ident=2b untuk bcrypt modern; truncate_error=False agar tidak rewel di env tertentu
    return passlib_bcrypt.using(rounds=12, ident="2b", truncate_error=False).hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return passlib_bcrypt.verify(pw, hashed)
    except Exception:
        return False

# ===== JWT helpers =====
def create_access_token(sub: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRES_MIN)
    return jwt.encode({"sub": sub, "role": role, "exp": exp}, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def set_jwt_cookie(resp: Response, token: str):
    resp.set_cookie(
        key="tcmudah_token",
        value=token,
        httponly=True,
        secure=False,  # set True di production HTTPS
        samesite="lax",
        path="/",
        max_age=settings.JWT_EXPIRES_MIN * 60,
    )

def clear_jwt_cookie(resp: Response):
    resp.delete_cookie("tcmudah_token", path="/")

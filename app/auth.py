from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import jwt
from fastapi import Response
from passlib.hash import bcrypt as passlib_bcrypt

from .config import get_settings

settings = get_settings()
COOKIE_NAME = "tcmudah_token"

# ========== Password helpers ==========
def hash_password(pw: str) -> str:
    return passlib_bcrypt.using(rounds=12, ident="2b", truncate_error=False).hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return passlib_bcrypt.verify(pw, hashed)
    except Exception:
        return False

# ========== JWT helpers ==========
def create_access_token(sub: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRES_MIN)
    return jwt.encode(
        {"sub": sub, "role": role, "exp": exp},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALG,
    )

# ========== Cookie attrs (konsistensi set & delete) ==========
def _cookie_attrs():
    """
    Dengan Opsi A (proxy via FE), cookie menjadi first-party.
    - Di lokal: SameSite=Lax, Secure=False
    - Di produksi: SameSite=Lax, Secure=True
    - Domain: None (host-only) -> WAJIB, jangan set .vercel.app
    """
    fe = (settings.APP_ORIGIN or "http://localhost:3000").rstrip("/")
    fe_host = urlparse(fe).hostname or "localhost"
    is_local = fe_host in {"localhost", "127.0.0.1"}

    same_site = "lax" 
    secure = not is_local
    domain = None             
    return same_site, secure, domain

def set_jwt_cookie(resp: Response, token: str):
    same_site, secure, domain = _cookie_attrs()
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
        max_age=settings.JWT_EXPIRES_MIN * 60,
        domain=domain,  # None = host-only
    )

def clear_jwt_cookie(resp: Response):
    same_site, secure, domain = _cookie_attrs()
    resp.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        domain=domain,
        samesite=same_site,
    )
    resp.set_cookie(
        key=COOKIE_NAME,
        value="",
        httponly=True,
        secure=secure,
        samesite=same_site,
        path="/",
        max_age=0,
        domain=domain,
    )

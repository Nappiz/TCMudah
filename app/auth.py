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
    # ident=2b untuk bcrypt modern; truncate_error=False agar aman di berbagai env
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
    Tentukan atribut cookie berdasarkan APP_ORIGIN.
    - Di localhost: Secure=False, SameSite=Lax
    - Di produksi (vercel.app): Secure=True, SameSite=Lax
    - domain=None => host-only cookie (menempel hanya ke host BE, tcmudahbe.vercel.app)
    """
    fe = (settings.APP_ORIGIN or "http://localhost:3000").rstrip("/")
    fe_host = urlparse(fe).hostname or "localhost"
    is_localhost = fe_host in {"localhost", "127.0.0.1"}

    same_site = "lax"  # vercel FE & BE berada di eTLD+1 yang sama → same-site cukup Lax
    secure = False if is_localhost else True
    domain = None  # PENTING: host-only. Jangan set ".vercel.app"

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
    # 1) Hapus dengan atribut yang sama
    resp.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        domain=domain,
        samesite=same_site,
    )
    # 2) Belt & suspenders: set cookie expired (untuk browser yang rewel)
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
    
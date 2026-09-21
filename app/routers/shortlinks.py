from fastapi import APIRouter, Depends, Query
from app.errors.exceptions import ConflictError, NotFoundError

from app.schemas.schemas import PaginatedShortlinksOut, ShortlinkIn, ShortlinkOut, ShortlinkUpdate, ShortlinkResolveOut
from app.core.deps import require_roles, get_current_user
from app.core.rpc import is_unique_violation
from app.crud import crud_shortlink

router = APIRouter(tags=["shortlinks"])

@router.get(
    "/admin/shortlinks",
    response_model=PaginatedShortlinksOut,
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_shortlinks_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=120),
):
    total, data = crud_shortlink.get_admin_shortlinks(
        limit=limit, offset=(page - 1) * limit, search=search
    )
    return {"total": total, "data": data}

@router.post(
    "/admin/shortlinks",
    response_model=ShortlinkOut,
    status_code=201,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_shortlink(data: ShortlinkIn, current=Depends(get_current_user)):
    payload = data.model_dump()
    payload["slug"] = data.slug.strip().lower()
    payload["created_by"] = current["id"]
    try:
        return crud_shortlink.create_shortlink(payload)
    except Exception as exc:
        if is_unique_violation(exc):
            raise ConflictError(detail="Slug sudah dipakai") from exc
        raise

@router.patch(
    "/admin/shortlinks/{sid}",
    response_model=ShortlinkOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_shortlink(sid: str, data: ShortlinkUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}

    if payload.get("slug"):
        payload["slug"] = payload["slug"].strip().lower()

    if not payload:
        res = crud_shortlink.get_shortlink_by_id(sid)
        if not res:
            raise NotFoundError(detail="Shortlink tidak ditemukan")
        return res

    try:
        up = crud_shortlink.update_shortlink(sid, payload)
    except Exception as exc:
        if is_unique_violation(exc):
            raise ConflictError(detail="Slug sudah dipakai") from exc
        raise
    if not up:
        raise NotFoundError(detail="Shortlink tidak ditemukan")
    return up

@router.delete(
    "/admin/shortlinks/{sid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_shortlink(sid: str):
    delres = crud_shortlink.delete_shortlink(sid)
    if not delres:
        raise NotFoundError(detail="Shortlink tidak ditemukan")
    return {"ok": True}

@router.get("/shortlinks/{slug}", response_model=ShortlinkResolveOut)
def resolve_shortlink(slug: str):
    row = crud_shortlink.resolve_shortlink(slug)
    if not row:
        raise NotFoundError(detail="Shortlink tidak ditemukan")

    return {"url": row["url"]}

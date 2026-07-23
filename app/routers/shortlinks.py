from fastapi import APIRouter, Depends, HTTPException
from app.schemas.schemas import ShortlinkIn, ShortlinkOut, ShortlinkUpdate, ShortlinkResolveOut
from app.core.deps import require_roles, get_current_user
from app.crud import crud_shortlink

router = APIRouter(tags=["shortlinks"])

@router.get(
    "/admin/shortlinks",
    response_model=list[ShortlinkOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_shortlinks_admin():
    return crud_shortlink.get_admin_shortlinks()

@router.post(
    "/admin/shortlinks",
    response_model=ShortlinkOut,
    status_code=201,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_shortlink(data: ShortlinkIn, current=Depends(get_current_user)):
    if crud_shortlink.check_slug_exists(data.slug):
        raise HTTPException(status_code=400, detail="Slug sudah dipakai")

    payload = data.model_dump()
    payload["created_by"] = current["id"]

    return crud_shortlink.create_shortlink(payload)

@router.patch(
    "/admin/shortlinks/{sid}",
    response_model=ShortlinkOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_shortlink(sid: str, data: ShortlinkUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}

    new_slug = payload.get("slug")
    if new_slug:
        if crud_shortlink.check_slug_exists(new_slug, exclude_id=sid):
            raise HTTPException(status_code=400, detail="Slug sudah dipakai")

    if not payload:
        res = crud_shortlink.get_shortlink_by_id(sid)
        if not res:
            raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")
        return res

    up = crud_shortlink.update_shortlink(sid, payload)
    if not up:
        raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")
    return up

@router.delete(
    "/admin/shortlinks/{sid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_shortlink(sid: str):
    delres = crud_shortlink.delete_shortlink(sid)
    if not delres:
        raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")
    return {"ok": True}

@router.get("/shortlinks/{slug}", response_model=ShortlinkResolveOut)
def resolve_shortlink(slug: str):
    row = crud_shortlink.resolve_shortlink(slug)
    if not row:
        raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")

    try:
        current_clicks = int(row.get("clicks") or 0)
    except Exception:
        current_clicks = 0

    crud_shortlink.increment_shortlink_clicks(row["id"], current_clicks)
    return {"url": row["url"]}

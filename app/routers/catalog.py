import hashlib
import json

from fastapi import APIRouter, Header
from fastapi.responses import Response as RawResponse

from app.crud import crud_catalog
from app.schemas.schemas import CatalogOut


router = APIRouter(tags=["catalog"])
# Catalog prices and meeting options are managed from the CMS and must be
# visible immediately after an update. Keep the ETag for explicit conditional
# requests, but do not let browsers or shared proxies serve an old snapshot.
CACHE_CONTROL = "no-store"


def _etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    for candidate in if_none_match.split(","):
        normalized = candidate.strip()
        if normalized == "*":
            return True
        if normalized.startswith("W/"):
            normalized = normalized[2:].strip()
        if normalized == etag:
            return True
    return False


@router.get("/catalog", response_model=CatalogOut)
def public_catalog(
    if_none_match: str | None = Header(None),
):
    payload = CatalogOut.model_validate(crud_catalog.get_public_catalog()).model_dump(
        mode="json"
    )
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    etag = f'"{hashlib.sha256(serialized).hexdigest()}"'
    headers = {
        "Cache-Control": CACHE_CONTROL,
        "ETag": etag,
        "Vary": "Accept-Encoding",
        "Surrogate-Key": "public-catalog",
    }
    if _etag_matches(if_none_match, etag):
        return RawResponse(status_code=304, headers=headers)
    return RawResponse(
        content=serialized,
        media_type="application/json",
        headers=headers,
    )

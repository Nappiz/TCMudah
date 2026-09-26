from fastapi import APIRouter, Response

from app.crud import crud_catalog
from app.schemas.schemas import CatalogOut


router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=CatalogOut)
def public_catalog(response: Response):
    # Catalog changes must be visible immediately after a CMS update. These
    # headers also cover older HTTP/1.0 proxies that do not understand no-store.
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return CatalogOut.model_validate(crud_catalog.get_public_catalog())

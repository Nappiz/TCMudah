from fastapi import APIRouter, Depends, HTTPException
from app.schemas.schemas import PackageIn, PackageOut, PackageUpdate
from app.core.deps import require_roles
from app.crud import crud_package

router = APIRouter(tags=["packages"])

@router.get("/packages", response_model=list[PackageOut])
def list_packages_public():
    return crud_package.get_public_packages()

@router.get(
    "/admin/packages",
    response_model=list[PackageOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def list_packages_admin():
    return crud_package.get_all_packages()

@router.post(
    "/admin/packages",
    response_model=PackageOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def create_package(data: PackageIn):
    ins = crud_package.create_package(data.model_dump())
    if not ins:
        raise HTTPException(status_code=400, detail="Gagal membuat paket")
    return ins

@router.patch(
    "/admin/packages/{pid}",
    response_model=PackageOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def update_package(pid: str, data: PackageUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        res = crud_package.get_package_by_id(pid)
        if not res:
            raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
        return res
        
    up = crud_package.update_package(pid, payload)
    if not up:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
    return up

@router.delete(
    "/admin/packages/{pid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def delete_package(pid: str):
    delres = crud_package.delete_package(pid)
    if not delres:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")
    return {"ok": True}

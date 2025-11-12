from fastapi import FastAPI, Depends, HTTPException, Response, Query, Path, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal
from pydantic import BaseModel
from uuid import uuid4

from .config import get_settings
from .supabase_client import supabase
from .schemas import (
    RegisterIn, LoginIn, UserOut, UpdateRoleIn,
    CurriculumIn, CurriculumOut, CurriculumUpdate,
    TestimonialIn, TestimonialOut, TestimonialUpdate,
    MentorIn, MentorOut, MentorUpdate,
    ClassIn, ClassOut, ClassUpdate,
    CheckoutInfoOut, OrderCreateIn, OrderOut, AdminOrderOut,
    EnrollmentOut, EnrollmentSetIn,
    MaterialIn, MaterialOut, MaterialUpdate,
    FeedbackIn, FeedbackOut, AdminFeedbackOut,
    ShortlinkIn, ShortlinkOut, ShortlinkUpdate, ShortlinkResolveOut,
)
from .auth import (
    hash_password, verify_password,
    create_access_token, set_jwt_cookie, clear_jwt_cookie
)
from .deps import get_current_user, require_roles

settings = get_settings()

app = FastAPI(title="TC Mudah API")

# ---------------- CORS ----------------
frontend_origin = (settings.APP_ORIGIN or "http://localhost:3000").rstrip("/")
DEV_ORIGINS = {
    frontend_origin,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(DEV_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- HEALTH ----------------
@app.get("/healthz")
def healthz():
    return {"ok": True}

# =========================================================
#                         AUTH
# =========================================================

@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn):
    sb = supabase()
    exists = sb.table("users").select("id").eq("email", data.email).limit(1).execute()
    if exists.data:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")

    if len(data.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password cannot be longer than 72 bytes")

    ph = hash_password(data.password)
    inserted = sb.table("users").insert({
        "email": data.email,
        "password_hash": ph,
        "full_name": data.full_name,
        "nim": data.nim,
        "role": "peserta",
    }).execute()

    user = inserted.data[0]
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

@app.post("/auth/login", response_model=UserOut)
def login(data: LoginIn, resp: Response):
    sb = supabase()
    res = sb.table("users").select("*").eq("email", data.email).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Email atau password salah")

    user = res.data[0]
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Email atau password salah")

    token = create_access_token(user["id"], user["role"])
    set_jwt_cookie(resp, token)

    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

@app.post("/auth/logout")
def logout(resp: Response):
    clear_jwt_cookie(resp)
    return {"ok": True}

@app.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

@app.get("/me/has-access")
def me_has_access(user=Depends(get_current_user)):
    sb = supabase()
    res = (
        sb.table("orders")
        .select("id")
        .eq("user_id", user["id"])
        .eq("status", "approved")
        .limit(1)
        .execute()
    )
    return {"has_access": bool(res.data)}

# =========================================================
#                  USER MANAGEMENT (CMS)
# =========================================================

@app.get(
    "/admin/users",
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_users(current=Depends(get_current_user)):
    sb = supabase()
    res = sb.table("users").select("*").order("created_at", desc=True).execute()
    data = res.data or []
    me_id = current["id"]
    top = [u for u in data if u["id"] == me_id]
    rest = [u for u in data if u["id"] != me_id]
    combined = top + rest
    return [
        {
            "id": u["id"],
            "email": u["email"],
            "full_name": u["full_name"],
            "nim": u.get("nim"),
            "role": u["role"],
        }
        for u in combined
    ]

@app.patch(
    "/admin/users/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_user_role(user_id: str, data: UpdateRoleIn, current=Depends(get_current_user)):
    sb = supabase()
    if user_id == current["id"]:
        raise HTTPException(status_code=403, detail="Tidak boleh mengubah role akun sendiri")
    res = sb.table("users").select("*").eq("id", user_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    target = res.data[0]
    if target["role"] == "superadmin" and current["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Tidak boleh mengubah akun superadmin")
    if data.role == "superadmin" and current["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Hanya superadmin yang dapat mengatur role superadmin")
    upd = sb.table("users").update({"role": data.role}).eq("id", user_id).execute()
    user = upd.data[0]
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "nim": user.get("nim"),
        "role": user["role"],
    }

# =========================================================
#                      CURRICULUM
# =========================================================

@app.get("/curriculum", response_model=list[CurriculumOut])
def list_curriculum(q: str = Query("", alias="q")):
    sb = supabase()
    query = sb.table("curriculum").select("*").order("sem", desc=False).order("code", desc=False)
    if q:
        like = f"%{q}%"
        query = query.ilike("name", like)
    res = query.execute()
    return res.data or []

@app.post(
    "/curriculum",
    response_model=CurriculumOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_curriculum(data: CurriculumIn):
    sb = supabase()
    exists = sb.table("curriculum").select("id").eq("code", data.code).limit(1).execute()
    if exists.data:
        raise HTTPException(status_code=400, detail="Kode mata kuliah sudah ada")
    ins = sb.table("curriculum").insert(data.model_dump()).execute()
    return ins.data[0]

@app.patch(
    "/curriculum/{item_id}",
    response_model=CurriculumOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_curriculum(item_id: str = Path(...), data: CurriculumUpdate = ...):
    sb = supabase()
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = sb.table("curriculum").update(payload).eq("id", item_id).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return up.data[0]

@app.delete(
    "/curriculum/{item_id}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_curriculum(item_id: str):
    sb = supabase()
    delres = sb.table("curriculum").delete().eq("id", item_id).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"ok": True}

# =========================================================
#                      TESTIMONIALS
# =========================================================

@app.get("/testimonials", response_model=list[TestimonialOut])
def list_testimonials_public():
    sb = supabase()
    res = (
        sb.table("testimonials")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

@app.get(
    "/admin/testimonials",
    response_model=list[TestimonialOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_testimonials_admin():
    sb = supabase()
    res = sb.table("testimonials").select("*").order("created_at", desc=True).execute()
    return res.data or []

@app.post(
    "/admin/testimonials",
    response_model=TestimonialOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_testimonial(data: TestimonialIn):
    sb = supabase()
    ins = sb.table("testimonials").insert(data.model_dump()).execute()
    return ins.data[0]

@app.patch(
    "/admin/testimonials/{tid}",
    response_model=TestimonialOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_testimonial(tid: str, data: TestimonialUpdate):
    sb = supabase()
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = sb.table("testimonials").update(payload).eq("id", tid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return up.data[0]

@app.delete(
    "/admin/testimonials/{tid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_testimonial(tid: str):
    sb = supabase()
    delres = sb.table("testimonials").delete().eq("id", tid).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"ok": True}

# =========================================================
#                         MENTORS
# =========================================================

@app.get("/mentors", response_model=list[MentorOut])
def list_mentors_public():
    sb = supabase()
    res = (
        sb.table("mentors")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

# LIST: buka untuk mentor/admin/superadmin
@app.get("/admin/mentors",
         response_model=list[MentorOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_mentors_admin():
    sb = supabase()
    res = sb.table("mentors").select("*").order("created_at", desc=True).execute()
    return res.data or []

# CRUD: tetap admin/superadmin
@app.post("/admin/mentors",
          response_model=MentorOut,
          dependencies=[Depends(require_roles("admin", "superadmin"))])
def create_mentor(data: MentorIn):
    sb = supabase()
    ins = sb.table("mentors").insert(data.model_dump()).execute()
    return ins.data[0]

@app.patch("/admin/mentors/{mid}",
           response_model=MentorOut,
           dependencies=[Depends(require_roles("admin", "superadmin"))])
def update_mentor(mid: str, data: MentorUpdate):
    sb = supabase()
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = sb.table("mentors").update(payload).eq("id", mid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return up.data[0]

@app.delete("/admin/mentors/{mid}",
            dependencies=[Depends(require_roles("admin", "superadmin"))])
def delete_mentor(mid: str):
    sb = supabase()
    delres = sb.table("mentors").delete().eq("id", mid).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"ok": True}

# =========================================================
#                         CLASSES
# =========================================================

@app.get("/classes", response_model=list[ClassOut])
def list_classes_public():
    sb = supabase()
    res = (
        sb.table("classes")
        .select("*")
        .eq("visible", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

# LIST/GET: buka untuk mentor/admin/superadmin
@app.get("/admin/classes",
         response_model=list[ClassOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_classes_admin():
    sb = supabase()
    res = sb.table("classes").select("*").order("created_at", desc=True).execute()
    return res.data or []

@app.get("/admin/classes/{cid}",
         response_model=ClassOut,
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def get_class_admin(cid: str):
    sb = supabase()
    res = sb.table("classes").select("*").eq("id", cid).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
    return res.data[0]

# CRUD: tetap admin/superadmin
@app.post("/admin/classes",
          response_model=ClassOut,
          dependencies=[Depends(require_roles("admin", "superadmin"))])
def create_class(data: ClassIn):
    sb = supabase()
    ins = sb.table("classes").insert(data.model_dump()).execute()
    return ins.data[0]

@app.patch("/admin/classes/{cid}",
           response_model=ClassOut,
           dependencies=[Depends(require_roles("admin", "superadmin"))])
def update_class(cid: str, data: ClassUpdate):
    sb = supabase()
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    up = sb.table("classes").update(payload).eq("id", cid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return up.data[0]

@app.delete("/admin/classes/{cid}",
            dependencies=[Depends(require_roles("admin", "superadmin"))])
def delete_class(cid: str):
    sb = supabase()
    delres = sb.table("classes").delete().eq("id", cid).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
    return {"ok": True}

# =========================================================
#                       CHECKOUT / ORDERS
# =========================================================

@app.get("/checkout/info", response_model=CheckoutInfoOut, dependencies=[Depends(get_current_user)])
def checkout_info():
    return {
        "bank_name": settings.BANK_NAME,
        "bank_account": settings.BANK_ACCOUNT,
        "bank_holder": settings.BANK_HOLDER,
        "group_link": settings.GROUP_LINK,
    }

@app.post("/orders/upload")
def upload_payment_proof(file: UploadFile = File(...), user=Depends(get_current_user)):
    sb = supabase()
    ext = (file.filename or "").split(".")[-1].lower() or "jpg"
    key = f"{user['id']}/{uuid4().hex}.{ext}"
    data = file.file.read()
    sb.storage.from_("payments").upload(
        path=key,
        file=data,
        file_options={"contentType": file.content_type or "image/jpeg", "upsert": "true"},
    )
    pub = sb.storage.from_("payments").get_public_url(key)
    return {"url": pub}

@app.post("/orders", response_model=OrderOut, status_code=201, dependencies=[Depends(get_current_user)])
def create_order(payload: OrderCreateIn, user=Depends(get_current_user)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Keranjang kosong")

    sb = supabase()
    class_ids = [it.class_id for it in payload.items]
    res = sb.table("classes").select("id, price, visible").in_("id", class_ids).execute()
    price_by_id = {row["id"]: int(row["price"]) for row in (res.data or [])}
    missing = [cid for cid in class_ids if cid not in price_by_id]
    if missing:
        raise HTTPException(status_code=400, detail=f"Kelas tidak ditemukan: {', '.join(missing)}")

    items_enriched = []
    total = 0
    for it in payload.items:
        price = price_by_id[it.class_id]
        items_enriched.append({"class_id": it.class_id, "qty": it.qty, "price": price})
        total += price * it.qty

    ins = sb.table("orders").insert({
        "user_id": user["id"],
        "items": items_enriched,
        "total": total,
        "status": "pending",
        "proof_url": payload.proof_url,
        "sender_name": user["full_name"],
        "note": payload.note,
    }).execute()

    row = ins.data[0]
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "items": row["items"],
        "total": row["total"],
        "status": row["status"],
        "proof_url": row.get("proof_url"),
        "sender_name": row.get("sender_name"),
        "note": row.get("note"),
        "created_at": row.get("created_at"),
    }

@app.get("/orders/me", response_model=list[OrderOut], dependencies=[Depends(get_current_user)])
def my_orders(user=Depends(get_current_user)):
    sb = supabase()
    res = sb.table("orders").select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
    return res.data or []

# ---- ADMIN ----
@app.get("/admin/orders",
         response_model=list[AdminOrderOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_orders_admin(status: str = Query("", description="optional filter: pending/approved/rejected/expired")):
    sb = supabase()
    q = sb.table("orders").select("*").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    res = q.execute()
    orders = res.data or []

    # join user
    uids = list({o["user_id"] for o in orders if o.get("user_id")})
    users_map: dict[str, dict] = {}
    if uids:
        ures = sb.table("users").select("id, full_name, email").in_("id", uids).execute()
        for u in (ures.data or []):
            users_map[u["id"]] = u

    out = []
    for o in orders:
        u = users_map.get(o["user_id"], {})
        out.append({
            "id": o["id"],
            "user_id": o["user_id"],
            "items": o.get("items", []),
            "total": o.get("total", 0),
            "status": o.get("status", "pending"),
            "proof_url": o.get("proof_url"),
            "sender_name": o.get("sender_name"),
            "note": o.get("note"),
            "created_at": o.get("created_at"),
            "user_name": u.get("full_name"),
            "user_email": u.get("email"),
        })
    return out

class OrderStatusIn(BaseModel):
    status: Literal["approved", "rejected", "expired"]

@app.patch("/admin/orders/{oid}/status",
           response_model=AdminOrderOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def update_order_status(oid: str, data: OrderStatusIn):
    sb = supabase()
    up = sb.table("orders").update({"status": data.status}).eq("id", oid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    row = up.data[0]

    u = None
    if row.get("user_id"):
        ures = sb.table("users").select("full_name,email").eq("id", row["user_id"]).limit(1).execute()
        if ures.data:
            u = ures.data[0]

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "items": row.get("items", []),
        "total": row.get("total", 0),
        "status": row.get("status", "pending"),
        "proof_url": row.get("proof_url"),
        "sender_name": row.get("sender_name"),
        "note": row.get("note"),
        "created_at": row.get("created_at"),
        "user_name": (u or {}).get("full_name"),
        "user_email": (u or {}).get("email"),
    }

# =========================================================
#                      ENROLLMENTS
# =========================================================

@app.get("/enrollments/me", response_model=list[EnrollmentOut], dependencies=[Depends(get_current_user)])
def my_enrollments(user=Depends(get_current_user)):
    sb = supabase()
    res = (
        sb.table("enrollments")
        .select("*")
        .eq("user_id", user["id"])
        .eq("active", True)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

@app.post("/admin/enrollments/set", response_model=list[EnrollmentOut],
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def set_user_enrollments(payload: EnrollmentSetIn, current=Depends(get_current_user)):
    sb = supabase()
    existing = sb.table("enrollments").select("id, class_id").eq("user_id", payload.user_id).execute()
    existing_map = {row["class_id"]: row for row in (existing.data or [])}
    req_set = set(payload.class_ids)

    to_delete = [row["id"] for cid, row in existing_map.items() if cid not in req_set]
    if to_delete:
        sb.table("enrollments").delete().in_("id", to_delete).execute()

    to_insert = [{"user_id": payload.user_id, "class_id": cid, "active": True, "assigned_by": current["id"]} for cid in req_set if cid not in existing_map]
    if to_insert:
        sb.table("enrollments").insert(to_insert).execute()

    if req_set:
        sb.table("enrollments").update({"active": True}).eq("user_id", payload.user_id).in_("class_id", list(req_set)).execute()

    final = sb.table("enrollments").select("*").eq("user_id", payload.user_id).order("created_at", desc=True).execute()
    return final.data or []

@app.patch("/admin/enrollments/{eid}/active", response_model=EnrollmentOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def toggle_enrollment(eid: str, active: bool = Query(True)):
    sb = supabase()
    up = sb.table("enrollments").update({"active": active}).eq("id", eid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Enrollment tidak ditemukan")
    return up.data[0]

@app.get("/admin/enrollments", response_model=list[EnrollmentOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def admin_list_enrollments(user_id: str = Query(..., description="target user id")):
    sb = supabase()
    res = (
        sb.table("enrollments")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

# =========================================================
#                      MATERIALS
# =========================================================

@app.get("/admin/materials", response_model=list[MaterialOut],
         dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def list_materials_admin(class_id: str = Query(...)):
    sb = supabase()
    q = (
        sb.table("class_materials")
        .select("*")
        .eq("class_id", class_id)
        .order("created_at", desc=True)
    )
    res = q.execute()
    return res.data or []

@app.post("/admin/materials", response_model=MaterialOut,
          dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def create_material_admin(payload: MaterialIn):
    sb = supabase()
    data_to_insert = payload.model_dump(by_alias=True, exclude_none=True)
    ins = sb.table("class_materials").insert(data_to_insert).execute()
    return ins.data[0]

@app.patch("/admin/materials/{mid}", response_model=MaterialOut,
           dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def update_material_admin(mid: str, data: MaterialUpdate):
    sb = supabase()
    payload = data.model_dump(by_alias=True, exclude_none=True)
    if not payload:
        res = sb.table("class_materials").select("*").eq("id", mid).limit(1).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Materi tidak ditemukan")
        return res.data[0]
    up = sb.table("class_materials").update(payload).eq("id", mid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Materi tidak ditemukan")
    return up.data[0]

@app.delete("/admin/materials/{mid}",
            dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))])
def delete_material_admin(mid: str):
    sb = supabase()
    delres = sb.table("class_materials").delete().eq("id", mid).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Materi tidak ditemukan")
    return {"ok": True}

@app.get("/materials", response_model=list[MaterialOut], dependencies=[Depends(get_current_user)])
def list_materials_user(class_id: str = Query(...), user=Depends(get_current_user)):
    sb = supabase()

    role = (user or {}).get("role", "peserta")
    is_staff = role in ("mentor", "admin", "superadmin")

    if not is_staff:
        enr = (
            sb.table("enrollments")
            .select("id")
            .eq("user_id", user["id"])
            .eq("class_id", class_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not enr.data:
            raise HTTPException(status_code=403, detail="Tidak punya akses ke kelas ini")

    q = (
        sb.table("class_materials")
        .select("*")
        .eq("class_id", class_id)
        .eq("visible", True)
        .order("created_at", desc=True)
    )
    res = q.execute()
    return res.data or []

# =========================================================
#                      FEEDBACK (Anon)
# =========================================================

@app.post("/feedback", response_model=FeedbackOut, dependencies=[Depends(get_current_user)])
def create_or_update_feedback(payload: FeedbackIn, user=Depends(get_current_user)):
    sb = supabase()

    role = (user or {}).get("role", "peserta")
    is_staff = role in ("mentor", "admin", "superadmin")

    if not is_staff:
        enr = (
            sb.table("enrollments")
            .select("id")
            .eq("user_id", user["id"])
            .eq("class_id", payload.class_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not enr.data:
            raise HTTPException(status_code=403, detail="Tidak punya akses ke kelas ini")

    existing = (
        sb.table("feedbacks")
        .select("id")
        .eq("user_id", user["id"])
        .eq("class_id", payload.class_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        fid = existing.data[0]["id"]
        up = (
            sb.table("feedbacks")
            .update({"text": payload.text, "rating": payload.rating})
            .eq("id", fid)
            .execute()
        )
        row = up.data[0]
    else:
        ins = (
            sb.table("feedbacks")
            .insert({
                "user_id": user["id"],
                "class_id": payload.class_id,
                "text": payload.text,
                "rating": payload.rating,
            })
            .execute()
        )
        row = ins.data[0]

    return {
        "id": row["id"],
        "class_id": row["class_id"],
        "text": row["text"],
        "rating": row.get("rating"),
        "created_at": row.get("created_at"),
    }

@app.get("/feedback/me", response_model=list[FeedbackOut], dependencies=[Depends(get_current_user)])
def my_feedbacks(user=Depends(get_current_user)):
    sb = supabase()
    res = (
        sb.table("feedbacks")
        .select("id, class_id, text, rating, created_at")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

@app.get(
    "/admin/feedback",
    response_model=list[AdminFeedbackOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))]
)
def list_feedback_admin(class_id: str = Query("", description="Optional filter: class_id atau kosong untuk semua")):
    sb = supabase()
    q = sb.table("feedbacks").select("id, class_id, text, rating, created_at").order("created_at", desc=True)
    if class_id:
        q = q.eq("class_id", class_id)
    res = q.execute()
    fb = res.data or []

    cids = list({row["class_id"] for row in fb if row.get("class_id")})
    title_map: dict[str, str] = {}
    if cids:
        c = sb.table("classes").select("id,title").in_("id", cids).execute()
        for row in (c.data or []):
            title_map[row["id"]] = row.get("title", "")

    out = []
    for row in fb:
        out.append({
            "id": row["id"],
            "class_id": row["class_id"],
            "text": row["text"],
            "rating": row.get("rating"),
            "created_at": row.get("created_at"),
            "class_title": title_map.get(row["class_id"]),
        })
    return out

@app.delete(
    "/admin/feedback/{fid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))]
)
def delete_feedback_admin(fid: str):
    sb = supabase()
    delres = sb.table("feedbacks").delete().eq("id", fid).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Feedback tidak ditemukan")
    return {"ok": True}

# =========================================================
#                      SHORTLINKS
# =========================================================

@app.get(
    "/admin/shortlinks",
    response_model=list[ShortlinkOut],
    dependencies=[Depends(require_roles("mentor", "admin", "superadmin"))],
)
def list_shortlinks_admin():
    sb = supabase()
    res = (
        sb.table("shortlinks")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@app.post(
    "/admin/shortlinks",
    response_model=ShortlinkOut,
    status_code=201,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def create_shortlink(data: ShortlinkIn, current=Depends(get_current_user)):
    sb = supabase()

    # slug unik (case-insensitive)
    exists = (
        sb.table("shortlinks")
        .select("id")
        .ilike("slug", data.slug)
        .limit(1)
        .execute()
    )
    if exists.data:
        raise HTTPException(status_code=400, detail="Slug sudah dipakai")

    payload = data.model_dump()
    payload["created_by"] = current["id"]

    ins = sb.table("shortlinks").insert(payload).execute()
    return ins.data[0]


@app.patch(
    "/admin/shortlinks/{sid}",
    response_model=ShortlinkOut,
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def update_shortlink(sid: str, data: ShortlinkUpdate):
    sb = supabase()
    payload = {k: v for k, v in data.model_dump().items() if v is not None}

    # kalau slug diubah, cek unik
    new_slug = payload.get("slug")
    if new_slug:
        exists = (
            sb.table("shortlinks")
            .select("id")
            .ilike("slug", new_slug)
            .neq("id", sid)
            .limit(1)
            .execute()
        )
        if exists.data:
            raise HTTPException(status_code=400, detail="Slug sudah dipakai")

    # kalau payload kosong, cuma get data sekarang
    if not payload:
        res = sb.table("shortlinks").select("*").eq("id", sid).limit(1).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")
        return res.data[0]

    up = sb.table("shortlinks").update(payload).eq("id", sid).execute()
    if not up.data:
        raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")
    return up.data[0]


@app.delete(
    "/admin/shortlinks/{sid}",
    dependencies=[Depends(require_roles("admin", "superadmin"))],
)
def delete_shortlink(sid: str):
    sb = supabase()
    delres = sb.table("shortlinks").delete().eq("id", sid).execute()
    if not delres.data:
        raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")
    return {"ok": True}


@app.get("/shortlinks/{slug}", response_model=ShortlinkResolveOut)
def resolve_shortlink(slug: str):
    """
    Endpoint yang dipakai FE di /m/[slug].
    Return cuma { url }, FE yang urus redirect.
    """
    sb = supabase()
    res = (
        sb.table("shortlinks")
        .select("id, url, clicks, active")
        .ilike("slug", slug)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Shortlink tidak ditemukan")

    row = res.data[0]

    # increment clicks (best effort, kalau gagal ya udah)
    try:
        current_clicks = int(row.get("clicks") or 0)
    except Exception:
        current_clicks = 0

    try:
        sb.table("shortlinks").update({"clicks": current_clicks + 1}).eq("id", row["id"]).execute()
    except Exception:
        # jangan matiin request cuma gara-gara update clicks gagal
        pass

    return {"url": row["url"]}

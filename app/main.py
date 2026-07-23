from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

# Import routers
from app.routers.auth import router as auth_router, router_me
from app.routers.users import router as users_router
from app.routers.curriculum import router as curriculum_router
from app.routers.testimonials import router as testimonials_router
from app.routers.mentors import router as mentors_router
from app.routers.classes import router as classes_router
from app.routers.orders import router as orders_router
from app.routers.enrollments import router as enrollments_router
from app.routers.packages import router as packages_router
from app.routers.materials import router as materials_router
from app.routers.feedback import router as feedback_router
from app.routers.shortlinks import router as shortlinks_router

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

# ---------------- ERROR HANDLING ----------------
from app.errors.exceptions import AppException
from app.errors.handlers import app_exception_handler

app.add_exception_handler(AppException, app_exception_handler)

# ---------------- ROUTERS ----------------
app.include_router(auth_router)
app.include_router(router_me)
app.include_router(users_router)
app.include_router(curriculum_router)
app.include_router(testimonials_router)
app.include_router(mentors_router)
app.include_router(classes_router)
app.include_router(orders_router)
app.include_router(enrollments_router)
app.include_router(packages_router)
app.include_router(materials_router)
app.include_router(feedback_router)
app.include_router(shortlinks_router)

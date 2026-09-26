from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.observability import ObservabilityMiddleware
from app.core.supabase_client import close_supabase_client

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
from app.routers.notifications import router as notifications_router
from app.routers.dashboard import router as dashboard_router
from app.routers.observability import router as observability_router
from app.routers.catalog import router as catalog_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    limiter = to_thread.current_default_thread_limiter()
    limiter.total_tokens = max(
        1,
        min(settings.SYNC_WORKER_LIMIT, settings.SUPABASE_MAX_CONNECTIONS),
    )
    try:
        yield
    finally:
        close_supabase_client()


app = FastAPI(title="TC Mudah API", lifespan=lifespan)

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
    expose_headers=[
        "X-Request-ID",
        "X-DB-Queries",
        "X-Instance-Cold",
        "Server-Timing",
        "ETag",
    ],
)
# Added after CORS so instrumentation also observes preflight responses.
app.add_middleware(ObservabilityMiddleware)

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
app.include_router(notifications_router)
app.include_router(dashboard_router)
app.include_router(observability_router)
app.include_router(catalog_router)

from app.routers.batches import router as batches_router
app.include_router(batches_router)

from app.routers.settings import admin_router as admin_settings_router
from app.routers.settings import router as settings_router
app.include_router(settings_router)
app.include_router(admin_settings_router)

"""Punto de entrada FastAPI para Qullqi Rimay (Reto 2 BCP - Women in Tech)."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings, validate_runtime_security_settings
from app.services.supabase_adapter import SupabasePersistenceError
from app.routers import (
    analytics,
    auth_onboarding,
    demo_sandbox,
    health,
    movements,
    profile_consent,
    simulator,
    twilio_webhook,
)

validate_runtime_security_settings(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_runtime_security_settings()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    description=(
        "Backend de Qullqi Rimay: Registro web y WhatsApp multiusuario con Supabase Auth, "
        "intérprete bilingüe Español/Quechua Ayacuchano con confirmación en 2 pasos, "
        "cálculo semanal determinístico en Python, meta de 8 semanas y Perfil Financiero "
        "con consentimiento revocable."
    ),
)

allowed_origins = (
    [settings.frontend_origin]
    if settings.app_env == "production"
    else [
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Entrepreneur-Id",
        "X-Demo-Visitor-Id",
    ],
)

app.include_router(health.router)
app.include_router(auth_onboarding.router)
app.include_router(movements.router)
app.include_router(simulator.router)
app.include_router(analytics.router)
app.include_router(profile_consent.router)
app.include_router(demo_sandbox.router)
app.include_router(twilio_webhook.router)


@app.exception_handler(SupabasePersistenceError)
async def supabase_persistence_exception_handler(
    _request: Request, exc: SupabasePersistenceError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


@app.get("/health", tags=["Health & Demo Seed"])
def root_health_check() -> dict:
    """Endpoint directo /health para sondas de Render y verificación rápida."""
    return health.health_check()


# Sirve el panel web ya compilado (frontend/dist) desde el mismo servidor, para que la demo
# funcione en http://localhost:8000 sin necesitar Node.js. Se monta al final para que las
# rutas /api y /health tengan prioridad.
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles

_FRONTEND_DIST = _Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if (_FRONTEND_DIST / "index.html").exists():
    app.mount("/", _StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")

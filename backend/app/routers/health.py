"""Healthcheck y control del escenario Demo Rosa (Huamanga)."""

from fastapi import APIRouter, Depends
from app.config import settings
from app.security import AuthenticatedPrincipal, require_admin_or_demo_operator
from app.services.store import store

router = APIRouter(prefix="/api", tags=["Health & Demo Seed"])


@router.get("/health")
def health_check() -> dict:
    entrepreneur = store.get_entrepreneur()
    movements = store.list_movements()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "demo_entrepreneur": entrepreneur.full_name,
        "city": entrepreneur.city,
        "total_movements": len(movements),
        "external_integrations_enabled": {
            "gemini": settings.use_external_gemini,
            "supabase": settings.use_external_supabase,
            "twilio": settings.use_external_twilio,
        },
    }


@router.post("/demo/reset")
def reset_demo_state(
    _principal: AuthenticatedPrincipal = Depends(require_admin_or_demo_operator),
) -> dict:
    """Restaura las 7 semanas precargadas de Rosa y limpia la Semana 8 para repetir la demo en vivo."""
    store.reset_to_demo_seed()
    return {
        "status": "reset_ok",
        "message": "Escenario de Rosa (Huamanga) restaurado: Semanas 1-7 precargadas y Semana 8 lista para demo en vivo.",
    }

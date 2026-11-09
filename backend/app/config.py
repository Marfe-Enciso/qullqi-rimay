"""Configuración centralizada de Qullqi Rimay (sin secretos predeterminados en código)."""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

_backend_env_path = Path(__file__).resolve().parent.parent / ".env"
if _backend_env_path.exists():
    load_dotenv(_backend_env_path)
else:
    load_dotenv()

FORBIDDEN_SECRET_PREFIXES = (
    "tu_",
    "reemplazar_",
    "changeme",
    "default",
    "qullqi-rimay-local",
    "qullqi-demo-",
    "example",
)


def _is_weak_or_placeholder_secret(value: str, min_length: int = 32) -> bool:
    cleaned = (value or "").strip()
    if len(cleaned) < min_length:
        return True
    lower = cleaned.lower()
    return any(lower.startswith(prefix) for prefix in FORBIDDEN_SECRET_PREFIXES)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Qullqi Rimay API"
    app_version: str = "1.0.0"
    app_env: str = os.getenv("APP_ENV", "development").strip().lower()
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()
    use_external_gemini: bool = (
        os.getenv("USE_EXTERNAL_GEMINI", "false").strip().lower() == "true"
    )
    use_external_supabase: bool = (
        os.getenv("USE_EXTERNAL_SUPABASE", "false").strip().lower() == "true"
    )
    use_external_twilio: bool = (
        os.getenv("USE_EXTERNAL_TWILIO", "false").strip().lower() == "true"
    )
    allow_admin_demo_reset: bool = (
        os.getenv("ALLOW_ADMIN_DEMO_RESET", "false").strip().lower() == "true"
    )
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    consent_signing_secret: str = os.getenv("CONSENT_SIGNING_SECRET", "").strip()
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "").strip()


def validate_runtime_security_settings(current_settings: Optional["Settings"] = None) -> None:
    """Impide que el backend inicie en producción con secretos faltantes, cortos o predeterminados."""
    cfg = current_settings or Settings()
    if cfg.app_env != "production":
        return

    errors: list[str] = []

    if _is_weak_or_placeholder_secret(cfg.consent_signing_secret, min_length=32):
        errors.append(
            "CONSENT_SIGNING_SECRET falta, tiene menos de 32 caracteres o usa un valor predeterminado prohibido."
        )

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if _is_weak_or_placeholder_secret(cfg.supabase_jwt_secret, min_length=32) and not (
        supabase_url and supabase_anon_key
    ):
        errors.append(
            "En producción debe configurarse SUPABASE_JWT_SECRET (>=32 chars) o SUPABASE_URL + SUPABASE_ANON_KEY para validar JWTs de Supabase Auth."
        )

    if cfg.use_external_supabase:
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not supabase_url or _is_weak_or_placeholder_secret(service_key, min_length=32):
            errors.append(
                "USE_EXTERNAL_SUPABASE=true en producción requiere SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY válidos."
            )

    if not cfg.frontend_origin or "localhost" in cfg.frontend_origin or cfg.frontend_origin == "*":
        errors.append(
            "FRONTEND_ORIGIN en producción debe ser un dominio HTTPS explícito (no localhost ni '*')."
        )

    if errors:
        raise RuntimeError(
            "Fallo de seguridad al iniciar en producción: " + " | ".join(errors)
        )


settings = Settings()

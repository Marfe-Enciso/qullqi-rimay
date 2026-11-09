"""Autenticación real mediante Supabase Auth / JWT y autorización por titularidad (ownership) en FastAPI.

Garantías de seguridad:
1. CERO claves predeterminadas o secretos escritos en código (ni en backend ni en frontend).
2. El backend NO emite JWT de Supabase Auth por su cuenta en producción/runtime:
   - Los tokens provienen de Supabase Auth (`/auth/v1/verify` o `/auth/v1/token?grant_type=password`).
   - La validación criptográfica comprueba algoritmo (`HS256`), firma HMAC-SHA256 (`SUPABASE_JWT_SECRET`)
     en tiempo constante (`hmac.compare_digest`), expiración (`exp`), vigencia (`nbf`), audiencia (`aud`)
     y emisor (`iss`), o valida el token directamente contra el servidor oficial de Supabase Auth (`GET /auth/v1/user`).
3. Resolución estricta de titularidad (`auth.users.id` -> `entrepreneurs.owner_user_id`):
   - Se prohíbe reclamar un `entrepreneur_id` mediante `user_metadata` o `app_metadata` del JWT.
   - La titularidad procede exclusivamente de relaciones verificadas en PostgreSQL y procesos de registro
     o vinculación autorizados por el backend.
   - La cuenta ficticia `rosa-huamanga-001` jamás puede ser reclamada por ningún usuario autenticado.
4. Protección de operaciones administrativas (`/api/demo/reset`):
   - Desactivadas en producción salvo que `ALLOW_ADMIN_DEMO_RESET=true` esté activo en el servidor y el
     token posea rol administrativo verificado (`service_role` o `app_metadata.role == "admin"`).
"""

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status
import httpx

DEMO_ENTREPRENEUR_ID = "rosa-huamanga-001"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: str
    entrepreneur_id: str
    role: str = "authenticated"
    is_admin: bool = False


def _b64url_decode(segment: str) -> bytes:
    rem = len(segment) % 4
    if rem > 0:
        segment += "=" * (4 - rem)
    return base64.urlsafe_b64decode(segment.encode("ascii"))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def get_expected_jwt_issuer() -> str:
    """Devuelve el emisor ('iss') esperado para los JWT emitidos por Supabase Auth."""
    explicit_iss = os.getenv("SUPABASE_JWT_ISSUER", "").strip().rstrip("/")
    if explicit_iss:
        return explicit_iss
    supabase_url = os.getenv(
        "SUPABASE_URL", "https://oqbfuyxoclufkikaddoj.supabase.co"
    ).strip().rstrip("/")
    return f"{supabase_url}/auth/v1"


def create_signed_jwt(payload: Dict[str, Any], secret: str) -> str:
    """Genera un JWT HS256 firmado con el secreto provisto (utilizado únicamente en pruebas automatizadas `pytest`)."""
    if not secret or len(secret.strip()) < 16:
        raise ValueError("Se requiere un secreto de firma válido para emitir un JWT.")
    claims = dict(payload)
    claims.setdefault("aud", "authenticated")
    claims.setdefault("iss", get_expected_jwt_issuer())
    header_b64 = _b64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = _b64url_encode(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.strip().encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def _verify_hs256_jwt(token: str, secret: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token JWT inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo decodificar el token JWT.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Estructura de token JWT inválida.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if header.get("alg") != "HS256":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Algoritmo JWT no permitido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = _b64url_encode(
        hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de token JWT inválida.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now_ts = time.time()
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or isinstance(exp, bool) or now_ts >= float(exp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token JWT ha expirado o carece de fecha de expiración ('exp').",
            headers={"WWW-Authenticate": "Bearer"},
        )

    nbf = payload.get("nbf")
    if nbf is not None:
        if not isinstance(nbf, (int, float)) or isinstance(nbf, bool) or now_ts < float(nbf):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token JWT aún no es válido ('nbf').",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Validación de audiencia ('aud') conforme a Supabase Auth
    aud = payload.get("aud")
    valid_aud = False
    if isinstance(aud, str) and aud in ("authenticated", "service_role"):
        valid_aud = True
    elif isinstance(aud, list) and any(a in ("authenticated", "service_role") for a in aud):
        valid_aud = True
    if not valid_aud:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audiencia ('aud') de token JWT inválida para Supabase Auth.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validación de emisor ('iss') conforme a Supabase Auth
    iss = str(payload.get("iss") or "").strip().rstrip("/")
    expected_iss = get_expected_jwt_issuer()
    if not iss or iss != expected_iss:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Emisor ('iss') de token JWT inválido para este proyecto de Supabase Auth.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def _verify_via_supabase_auth_api(token: str) -> Optional[Dict[str, Any]]:
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if (
        not supabase_url
        or not anon_key
        or anon_key.startswith("tu_")
        or anon_key.startswith("REEMPLAZAR_")
    ):
        return None
    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "apikey": anon_key,
                    "Authorization": f"Bearer {token}",
                },
            )
            if resp.status_code != 200:
                return None
            user_data = resp.json()
            aud = user_data.get("aud") or "authenticated"
            if aud not in ("authenticated", "service_role"):
                return None
            return {
                "sub": user_data.get("id"),
                "email": user_data.get("email"),
                "email_confirmed_at": user_data.get("email_confirmed_at"),
                "role": user_data.get("role", "authenticated"),
                "aud": aud,
                "iss": get_expected_jwt_issuer(),
                "app_metadata": user_data.get("app_metadata") or {},
            }
    except Exception:
        return None


def _resolve_owned_entrepreneur_id(claims: Dict[str, Any]) -> str:
    """Resuelve el entrepreneur_id del usuario autenticado exclusivamente mediante titularidad verificada.

    PROHIBICIÓN DE SEGURIDAD:
    Jamás se lee ni acepta `user_metadata.entrepreneur_id` ni `app_metadata.entrepreneur_id`
    para reclamar ni asignar perfiles existentes.
    """
    user_id = str(claims.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token JWT no contiene identificador de usuario ('sub').",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.services.store import store

    owned_id = store.get_entrepreneur_id_by_owner_user(user_id)
    if owned_id and owned_id != DEMO_ENTREPRENEUR_ID:
        return owned_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="El usuario autenticado no tiene una cuenta de emprendedora vinculada (owner_user_id verificado).",
    )


def require_authenticated_entrepreneur(
    authorization: Optional[str] = Header(default=None),
    x_entrepreneur_id: Optional[str] = Header(default=None, alias="X-Entrepreneur-Id"),
) -> AuthenticatedPrincipal:
    """Exige un JWT Bearer válido de Supabase Auth y comprueba titularidad."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida: envíe un token Bearer JWT válido de Supabase Auth.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer vacío.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    claims: Optional[Dict[str, Any]] = None

    if jwt_secret and len(jwt_secret) >= 16:
        claims = _verify_hs256_jwt(token, jwt_secret)
    else:
        claims = _verify_via_supabase_auth_api(token)

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT de Supabase Auth inválido, expirado o no verificable.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = str(claims.get("role") or "authenticated")
    if role not in ("authenticated", "service_role"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol de token no autorizado.",
        )

    entrepreneur_id = _resolve_owned_entrepreneur_id(claims)
    if x_entrepreneur_id and x_entrepreneur_id.strip() != entrepreneur_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: la sesión autenticada no es titular del entrepreneur_id solicitado.",
        )

    app_meta = claims.get("app_metadata") or {}
    is_admin = role == "service_role" or (
        isinstance(app_meta, dict) and app_meta.get("role") == "admin"
    )

    return AuthenticatedPrincipal(
        user_id=str(claims["sub"]),
        entrepreneur_id=entrepreneur_id,
        role=role,
        is_admin=is_admin,
    )


def require_admin_or_demo_operator(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> AuthenticatedPrincipal:
    """Protege /api/demo/reset: desactivado en producción salvo autorización administrativa explícita."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    allow_reset = os.getenv("ALLOW_ADMIN_DEMO_RESET", "false").strip().lower() == "true"

    if app_env == "production" and not allow_reset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La operación administrativa /api/demo/reset está desactivada en el entorno público.",
        )

    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere privilegio administrativo verificado (role=admin o service_role) para ejecutar esta operación.",
        )

    return principal

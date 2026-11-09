"""Rutas de Registro Web Real con Supabase Auth Oficial, Verificación de Correo, Login y Vinculación WhatsApp.

Garantías de seguridad:
1. No se devuelve jamás un código de verificación generado localmente en la respuesta HTTP.
2. El backend no emite JWT de Supabase Auth por su cuenta ni marca cuentas como verificadas
   sin completar el procedimiento oficial de Supabase Auth (`/auth/v1/signup`, `/auth/v1/verify`,
   `/auth/v1/token?grant_type=password`).
3. Si Supabase Auth devuelve HTTP 429 (límite de envío SMTP), el backend informa explícitamente
   el bloqueo SMTP sin saltar ni simular la verificación de correo.
"""

import os
from typing import Any, Dict, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
import httpx

from app.models import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthRegisterResponse,
    AuthSessionResponse,
    AuthVerifyEmailRequest,
    EntrepreneurProfileInfo,
    LanguagePreferenceUpdateRequest,
    WhatsappClaimCodeRequest,
    WhatsappLinkGenerateResponse,
)
from app.security import (
    AuthenticatedPrincipal,
    require_authenticated_entrepreneur,
)
from app.services.store import store

router = APIRouter(
    prefix="/api/auth",
    tags=["1 & 2. Registro Web Real, Supabase Auth y Vinculación WhatsApp"],
)


def _get_supabase_auth_config() -> Tuple[str, str]:
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if (
        not supabase_url
        or not anon_key
        or anon_key.startswith(("tu_", "REEMPLAZAR_"))
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configuración de Supabase Auth (SUPABASE_URL / SUPABASE_ANON_KEY) ausente en el servidor.",
        )
    return supabase_url, anon_key


def _supabase_auth_signup(
    email: str, password: str, metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """Ejecuta el registro oficial en Supabase Auth (`POST /auth/v1/signup`)."""
    supabase_url, anon_key = _get_supabase_auth_config()
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{supabase_url}/auth/v1/signup",
                headers={
                    "apikey": anon_key,
                    "Content-Type": "application/json",
                },
                json={
                    "email": email,
                    "password": password,
                    "data": metadata,
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo conectar con el servicio oficial de Supabase Auth.",
        ) from exc

    if resp.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Límite de envío de correos de Supabase Auth alcanzado (HTTP 429). "
                "Por seguridad no se generan códigos locales sin entrega real al buzón de la emprendedora. "
                "Espera unos minutos o configura un servidor SMTP personalizado en Supabase Dashboard -> Authentication -> Emails -> SMTP Settings."
            ),
        )

    if resp.status_code not in (200, 201):
        err_body = resp.json() if resp.content else {}
        err_msg = (
            err_body.get("msg")
            or err_body.get("error_description")
            or err_body.get("message")
            or f"Error en Supabase Auth ({resp.status_code})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supabase Auth rechazó el registro: {err_msg}",
        )

    return resp.json()


def _supabase_auth_verify_otp(email: str, token: str) -> Dict[str, Any]:
    """Verifica el código/token oficial enviado al correo de la usuaria mediante `POST /auth/v1/verify`."""
    supabase_url, anon_key = _get_supabase_auth_config()
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{supabase_url}/auth/v1/verify",
                headers={
                    "apikey": anon_key,
                    "Content-Type": "application/json",
                },
                json={
                    "type": "signup",
                    "email": email,
                    "token": token,
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo conectar con Supabase Auth para verificar el correo.",
        ) from exc

    if resp.status_code != 200:
        err_body = resp.json() if resp.content else {}
        err_msg = (
            err_body.get("msg")
            or err_body.get("error_description")
            or err_body.get("message")
            or "Código o token de verificación inválido o expirado en Supabase Auth."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    return resp.json()


def _supabase_auth_login_password(email: str, password: str) -> Dict[str, Any]:
    """Inicia sesión oficial contra Supabase Auth (`POST /auth/v1/token?grant_type=password`)."""
    supabase_url, anon_key = _get_supabase_auth_config()
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{supabase_url}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": anon_key,
                    "Content-Type": "application/json",
                },
                json={
                    "email": email,
                    "password": password,
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo conectar con Supabase Auth para iniciar sesión.",
        ) from exc

    if resp.status_code != 200:
        err_body = resp.json() if resp.content else {}
        err_msg = (
            err_body.get("msg")
            or err_body.get("error_description")
            or err_body.get("message")
            or "Credenciales inválidas o correo electrónico aún no confirmado en Supabase Auth."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_msg,
        )

    return resp.json()


@router.post("/register", response_model=AuthRegisterResponse, status_code=201)
def register_entrepreneur_account(payload: AuthRegisterRequest) -> AuthRegisterResponse:
    """Inicia el registro real de una emprendedora en Supabase Auth con verificación real por correo."""
    if not payload.accepted_data_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Es obligatorio aceptar el consentimiento informado de tratamiento de datos.",
        )

    # 1. Registrar identidad en Supabase Auth oficial (envía correo real a la bandeja de la emprendedora)
    signup_data = _supabase_auth_signup(
        email=payload.email.strip().lower(),
        password=payload.password,
        metadata={
            "full_name": payload.full_name.strip(),
            "business_name": payload.business_name.strip(),
            "trade_sector": payload.trade_sector.strip(),
            "market_location": payload.market_location.strip(),
            "city": payload.city.strip(),
            "region": payload.region.strip(),
            "goal_title": payload.goal_title.strip(),
            "goal_target_pen": payload.goal_target_pen,
            "preferred_language": payload.preferred_language,
            "whatsapp_claim_code": payload.whatsapp_claim_code,
        },
    )

    user_obj = signup_data.get("user") if isinstance(signup_data.get("user"), dict) else signup_data
    supabase_user_id = str((user_obj or {}).get("id") or "").strip()
    if not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supabase Auth no devolvió un identificador de usuario válido.",
        )

    # Si Supabase devuelve identities == [] significa que el correo ya estaba registrado en auth.users
    identities = (user_obj or {}).get("identities")
    if isinstance(identities, list) and len(identities) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta registrada con este correo electrónico en Supabase Auth.",
        )

    # 2. Preparar el perfil de emprendedora vinculado al UUID oficial de Supabase Auth (pendiente de confirmar correo)
    try:
        acc, profile = store.initiate_web_registration(
            email=payload.email,
            full_name=payload.full_name,
            business_name=payload.business_name,
            trade_sector=payload.trade_sector,
            market_location=payload.market_location,
            city=payload.city,
            region=payload.region,
            goal_title=payload.goal_title,
            goal_target_pen=payload.goal_target_pen,
            preferred_language=payload.preferred_language,
            accepted_data_consent=payload.accepted_data_consent,
            consent_version=payload.consent_version,
            whatsapp_claim_code=payload.whatsapp_claim_code,
            supabase_user_id=supabase_user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AuthRegisterResponse(
        status="PENDING_EMAIL_VERIFICATION",
        user_id=supabase_user_id,
        entrepreneur_id=profile.id,
        email=acc.email,
        verification_required=True,
        email_verification_required=True,
        verification_delivery_mode="SUPABASE_AUTH_EMAIL",
        message=(
            f"Cuenta registrada en Supabase Auth para {profile.full_name} ({profile.business_name}). "
            f"Revisa la bandeja de entrada de '{acc.email}': haz clic en el enlace oficial de confirmación "
            "enviado por Supabase Auth (y luego inicia sesión) o ingresa el código OTP recibido por correo."
        ),
    )


@router.post("/verify-email", response_model=AuthSessionResponse)
def verify_email_and_login(payload: AuthVerifyEmailRequest) -> AuthSessionResponse:
    """Verifica el código OTP/token enviado por Supabase Auth al correo real de la emprendedora."""
    verify_data = _supabase_auth_verify_otp(
        email=payload.email.strip().lower(),
        token=payload.verification_code.strip(),
    )
    access_token = str(verify_data.get("access_token") or "").strip()
    user_obj = verify_data.get("user") or {}
    supabase_user_id = str(user_obj.get("id") or "").strip()

    if not access_token or not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supabase Auth no devolvió una sesión activa tras verificar el código.",
        )

    try:
        profile = store.activate_verified_supabase_user(
            email=payload.email.strip().lower(),
            supabase_user_id=supabase_user_id,
            user_metadata=user_obj.get("user_metadata") or {},
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return AuthSessionResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(verify_data.get("expires_in") or 3600),
        user_id=supabase_user_id,
        email=payload.email.strip().lower(),
        entrepreneur=profile,
    )


@router.post("/login", response_model=AuthSessionResponse)
def login_entrepreneur(payload: AuthLoginRequest) -> AuthSessionResponse:
    """Inicia sesión oficial contra Supabase Auth (solo permite cuentas con correo verificado)."""
    login_data = _supabase_auth_login_password(
        email=payload.email.strip().lower(),
        password=payload.password,
    )
    access_token = str(login_data.get("access_token") or "").strip()
    user_obj = login_data.get("user") or {}
    supabase_user_id = str(user_obj.get("id") or "").strip()
    email_confirmed_at = user_obj.get("email_confirmed_at") or user_obj.get("confirmed_at")

    if not access_token or not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase Auth no devolvió un token de sesión válido.",
        )

    if not email_confirmed_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes verificar tu correo electrónico antes de iniciar sesión.",
        )

    try:
        profile = store.activate_verified_supabase_user(
            email=payload.email.strip().lower(),
            supabase_user_id=supabase_user_id,
            user_metadata=user_obj.get("user_metadata") or {},
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return AuthSessionResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(login_data.get("expires_in") or 3600),
        user_id=supabase_user_id,
        email=payload.email.strip().lower(),
        entrepreneur=profile,
    )


@router.get("/me", response_model=EntrepreneurProfileInfo)
def get_authenticated_entrepreneur_profile(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> EntrepreneurProfileInfo:
    return store.get_entrepreneur(principal.entrepreneur_id)


@router.patch("/preferences", response_model=EntrepreneurProfileInfo)
def update_entrepreneur_preferences(
    payload: LanguagePreferenceUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> EntrepreneurProfileInfo:
    return store.update_entrepreneur_language(
        entrepreneur_id=principal.entrepreneur_id,
        preferred_language=payload.preferred_language,
    )


@router.post("/whatsapp/generate-code", response_model=WhatsappLinkGenerateResponse)
def generate_whatsapp_link_code(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> WhatsappLinkGenerateResponse:
    """Genera un código único VINC-XXXXXX (15 min) para vincular el WhatsApp de la emprendedora."""
    code, expires_at = store.generate_whatsapp_link_code(principal.entrepreneur_id)
    sandbox_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886").replace(
        "whatsapp:", ""
    )
    sandbox_join_phrase = os.getenv("TWILIO_SANDBOX_JOIN_CODE", "join <codigo-sandbox>")
    instructions = (
        f"1) Si usas Twilio Sandbox por primera vez, envía '{sandbox_join_phrase}' al número {sandbox_number}. "
        f"2) Luego envía únicamente el código '{code}' por WhatsApp para vincular tu cuenta."
    )
    return WhatsappLinkGenerateResponse(
        link_code=code,
        expires_at=expires_at,
        sandbox_join_instruction=instructions,
        sandbox_instructions=instructions,
        whatsapp_command=code,
        wa_me_url=f"https://wa.me/{sandbox_number.lstrip('+')}?text={code}",
    )


@router.post("/whatsapp/claim-provisional", response_model=EntrepreneurProfileInfo)
def claim_whatsapp_provisional_code(
    payload: WhatsappClaimCodeRequest,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> EntrepreneurProfileInfo:
    """Vincula un registro provisional iniciado por WhatsApp (WA-LINK-XXXXXXXX) con la sesión web actual."""
    try:
        return store.claim_whatsapp_provisional_from_web(
            entrepreneur_id=principal.entrepreneur_id,
            claim_code=payload.claim_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/whatsapp/provisional/{claim_code}")
def inspect_whatsapp_provisional_code(claim_code: str) -> dict:
    """Permite pre-llenar el formulario web cuando la usuaria abre el enlace recibido en WhatsApp."""
    draft = store.get_provisional_draft_by_claim_code(claim_code)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El código de vinculación de WhatsApp no existe, ya fue usado o expiró.",
        )
    return {
        "claim_code": claim_code.strip().upper(),
        "full_name": draft.full_name,
        "business_name": draft.business_name,
        "city": draft.city,
        "preferred_language": draft.preferred_language,
        "phone_masked": draft.phone_masked,
        "consent_accepted": draft.consent_accepted,
    }

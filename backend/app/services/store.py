"""Repositorio multiusuario de Qullqi Rimay con persistencia estricta en Supabase PostgreSQL
y soporte para sandboxes efímeros de la Demostración Ampliada de Rosa (133 movimientos).

Garantías de seguridad y persistencia:
1. Titularidad estricta (`owner_user_id` verificado en PostgreSQL):
   - Prohibido reclamar `entrepreneur_id` desde `user_metadata` o `app_metadata`.
   - Prohibido asignar `owner_user_id` o reclamar la cuenta ficticia `rosa-huamanga-001`.
2. Consentimiento expreso:
   - Ninguna cuenta real tiene consentimiento automático; se exige aceptación expresa registrando
     `data_consent_accepted=True`, `data_consent_accepted_at` (ISO-8601 UTC) y `data_consent_version`.
   - La cuenta ficticia `rosa-huamanga-001` conserva `data_consent_accepted=False`, `owner_user_id=None`.
3. WhatsApp y códigos de un solo uso en PostgreSQL:
   - `whatsapp_onboarding_sessions`, `whatsapp_links` y `whatsapp_link_challenges` se persisten en PostgreSQL
     como fuente de verdad cuando `USE_EXTERNAL_SUPABASE=true`.
   - Idempotencia de `MessageSid` sin usar jamás `rosa-huamanga-001` como referencia alternativa.
   - Verificación atómica de expiración, uso único y límite de intentos (<= 5).
4. CERO hashes de contraseñas en `store` ni en `audit_logs`; gestión de contraseñas delegada a Supabase Auth.
5. Sin regreso silencioso a memoria cuando `USE_EXTERNAL_SUPABASE=true`.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
import hmac
import re
import secrets
from threading import RLock
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from app.models import (
    ChatMessageBubble,
    ConsentRecord,
    EntrepreneurProfileInfo,
    LanguageCode,
    MovementRecord,
)
from app.seed_rosa import (
    get_enriched_demo_movements,
    get_initial_chat_history,
    get_initial_movements,
    get_rosa_profile,
)
from app.services.finance_engine import compute_weekly_summaries
from app.services.supabase_adapter import SupabasePersistenceError, supabase_adapter

DEMO_ENTREPRENEUR_ID = "rosa-huamanga-001"
DEFAULT_CONSENT_VERSION = "v1.0-2026-11"


def normalize_whatsapp_phone(raw_phone: str) -> str:
    cleaned = re.sub(r"^whatsapp:", "", (raw_phone or "").strip(), flags=re.IGNORECASE)
    digits = re.sub(r"[^\d+]", "", cleaned)
    if digits and not digits.startswith("+"):
        digits = "+" + digits
    return digits


def mask_phone_number(normalized_phone: str) -> str:
    digits = re.sub(r"\D", "", normalized_phone)
    if len(digits) < 6:
        return "+51 *** ***"
    return f"+{digits[:2]} {digits[2:5]} *** {digits[-3:]}"


def hash_phone_number(normalized_phone: str) -> str:
    return hashlib.sha256(normalized_phone.encode("utf-8")).hexdigest()


@dataclass
class RegisteredUserAccount:
    """Metadatos de vinculación entre usuario de Supabase Auth y perfil de emprendedora (CERO contraseñas)."""

    user_id: str
    email: str
    entrepreneur_id: str
    email_verified: bool = False
    created_at: str = ""


@dataclass
class SingleUseChallenge:
    code_sha256: str
    entrepreneur_id: str
    challenge_type: str = "WEB_TO_WA"
    phone_sha256: str = ""
    phone_masked: str = ""
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=15)
    )
    used: bool = False
    used_at: Optional[str] = None
    attempts: int = 0


@dataclass
class WhatsappOnboardingDraft:
    phone_sha256: str
    phone_masked: str
    step: str = "AWAITING_LANGUAGE"
    preferred_language: LanguageCode = "es"
    full_name: str = ""
    business_name: str = ""
    city: str = "Huamanga"
    trade_sector: str = "Comercio minorista"
    consent_accepted: bool = False
    consent_accepted_at: Optional[str] = None
    consent_version: Optional[str] = None
    provisional_entrepreneur_id: str = ""
    claim_code_plain_once: str = ""
    claim_code_sha256: str = ""
    claim_expires_at: Optional[datetime] = None
    last_message_sid: Optional[str] = None


class InMemoryStore:
    def __init__(
        self, use_supabase: bool = True, use_enriched_demo: bool = False
    ) -> None:
        self._lock = RLock()
        self._use_supabase = use_supabase
        self._use_enriched_demo = use_enriched_demo
        self._init_memory_state()
        if self._is_supabase_active():
            weekly_summaries = compute_weekly_summaries(
                self.movements, self.entrepreneur
            )
            supabase_adapter.ensure_seed_data(
                self.entrepreneur,
                self.movements,
                self.chat_history,
                weekly_summaries,
            )

    def _init_memory_state(self) -> None:
        rosa = get_rosa_profile()
        self.entrepreneur: EntrepreneurProfileInfo = rosa
        self.entrepreneurs_by_id: Dict[str, EntrepreneurProfileInfo] = {rosa.id: rosa}
        self.movements: List[MovementRecord] = (
            get_enriched_demo_movements()
            if self._use_enriched_demo
            else get_initial_movements()
        )
        self.chat_history_by_eid: Dict[str, List[ChatMessageBubble]] = {
            rosa.id: get_initial_chat_history()
        }
        self.consents: List[ConsentRecord] = []
        self.processed_message_sids: Set[str] = set()
        self.owner_by_entrepreneur: Dict[str, str] = {}
        self.users_by_email: Dict[str, RegisteredUserAccount] = {}
        self.phone_hash_to_entrepreneur: Dict[str, str] = {}
        self.whatsapp_drafts_by_phone_hash: Dict[str, WhatsappOnboardingDraft] = {}
        self.challenges_by_hash: Dict[str, SingleUseChallenge] = {}
        # Cuentas creadas por WhatsApp en modo demo que viven solo en memoria
        self.memory_only_eids: Set[str] = set()

    @property
    def chat_history(self) -> List[ChatMessageBubble]:
        return self.chat_history_by_eid.setdefault(self.entrepreneur.id, [])

    def _is_supabase_active(self) -> bool:
        return self._use_supabase and supabase_adapter.is_enabled

    def _remote_for(self, entrepreneur_id: Optional[str]) -> bool:
        """Supabase activo y la cuenta no es una cuenta demo creada solo en memoria."""
        if entrepreneur_id and entrepreneur_id in getattr(self, "memory_only_eids", set()):
            return False
        return self._is_supabase_active()

    @staticmethod
    def demo_autolink_enabled() -> bool:
        """Modo demo de la hackatón: el registro por WhatsApp crea la cuenta al instante."""
        return os.getenv("WHATSAPP_DEMO_AUTOLINK", "false").strip().lower() == "true"

    def _persist_entrepreneur_and_consent_audit(
        self,
        profile: EntrepreneurProfileInfo,
        action_type: str = "ENTREPRENEUR_ACCOUNT_UPDATED",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persiste el perfil en public.entrepreneurs y registra auditoría SIN contraseñas ni secretos."""
        if profile.id == DEMO_ENTREPRENEUR_ID and profile.owner_user_id is not None:
            raise PermissionError(
                "Prohibido reclamar o asignar owner_user_id a la cuenta ficticia 'rosa-huamanga-001'."
            )
        if not self._remote_for(profile.id):
            return
        supabase_adapter.upsert_entrepreneur(profile)
        self._sync_weekly_goals_snapshot(profile.id)
        audit_meta: Dict[str, Any] = {
            "owner_user_id": profile.owner_user_id,
            "preferred_language": profile.preferred_language,
            "data_consent_accepted": profile.data_consent_accepted,
            "data_consent_accepted_at": profile.data_consent_accepted_at,
            "data_consent_version": profile.data_consent_version,
            "whatsapp_linked": profile.whatsapp_linked,
        }
        if extra_metadata:
            for k, v in extra_metadata.items():
                if k not in ("password", "password_hash", "password_salt", "access_token"):
                    audit_meta[k] = v
        supabase_adapter.log_audit_event(
            entrepreneur_id=profile.id,
            action_type=action_type,
            entity_type="entrepreneur_account",
            entity_id=profile.id,
            metadata=audit_meta,
        )

    def get_entrepreneur_id_by_owner_user(self, user_id: str) -> Optional[str]:
        """Resuelve el entrepreneur_id exclusivamente por relación verificada owner_user_id."""
        if not user_id or not user_id.strip():
            return None
        clean_uid = user_id.strip()
        if self._is_supabase_active():
            row = supabase_adapter.fetch_entrepreneur_by_owner_user(clean_uid)
            if not row:
                return None
            eid = str(row.get("id") or "").strip()
            if not eid or eid == DEMO_ENTREPRENEUR_ID:
                return None
            prof = EntrepreneurProfileInfo.model_validate(row)
            with self._lock:
                self.entrepreneurs_by_id[eid] = prof
                self.owner_by_entrepreneur[eid] = clean_uid
            return eid

        with self._lock:
            for eid, owner in self.owner_by_entrepreneur.items():
                if owner == clean_uid and eid != DEMO_ENTREPRENEUR_ID:
                    return eid
        return None

    def get_entrepreneur(
        self, entrepreneur_id: Optional[str] = None
    ) -> EntrepreneurProfileInfo:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if self._remote_for(target_eid) and target_eid != DEMO_ENTREPRENEUR_ID:
            row = supabase_adapter.fetch_entrepreneur_by_id(target_eid)
            if not row:
                raise KeyError(
                    f"No existe el perfil de emprendedora '{target_eid}' en PostgreSQL."
                )
            prof = EntrepreneurProfileInfo.model_validate(row)
            with self._lock:
                self.entrepreneurs_by_id[target_eid] = prof
            return prof

        with self._lock:
            if target_eid in self.entrepreneurs_by_id:
                return self.entrepreneurs_by_id[target_eid]
        return self.entrepreneur

    def update_entrepreneur_language(
        self, entrepreneur_id: str, preferred_language: LanguageCode
    ) -> EntrepreneurProfileInfo:
        prof = self.get_entrepreneur(entrepreneur_id)
        updated = prof.model_copy(update={"preferred_language": preferred_language})
        with self._lock:
            self.entrepreneurs_by_id[entrepreneur_id] = updated
            if entrepreneur_id == self.entrepreneur.id:
                self.entrepreneur = updated
        self._persist_entrepreneur_and_consent_audit(
            updated,
            action_type="UPDATE_LANGUAGE_PREFERENCE",
            extra_metadata={"preferred_language": preferred_language},
        )
        return updated

    # --- Registro Web Real y Activación Tras Verificación en Supabase Auth (Prioridades 1 y 2) ---

    def initiate_web_registration(
        self,
        email: str,
        full_name: str,
        business_name: str,
        trade_sector: str,
        market_location: str,
        city: str,
        region: str,
        goal_title: str,
        goal_target_pen: float,
        preferred_language: LanguageCode,
        accepted_data_consent: bool,
        consent_version: str = DEFAULT_CONSENT_VERSION,
        whatsapp_claim_code: Optional[str] = None,
        supabase_user_id: Optional[str] = None,
    ) -> Tuple[RegisteredUserAccount, EntrepreneurProfileInfo]:
        if not accepted_data_consent:
            raise ValueError(
                "Es obligatorio aceptar expresamente el consentimiento informado de tratamiento de datos."
            )
        version_clean = (consent_version or "").strip()
        if not version_clean:
            raise ValueError(
                "Debe especificarse la versión de las condiciones de consentimiento aceptadas."
            )

        email_clean = email.strip().lower()
        user_id = (supabase_user_id or "").strip()
        if not user_id:
            raise ValueError(
                "Se requiere el identificador de usuario oficial emitido por Supabase Auth."
            )

        if self._is_supabase_active():
            existing_row = supabase_adapter.fetch_entrepreneur_by_owner_user(user_id)
            if existing_row:
                raise ValueError(
                    "Este usuario de Supabase Auth ya posee un perfil de emprendedora registrado."
                )

        with self._lock:
            existing = self.users_by_email.get(email_clean)
            if existing and existing.email_verified:
                raise ValueError(
                    "Ya existe una cuenta verificada con este correo electrónico."
                )

        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Verificar si se está reclamando un registro provisional iniciado por WhatsApp
        claimed_draft: Optional[WhatsappOnboardingDraft] = None
        claimed_phone_hash: Optional[str] = None
        if whatsapp_claim_code and whatsapp_claim_code.strip():
            raw_claim = whatsapp_claim_code.strip().upper()
            claim_hash = hashlib.sha256(raw_claim.encode("utf-8")).hexdigest()
            claimed_draft, claimed_phone_hash = self._consume_provisional_claim_code_atomic(
                claim_hash=claim_hash, now_dt=now_dt
            )

        if claimed_draft and claimed_draft.provisional_entrepreneur_id:
            eid = claimed_draft.provisional_entrepreneur_id
            if eid == DEMO_ENTREPRENEUR_ID:
                raise ValueError("Identificador de emprendedora inválido.")
            phone_masked = claimed_draft.phone_masked
            wa_linked = True
        else:
            eid = f"emp-{uuid.uuid4().hex[:10]}"
            phone_masked = "No vinculado"
            wa_linked = False

        weekly_target = round(float(goal_target_pen) / 8.0, 2)
        profile = EntrepreneurProfileInfo(
            id=eid,
            full_name=full_name.strip(),
            business_name=business_name.strip(),
            trade_sector=trade_sector.strip(),
            market_location=market_location.strip(),
            city=city.strip(),
            region=region.strip(),
            phone_masked=phone_masked,
            goal_title=goal_title.strip(),
            goal_target_pen=round(float(goal_target_pen), 2),
            goal_weekly_target_pen=weekly_target,
            goal_weeks=8,
            active_week=1,
            preferred_language=preferred_language,
            owner_user_id=user_id,
            data_consent_accepted=True,
            data_consent_accepted_at=now_iso,
            data_consent_version=version_clean,
            whatsapp_linked=wa_linked,
            is_fictional_demo=False,
        )

        acc = RegisteredUserAccount(
            user_id=user_id,
            email=email_clean,
            entrepreneur_id=eid,
            email_verified=False,
            created_at=now_iso,
        )

        welcome_bubble = ChatMessageBubble(
            id=f"chat-welcome-{eid}",
            sender="QULLQI_BOT",
            text=(
                f"¡Rimaykullayki {profile.full_name}! Bienvenida a Qullqi Rimay para tu negocio '{profile.business_name}'."
                if preferred_language == "es"
                else f"¡Rimaykullayki {profile.full_name}! '{profile.business_name}' qhatuykipaq Qullqi Rimaypi chaskiykuyki."
            ),
            timestamp=now_iso,
            week_number=1,
        )

        # Si USE_EXTERNAL_SUPABASE=true, persistir en PostgreSQL antes de confirmar el registro
        if self._is_supabase_active():
            self._persist_entrepreneur_and_consent_audit(
                profile,
                action_type="DATA_CONSENT_ACCEPTED",
                extra_metadata={
                    "channel": "WEB_REGISTER_WITH_WA_CLAIM"
                    if claimed_phone_hash
                    else "WEB_REGISTER",
                    "consent_version": version_clean,
                    "consent_accepted_at": now_iso,
                },
            )
            if claimed_phone_hash:
                supabase_adapter.insert_whatsapp_link_atomic(
                    phone_sha256=claimed_phone_hash,
                    entrepreneur_id=eid,
                    phone_masked=phone_masked,
                )
                if claimed_draft:
                    supabase_adapter.upsert_whatsapp_onboarding_session(
                        {
                            "phone_sha256": claimed_phone_hash,
                            "phone_masked": phone_masked,
                            "step": "LINKED",
                            "preferred_language": profile.preferred_language,
                            "full_name": profile.full_name,
                            "business_name": profile.business_name,
                            "city": profile.city,
                            "consent_accepted": True,
                            "consent_accepted_at": claimed_draft.consent_accepted_at
                            or now_iso,
                            "consent_version": claimed_draft.consent_version
                            or version_clean,
                            "provisional_entrepreneur_id": eid,
                            "updated_at": now_iso,
                        }
                    )
            supabase_adapter.sync_chat_bubble(eid, welcome_bubble)

        with self._lock:
            self.users_by_email[email_clean] = acc
            self.entrepreneurs_by_id[eid] = profile
            self.owner_by_entrepreneur[eid] = user_id
            if claimed_phone_hash:
                self.phone_hash_to_entrepreneur[claimed_phone_hash] = eid
                if claimed_phone_hash in self.whatsapp_drafts_by_phone_hash:
                    self.whatsapp_drafts_by_phone_hash[claimed_phone_hash].step = "LINKED"
            self.chat_history_by_eid.setdefault(eid, [welcome_bubble])

        return acc, profile

    def activate_verified_supabase_user(
        self,
        email: str,
        supabase_user_id: str,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> EntrepreneurProfileInfo:
        """Activa y recupera el perfil de emprendedora tras verificación real en Supabase Auth.

        PROHIBICIÓN DE SEGURIDAD:
        Jamás se lee ni acepta `user_metadata.entrepreneur_id` para reclamar perfiles existentes.
        La titularidad proviene exclusivamente de PostgreSQL (`entrepreneurs.owner_user_id`)
        o del registro autorizado por el backend (`initiate_web_registration`).
        """
        email_clean = email.strip().lower()
        clean_uid = (supabase_user_id or "").strip()
        if not clean_uid:
            raise PermissionError("Identificador de usuario de Supabase Auth vacío.")

        # Si el usuario intentó inyectar entrepreneur_id="rosa-huamanga-001" en user_metadata,
        # se ignora por completo user_metadata.entrepreneur_id y solo se consulta la relación verificada.
        if self._is_supabase_active():
            row = supabase_adapter.fetch_entrepreneur_by_owner_user(clean_uid)
            if not row:
                raise PermissionError(
                    "Acceso denegado: este usuario no tiene un perfil de emprendedora registrado ni consentimiento expreso en PostgreSQL."
                )
            eid = str(row.get("id") or "").strip()
            if not eid or eid == DEMO_ENTREPRENEUR_ID:
                raise PermissionError(
                    "Acceso denegado: titularidad de emprendedora inválida."
                )
            prof = EntrepreneurProfileInfo.model_validate(row)
            if not prof.data_consent_accepted or not prof.data_consent_accepted_at or not prof.data_consent_version:
                raise PermissionError(
                    "Acceso denegado: la cuenta no registra consentimiento expreso válido."
                )
            with self._lock:
                self.entrepreneurs_by_id[eid] = prof
                self.owner_by_entrepreneur[eid] = clean_uid
                if email_clean in self.users_by_email:
                    self.users_by_email[email_clean].email_verified = True
            return prof

        with self._lock:
            owned_eid = next(
                (
                    eid
                    for eid, owner in self.owner_by_entrepreneur.items()
                    if owner == clean_uid and eid != DEMO_ENTREPRENEUR_ID
                ),
                None,
            )
            acc = self.users_by_email.get(email_clean)
            if not owned_eid and acc and acc.user_id == clean_uid:
                owned_eid = acc.entrepreneur_id

            if not owned_eid or owned_eid == DEMO_ENTREPRENEUR_ID:
                raise PermissionError(
                    "Acceso denegado: la cuenta autenticada no tiene un perfil registrado por el backend."
                )

            prof = self.entrepreneurs_by_id.get(owned_eid)
            if not prof or not prof.data_consent_accepted or not prof.data_consent_version:
                raise PermissionError(
                    "Acceso denegado: la cuenta no registra consentimiento expreso válido."
                )

            if acc:
                acc.email_verified = True
            self.owner_by_entrepreneur[owned_eid] = clean_uid
            return prof

    # --- Vinculación y Registro por WhatsApp en PostgreSQL (Prioridades 2 y 3) ---

    def _consume_provisional_claim_code_atomic(
        self, claim_hash: str, now_dt: datetime
    ) -> Tuple[WhatsappOnboardingDraft, str]:
        """Consume atómicamente un código WA-LINK-XXXXXXXX verificando expiración, uso único e intentos <= 5."""
        if self._is_supabase_active():
            consumed = supabase_adapter.consume_whatsapp_link_challenge_atomic(
                code_sha256=claim_hash,
                expected_type="WA_PROVISIONAL",
                now_dt=now_dt,
            )
            if not consumed:
                raise ValueError(
                    "El código de vinculación de WhatsApp es inválido, ya fue usado, superó el límite de intentos o ha expirado."
                )
            ph = str(consumed.get("phone_sha256") or "").strip()
            session_row = (
                supabase_adapter.get_whatsapp_onboarding_session(ph) if ph else None
            )
            if not ph or not session_row or not session_row.get("consent_accepted"):
                raise ValueError(
                    "La sesión de registro por WhatsApp no existe o no cuenta con consentimiento expreso."
                )
            draft = WhatsappOnboardingDraft(
                phone_sha256=ph,
                phone_masked=str(session_row.get("phone_masked") or ""),
                step=str(session_row.get("step") or "READY_TO_LINK"),
                preferred_language="qu"
                if session_row.get("preferred_language") == "qu"
                else "es",
                full_name=str(session_row.get("full_name") or ""),
                business_name=str(session_row.get("business_name") or ""),
                city=str(session_row.get("city") or "Huamanga"),
                consent_accepted=bool(session_row.get("consent_accepted", False)),
                consent_accepted_at=session_row.get("consent_accepted_at"),
                consent_version=session_row.get("consent_version"),
                provisional_entrepreneur_id=str(
                    session_row.get("provisional_entrepreneur_id")
                    or consumed.get("entrepreneur_id")
                    or ""
                ),
            )
            return draft, ph

        with self._lock:
            ch = self.challenges_by_hash.get(claim_hash)
            if not ch or ch.challenge_type != "WA_PROVISIONAL":
                raise ValueError(
                    "El código de vinculación de WhatsApp es inválido, ya fue usado o ha expirado."
                )
            if ch.used or ch.attempts >= 5 or now_dt >= ch.expires_at:
                if not ch.used and ch.attempts < 5:
                    ch.attempts += 1
                raise ValueError(
                    "El código de vinculación de WhatsApp es inválido, ya fue usado o ha expirado."
                )
            ch.attempts += 1
            ch.used = True
            ch.used_at = now_dt.isoformat()
            ph = ch.phone_sha256
            draft = self.whatsapp_drafts_by_phone_hash.get(ph)
            if not draft or not draft.consent_accepted:
                raise ValueError(
                    "La sesión de registro por WhatsApp no cuenta con consentimiento expreso."
                )
            return draft, ph

    def record_failed_challenge_attempt(self, raw_code: str) -> None:
        """Incrementa el contador de intentos de un código si existe y aún no fue usado (límite 5)."""
        code_clean = (raw_code or "").strip().upper()
        if not code_clean:
            return
        code_hash = hashlib.sha256(code_clean.encode("utf-8")).hexdigest()
        with self._lock:
            ch = self.challenges_by_hash.get(code_hash)
            if ch and not ch.used and ch.attempts < 5:
                ch.attempts += 1

    def generate_whatsapp_link_code(self, entrepreneur_id: str) -> Tuple[str, str]:
        """Genera un código de un solo uso con vigencia de 15 minutos para vincular WhatsApp desde la web."""
        if entrepreneur_id == DEMO_ENTREPRENEUR_ID:
            raise PermissionError(
                "No se permite generar códigos de vinculación para la cuenta de demostración ficticia."
            )
        raw_code = f"VINC-{secrets.token_hex(3).upper()}"
        code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        now_dt = datetime.now(timezone.utc)
        expires_dt = now_dt + timedelta(minutes=15)
        expires_iso = expires_dt.isoformat()

        if self._is_supabase_active():
            supabase_adapter.create_whatsapp_link_challenge(
                {
                    "code_sha256": code_hash,
                    "entrepreneur_id": entrepreneur_id,
                    "phone_sha256": None,
                    "phone_masked": None,
                    "challenge_type": "WEB_TO_WA",
                    "expires_at": expires_iso,
                    "used": False,
                    "attempts": 0,
                }
            )

        with self._lock:
            self.challenges_by_hash[code_hash] = SingleUseChallenge(
                code_sha256=code_hash,
                entrepreneur_id=entrepreneur_id,
                challenge_type="WEB_TO_WA",
                expires_at=expires_dt,
            )
        return raw_code, expires_iso

    def claim_whatsapp_provisional_from_web(
        self, entrepreneur_id: str, claim_code: str
    ) -> EntrepreneurProfileInfo:
        """Vincula un número de WhatsApp que completó el onboarding provisional con una cuenta web autenticada."""
        if entrepreneur_id == DEMO_ENTREPRENEUR_ID:
            raise ValueError("Operación no permitida en la cuenta ficticia de demostración.")
        raw_claim = (claim_code or "").strip().upper()
        claim_hash = hashlib.sha256(raw_claim.encode("utf-8")).hexdigest()
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        draft, ph = self._consume_provisional_claim_code_atomic(
            claim_hash=claim_hash, now_dt=now_dt
        )
        prof = self.get_entrepreneur(entrepreneur_id)

        with self._lock:
            existing_eid = self.phone_hash_to_entrepreneur.get(ph)
            if existing_eid and existing_eid != entrepreneur_id:
                raise ValueError(
                    "Este número de WhatsApp ya se encuentra vinculado a otra cuenta."
                )

        updated = prof.model_copy(
            update={
                "whatsapp_linked": True,
                "phone_masked": draft.phone_masked,
            }
        )

        if self._is_supabase_active():
            supabase_adapter.insert_whatsapp_link_atomic(
                phone_sha256=ph,
                entrepreneur_id=entrepreneur_id,
                phone_masked=draft.phone_masked,
            )
            supabase_adapter.upsert_whatsapp_onboarding_session(
                {
                    "phone_sha256": ph,
                    "phone_masked": draft.phone_masked,
                    "step": "LINKED",
                    "preferred_language": updated.preferred_language,
                    "full_name": updated.full_name,
                    "business_name": updated.business_name,
                    "city": updated.city,
                    "consent_accepted": True,
                    "consent_accepted_at": draft.consent_accepted_at or now_iso,
                    "consent_version": draft.consent_version or DEFAULT_CONSENT_VERSION,
                    "provisional_entrepreneur_id": entrepreneur_id,
                    "updated_at": now_iso,
                }
            )
            self._persist_entrepreneur_and_consent_audit(
                updated,
                action_type="WHATSAPP_LINKED_FROM_PROVISIONAL",
                extra_metadata={"phone_masked": draft.phone_masked},
            )

        with self._lock:
            self.phone_hash_to_entrepreneur[ph] = entrepreneur_id
            self.entrepreneurs_by_id[entrepreneur_id] = updated
            if ph in self.whatsapp_drafts_by_phone_hash:
                self.whatsapp_drafts_by_phone_hash[ph].step = "LINKED"

        return updated

    def get_verified_entrepreneur_by_phone(self, raw_phone: str) -> Optional[str]:
        norm = normalize_whatsapp_phone(raw_phone)
        if not norm:
            return None
        ph = hash_phone_number(norm)
        with self._lock:
            mem_eid = self.phone_hash_to_entrepreneur.get(ph)
        if mem_eid and mem_eid in self.memory_only_eids:
            return mem_eid
        if self._is_supabase_active():
            try:
                link_row = supabase_adapter.get_whatsapp_link_by_phone(ph)
            except SupabasePersistenceError:
                if not self.demo_autolink_enabled():
                    raise
                logging.getLogger("qullqi.whatsapp").exception("Fallo leyendo whatsapp_links")
                return None
            if not link_row:
                return None
            eid = str(link_row.get("entrepreneur_id") or "").strip()
            if not eid or eid == DEMO_ENTREPRENEUR_ID:
                return None
            with self._lock:
                self.phone_hash_to_entrepreneur[ph] = eid
            return eid

        with self._lock:
            eid = self.phone_hash_to_entrepreneur.get(ph)
            if eid and eid != DEMO_ENTREPRENEUR_ID:
                return eid
        return None

    def _load_or_init_onboarding_draft(
        self, ph: str, masked: str, force_reset: bool = False
    ) -> WhatsappOnboardingDraft:
        if not force_reset and self.demo_autolink_enabled():
            with self._lock:
                mem_draft = self.whatsapp_drafts_by_phone_hash.get(ph)
            if mem_draft is not None:
                return mem_draft
        if not force_reset and self._is_supabase_active():
            try:
                row = supabase_adapter.get_whatsapp_onboarding_session(ph)
            except SupabasePersistenceError:
                if not self.demo_autolink_enabled():
                    raise
                row = None
            if row:
                exp_dt: Optional[datetime] = None
                if row.get("claim_expires_at"):
                    try:
                        exp_dt = datetime.fromisoformat(
                            str(row["claim_expires_at"]).replace("Z", "+00:00")
                        )
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        exp_dt = None
                return WhatsappOnboardingDraft(
                    phone_sha256=ph,
                    phone_masked=str(row.get("phone_masked") or masked),
                    step=str(row.get("step") or "AWAITING_LANGUAGE"),
                    preferred_language="qu"
                    if row.get("preferred_language") == "qu"
                    else "es",
                    full_name=str(row.get("full_name") or ""),
                    business_name=str(row.get("business_name") or ""),
                    city=str(row.get("city") or "Huamanga"),
                    consent_accepted=bool(row.get("consent_accepted", False)),
                    consent_accepted_at=row.get("consent_accepted_at"),
                    consent_version=row.get("consent_version"),
                    provisional_entrepreneur_id=str(
                        row.get("provisional_entrepreneur_id") or ""
                    ),
                    claim_code_sha256=str(row.get("claim_code_sha256") or ""),
                    claim_expires_at=exp_dt,
                    last_message_sid=row.get("last_message_sid"),
                )

        with self._lock:
            existing = self.whatsapp_drafts_by_phone_hash.get(ph)
            if existing and not force_reset:
                return existing
            fresh = WhatsappOnboardingDraft(
                phone_sha256=ph,
                phone_masked=masked,
                step="AWAITING_LANGUAGE",
            )
            self.whatsapp_drafts_by_phone_hash[ph] = fresh
            return fresh

    def _save_onboarding_draft(
        self, draft: WhatsappOnboardingDraft, now_iso: str
    ) -> None:
        with self._lock:
            self.whatsapp_drafts_by_phone_hash[draft.phone_sha256] = draft
        if self._is_supabase_active():
          try:
            supabase_adapter.upsert_whatsapp_onboarding_session(
                {
                    "phone_sha256": draft.phone_sha256,
                    "phone_masked": draft.phone_masked,
                    "step": draft.step,
                    "preferred_language": draft.preferred_language,
                    "full_name": draft.full_name or None,
                    "business_name": draft.business_name or None,
                    "city": draft.city,
                    "consent_accepted": draft.consent_accepted,
                    "consent_accepted_at": draft.consent_accepted_at,
                    "consent_version": draft.consent_version,
                    "provisional_entrepreneur_id": draft.provisional_entrepreneur_id
                    or None,
                    "claim_code_sha256": draft.claim_code_sha256 or None,
                    "claim_expires_at": draft.claim_expires_at.isoformat()
                    if draft.claim_expires_at
                    else None,
                    "last_message_sid": draft.last_message_sid,
                    "updated_at": now_iso,
                }
            )
          except SupabasePersistenceError:
            if not self.demo_autolink_enabled():
                raise
            logging.getLogger("qullqi.whatsapp").exception("Fallo guardando sesión de onboarding")


    def handle_unlinked_whatsapp_message(
        self,
        raw_phone: str,
        incoming_body: str,
        message_sid: Optional[str] = None,
    ) -> str:
        """Gestiona la vinculación atómica por código o el onboarding conversacional en PostgreSQL."""
        norm_phone = normalize_whatsapp_phone(raw_phone)
        if not norm_phone:
            return "No se pudo identificar el número remitente de WhatsApp."
        ph = hash_phone_number(norm_phone)
        masked = mask_phone_number(norm_phone)
        text = incoming_body.strip()
        upper = text.upper()
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # 1. ¿Está enviando un código VINC-XXXXXX generado desde su cuenta web?
        vinc_match = re.search(r"\b(VINC-[A-F0-9]{6})\b", upper)
        if vinc_match:
            code_str = vinc_match.group(1)
            code_hash = hashlib.sha256(code_str.encode("utf-8")).hexdigest()
            eid: Optional[str] = None

            if self._is_supabase_active():
                consumed = supabase_adapter.consume_whatsapp_link_challenge_atomic(
                    code_sha256=code_hash,
                    expected_type="WEB_TO_WA",
                    now_dt=now_dt,
                )
                if not consumed:
                    return (
                        "⚠️ El código de vinculación es inválido, ya fue usado, superó el límite de intentos o expiró. "
                        "Genera uno nuevo desde tu panel web de Qullqi Rimay."
                    )
                eid = str(consumed.get("entrepreneur_id") or "").strip()
                if not eid or eid == DEMO_ENTREPRENEUR_ID:
                    return "⚠️ Código de vinculación no válido."
                try:
                    supabase_adapter.insert_whatsapp_link_atomic(
                        phone_sha256=ph,
                        entrepreneur_id=eid,
                        phone_masked=masked,
                    )
                except SupabasePersistenceError:
                    return (
                        "⚠️ Este teléfono o cuenta ya tiene un vínculo de WhatsApp activo."
                    )
            else:
                with self._lock:
                    ch = self.challenges_by_hash.get(code_hash)
                    if (
                        not ch
                        or ch.challenge_type != "WEB_TO_WA"
                        or ch.used
                        or ch.attempts >= 5
                        or now_dt >= ch.expires_at
                    ):
                        if ch and not ch.used and ch.attempts < 5:
                            ch.attempts += 1
                        return (
                            "⚠️ El código de vinculación es inválido, ya fue usado, superó el límite de intentos o expiró. "
                            "Genera uno nuevo desde tu panel web de Qullqi Rimay."
                        )
                    existing_for_phone = self.phone_hash_to_entrepreneur.get(ph)
                    if existing_for_phone and existing_for_phone != ch.entrepreneur_id:
                        ch.attempts += 1
                        return "⚠️ Este número de WhatsApp ya está vinculado a otra cuenta."
                    ch.attempts += 1
                    ch.used = True
                    ch.used_at = now_iso
                    eid = ch.entrepreneur_id
                    self.phone_hash_to_entrepreneur[ph] = eid

            prof = self.get_entrepreneur(eid)
            updated = prof.model_copy(
                update={"whatsapp_linked": True, "phone_masked": masked}
            )
            with self._lock:
                self.entrepreneurs_by_id[eid] = updated
                self.phone_hash_to_entrepreneur[ph] = eid
            self._persist_entrepreneur_and_consent_audit(
                updated,
                action_type="WHATSAPP_LINKED_VIA_CODE",
                extra_metadata={"phone_masked": masked},
            )
            if updated.preferred_language == "qu":
                return (
                    f"✅ ¡Allinmi {updated.full_name}! WhatsApp yupayki ({masked}) "
                    f"'{updated.business_name}' qhatuykiwan tinkisqaña. Kunanmantaqa rantikuykita "
                    "icha gastoykita kaypi qillqamuy."
                )
            return (
                f"✅ ¡Vínculo completado, {updated.full_name}! Tu WhatsApp ({masked}) quedó "
                f"vinculado de forma segura con tu negocio '{updated.business_name}'. "
                "Ya puedes enviarme tus ventas y gastos por aquí."
            )

        # 2. Flujo de Registro Provisional por WhatsApp (persistido en whatsapp_onboarding_sessions)
        is_reset_cmd = upper.strip(" .!¡,") in (
            "REINICIAR", "HOLA", "EMPEZAR", "REGISTRAR", "INICIO", "BUENAS", "BUENOS DÍAS",
            "BUENOS DIAS", "BUENAS TARDES", "BUENAS NOCHES", "MENU", "MENÚ", "AYUDA",
        )
        existing_draft: Any = None
        if self.demo_autolink_enabled():
            existing_draft = self.whatsapp_drafts_by_phone_hash.get(ph)
        if existing_draft is None:
            if self._is_supabase_active():
                try:
                    existing_draft = supabase_adapter.get_whatsapp_onboarding_session(ph)
                except SupabasePersistenceError:
                    if not self.demo_autolink_enabled():
                        raise
                    existing_draft = None
            else:
                existing_draft = self.whatsapp_drafts_by_phone_hash.get(ph)

        if existing_draft is None or is_reset_cmd:
            draft = self._load_or_init_onboarding_draft(
                ph=ph, masked=masked, force_reset=True
            )
            draft.last_message_sid = message_sid
            self._save_onboarding_draft(draft, now_iso)
            return (
                "🌱 *¡Rimaykullayki! Bienvenida a Qullqi Rimay*\n"
                "Te ayudo a anotar tus ventas y gastos por WhatsApp y te explico, con tus propios números, "
                "cuánto le queda a tu negocio y cuánto es tuyo.\n\n"
                "Tu registro toma 1 minuto (3 pasos).\n"
                "*Paso 1 de 3 — Elige tu idioma / Rimaynikita akllay:*\n"
                "• Escribe *1* para *Español*\n"
                "• Escribe *2* para *Quechua Ayacuchano (Chanka)*"
            )

        draft = self._load_or_init_onboarding_draft(
            ph=ph, masked=masked, force_reset=False
        )
        draft.last_message_sid = message_sid

        if draft.step == "AWAITING_LANGUAGE":
            low = text.lower().strip(" .!¡")
            if low in ("1", "1️⃣", "uno", "español", "espanol", "es", "castellano") or "espa" in low:
                draft.preferred_language = "es"
                draft.step = "AWAITING_NAME_BUSINESS"
                self._save_onboarding_draft(draft, now_iso)
                return (
                    "👍 Idioma configurado: *Español*.\n\n"
                    "*Paso 2 de 3 — Datos esenciales de tu negocio:*\n"
                    "Escríbeme en un solo mensaje tu *nombre*, el *nombre de tu negocio o puesto* y tu *ciudad*, separados por guion (-).\n\n"
                    "Ejemplo:\n*Juana Mendoza - Verdulería Sumaq - Huamanga*"
                )
            if low in ("2", "2️⃣", "dos", "iskay", "quechua", "runasimi", "qu") or "quechua" in low:
                draft.preferred_language = "qu"
                draft.step = "AWAITING_NAME_BUSINESS"
                self._save_onboarding_draft(draft, now_iso)
                return (
                    "👍 Rimayniki: *Quechua Ayacuchano (Chanka)*.\n\n"
                    "*Paso 2 de 3 — Qhatuykipa sutin:*\n"
                    "Qillqamuway *Sutikita*, *Negocioykipa sutinta* hinaspa *Llaqtaykita* guionwan (`-`) rakispa.\n"
                    "Kayhina: *Juana Mendoza - Verdulería Sumaq - Huamanga*"
                )
            self._save_onboarding_draft(draft, now_iso)
            return (
                "Por favor responde *1* para Español o *2* para Quechua Ayacuchano / "
                "Ama hina kaspa *1* (Español) icha *2* (Quechua) kutichimuway."
            )

        if draft.step == "AWAITING_NAME_BUSINESS":
            parts = [p.strip() for p in re.split(r"[-|,]", text) if p.strip()]
            if len(parts) < 2 or len(parts[0]) < 2:
                self._save_onboarding_draft(draft, now_iso)
                if draft.preferred_language == "qu":
                    return (
                        "Ama hina kaspa sutikita hinaspa negocioykipa sutinta guionwan (`-`) qillqamuway.\n"
                        "Kayhina: *Juana Mendoza - Verdulería Sumaq - Huamanga*"
                    )
                return (
                    "Por favor escribe al menos tu nombre y el nombre de tu negocio separados por guion (`-`).\n"
                    "Ejemplo: *Juana Mendoza - Verdulería Sumaq - Huamanga*"
                )
            draft.full_name = parts[0]
            draft.business_name = parts[1]
            draft.city = parts[2] if len(parts) >= 3 else "Huamanga"
            draft.step = "AWAITING_CONSENT"
            self._save_onboarding_draft(draft, now_iso)
            if draft.preferred_language == "qu":
                return (
                    f"📝 *Paso 3 de 3 — Willakuykunata waqaychanapaq autorización ({DEFAULT_CONSENT_VERSION}):*\n"
                    f"Sutiyki: *{draft.full_name}* | Qhatuyki: *{draft.business_name}* ({draft.city}).\n\n"
                    "¿Autorizankichu Qullqi Rimaypi qullqi yupaykikunata waqaychanaykupaq? "
                    "(Jayk'appas hark'ayta atinki). Kutichimuway *«ARI»* (o *«ACEPTO»*)."
                )
            return (
                f"📝 *Paso 3 de 3 — Consentimiento de Tratamiento de Datos ({DEFAULT_CONSENT_VERSION}):*\n"
                f"Titular: *{draft.full_name}* | Negocio: *{draft.business_name}* ({draft.city}).\n\n"
                "¿Autorizas el tratamiento de tus registros operativos en Qullqi Rimay para generar "
                "tus resúmenes semanales y perfil financiero (revocable en cualquier momento)?\n"
                "Tus datos son tuyos: no se comparten con nadie sin tu permiso.\n\n"
                "Escribe *ACEPTO* para terminar tu registro."
            )

        if draft.step == "AWAITING_CONSENT":
            if upper.strip(" .!¡,") not in (
                "ACEPTO", "SI ACEPTO", "SÍ ACEPTO", "SI, ACEPTO", "SÍ, ACEPTO",
                "SI", "SÍ", "ARI", "ALLINMI", "ACEPTAR",
            ):
                self._save_onboarding_draft(draft, now_iso)
                if draft.preferred_language == "qu":
                    return "Qallarinapaq kutichimuway *«ARI»* icha *«ACEPTO»*."
                return "Para continuar con tu registro seguro, responde *«ACEPTO»*."

            draft.consent_accepted = True
            draft.consent_accepted_at = now_iso
            draft.consent_version = DEFAULT_CONSENT_VERSION
            draft.provisional_entrepreneur_id = f"emp-wa-{uuid.uuid4().hex[:8]}"
            raw_claim = f"WA-LINK-{secrets.token_hex(4).upper()}"
            claim_hash = hashlib.sha256(raw_claim.encode("utf-8")).hexdigest()
            expires_dt = now_dt + timedelta(minutes=15)
            draft.claim_code_plain_once = raw_claim
            draft.claim_code_sha256 = claim_hash
            draft.claim_expires_at = expires_dt
            draft.step = "READY_TO_LINK"

            self._save_onboarding_draft(draft, now_iso)

            if self._is_supabase_active():
              try:
                supabase_adapter.create_whatsapp_link_challenge(
                    {
                        "code_sha256": claim_hash,
                        "entrepreneur_id": draft.provisional_entrepreneur_id,
                        "phone_sha256": ph,
                        "phone_masked": masked,
                        "challenge_type": "WA_PROVISIONAL",
                        "expires_at": expires_dt.isoformat(),
                        "used": False,
                        "attempts": 0,
                    }
                )
              except SupabasePersistenceError:
                if not self.demo_autolink_enabled():
                    raise
                logging.getLogger("qullqi.whatsapp").exception("Fallo creando challenge")

            with self._lock:
                self.challenges_by_hash[claim_hash] = SingleUseChallenge(
                    code_sha256=claim_hash,
                    entrepreneur_id=draft.provisional_entrepreneur_id,
                    challenge_type="WA_PROVISIONAL",
                    phone_sha256=ph,
                    phone_masked=masked,
                    expires_at=expires_dt,
                )

            if self.demo_autolink_enabled():
                return self._autolink_demo_account(draft, ph, masked, now_iso)

            if draft.preferred_language == "qu":
                return (
                    f"🔐 *¡Registro provisional waqaychasqaña, {draft.full_name}!*\n"
                    f"Qhatuyki: *{draft.business_name}* ({draft.city})\n\n"
                    "Cuenta Supabase Auth webpi hunt'achinaykipaq kay código único (15 min) churay:\n"
                    f"👉 Código de vinculación: *{raw_claim}*\n"
                    f"👉 Enlace web: `/?wa_claim={raw_claim}`\n\n"
                    "Webpi verificaptiykiña, kay WhatsAppmanta rantikuykikunata qillqamunki."
                )
            return (
                f"🔐 *¡Progreso guardado en Qullqi Rimay, {draft.full_name}!*\n"
                f"Negocio: *{draft.business_name}* ({draft.city})\n\n"
                "Para proteger tu cuenta sin pedirte contraseñas por WhatsApp, completa la verificación "
                "en la web ingresando este código único (válido por 15 minutos):\n"
                f"👉 Código de vinculación: *{raw_claim}*\n"
                f"👉 Enlace directo: `/?wa_claim={raw_claim}`\n\n"
                "Una vez vinculada tu cuenta en la web, podrás registrar y consultar tus movimientos desde este WhatsApp."
            )

        self._save_onboarding_draft(draft, now_iso)
        if draft.preferred_language == "qu":
            return (
                f"🔐 *{draft.full_name}*, registro provisionalniki suyachkanmi.\n"
                "Webpi cuenta Supabase Auth hunt'achiy código únicoykiwan, icha *REINICIAR* qillqamuway."
            )
        return (
            f"🔐 *{draft.full_name}*, tu registro provisional está listo para vincularse en la web.\n"
            "Completa la verificación con tu código único o escribe *REINICIAR* para generar uno nuevo."
        )

    def _autolink_demo_account(
        self, draft: "WhatsappOnboardingDraft", ph: str, masked: str, now_iso: str
    ) -> str:
        """Modo demo: crea la cuenta y vincula el WhatsApp al instante (solo en memoria)."""
        eid = draft.provisional_entrepreneur_id or f"emp-wa-{uuid.uuid4().hex[:8]}"
        city = (draft.city or "Huamanga").strip()
        prof = EntrepreneurProfileInfo(
            id=eid,
            full_name=draft.full_name,
            business_name=draft.business_name,
            trade_sector=draft.trade_sector,
            market_location=city,
            city=city,
            region="Ayacucho",
            phone_masked=masked,
            goal_title="Juntar un fondo para hacer crecer tu negocio",
            goal_target_pen=800.0,
            goal_weekly_target_pen=100.0,
            goal_weeks=8,
            active_week=1,
            preferred_language=draft.preferred_language,
            owner_user_id=None,
            data_consent_accepted=True,
            data_consent_accepted_at=draft.consent_accepted_at or now_iso,
            data_consent_version=draft.consent_version or DEFAULT_CONSENT_VERSION,
            whatsapp_linked=True,
        )
        with self._lock:
            self.memory_only_eids.add(eid)
            self.entrepreneurs_by_id[eid] = prof
            self.phone_hash_to_entrepreneur[ph] = eid
            self.chat_history_by_eid.setdefault(eid, [])
            draft.step = "LINKED"
            self.whatsapp_drafts_by_phone_hash[ph] = draft
        first = (draft.full_name.split() or ["casera"])[0]
        if draft.preferred_language == "qu":
            return (
                f"✅ *¡Allinmi, {first}! Cuentayki listoña.*\n"
                f"Qhatuyki: *{draft.business_name}* ({city})\n"
                "Metayki: 8 semanapi *S/ 800* huñunaykipaq (semanapi S/ 100).\n\n"
                + self.whatsapp_menu_text(prof)
            )
        return (
            f"✅ *¡Listo, {first}! Tu cuenta ya está creada.*\n"
            f"Negocio: *{draft.business_name}* ({city})\n"
            "Tu meta inicial: juntar *S/ 800 en 8 semanas* (S/ 100 por semana) para hacer crecer tu negocio.\n\n"
            + self.whatsapp_menu_text(prof)
        )

    @staticmethod
    def whatsapp_menu_text(prof: EntrepreneurProfileInfo) -> str:
        if prof.preferred_language == "qu":
            return (
                "📋 *Imatam ruwasaq:*\n"
                "1️⃣ Rantikusqaykita icha gastoykita qillqamuway, kayhina:\n"
                "   • *Rantikurqani 80 soles papata*\n"
                "   • *gasté 12 en pasaje*\n"
                "2️⃣ Chaymanta *ARI* (waqaychanaypaq) icha *MANAM* (pichanaypaq) kutichimuway.\n"
                "3️⃣ *RESUMEN* — semanaykita hinaspa metaykita qawanaykipaq.\n"
                "4️⃣ *MANAM YACHANICHU* — aswan facilta willanaypaq.\n"
                "5️⃣ *IDIOMA ESPAÑOL* — castellanoman tikranaypaq.\n"
                "6️⃣ *MENÚ* — kayta yapamanta qawanaykipaq.\n"
                "7️⃣ *CUADRE* — qullqiykita yupanapaq (gastos hormiga).\n"
                "8️⃣ *PUNTOS* — rachaykita, puntosniykita qawanaykipaq.\n"
                "9️⃣ *ASESOR* — BCP asesorwan icha Agente Móvilwan rimanaykipaq."
            )
        return (
            "📋 *¿Qué puedes hacer aquí?*\n"
            "1️⃣ Escríbeme tus ventas o gastos como hablas, por ejemplo:\n"
            "   • *Vendí 50 soles de fruta*\n"
            "   • *Gasté 12 en pasaje*\n"
            "2️⃣ Te muestro lo que entendí y respondes *SÍ* para guardarlo o *NO* para borrarlo.\n"
            "3️⃣ *RESUMEN* — cuánto ganaste esta semana y cómo vas con tu meta.\n"
            "4️⃣ *NO ENTENDÍ* — te lo explico más fácil, con tus propios números.\n"
            "5️⃣ *IDIOMA QUECHUA* — cambiar a quechua ayacuchano.\n"
            "6️⃣ *MENÚ* — ver estas opciones otra vez.\n"
            "7️⃣ *CUADRE* — cuadra tu caja y descubre tus gastos hormiga 🐜\n"
            "8️⃣ *PUNTOS* — tu racha 🔥, tus Qullqi puntos ⭐ y tu nivel 🌱\n"
            "9️⃣ *ASESOR* — hablar con un asesor BCP o pedir el Agente Móvil 🚚\n\n"
            "Empieza ahora: cuéntame qué vendiste hoy 🙂"
        )

    def demo_unlink_phone(self, raw_phone: str) -> bool:
        """Modo demo: desvincula un teléfono creado en memoria para repetir el registro."""
        norm = normalize_whatsapp_phone(raw_phone)
        if not norm:
            return False
        ph = hash_phone_number(norm)
        with self._lock:
            eid = self.phone_hash_to_entrepreneur.get(ph)
            if not eid or eid not in self.memory_only_eids:
                return False
            self.phone_hash_to_entrepreneur.pop(ph, None)
            self.whatsapp_drafts_by_phone_hash.pop(ph, None)
        return True

    def get_provisional_draft_by_claim_code(
        self, claim_code: str
    ) -> Optional[WhatsappOnboardingDraft]:
        raw_claim = (claim_code or "").strip().upper()
        if not raw_claim:
            return None
        claim_hash = hashlib.sha256(raw_claim.encode("utf-8")).hexdigest()
        now_dt = datetime.now(timezone.utc)

        if self._is_supabase_active():
            ch_row = supabase_adapter.get_whatsapp_link_challenge(claim_hash)
            if (
                not ch_row
                or ch_row.get("used")
                or int(ch_row.get("attempts") or 0) >= 5
                or ch_row.get("challenge_type") != "WA_PROVISIONAL"
            ):
                return None
            exp_str = str(ch_row.get("expires_at") or "")
            try:
                exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now_dt >= exp_dt:
                    return None
            except ValueError:
                return None
            ph = str(ch_row.get("phone_sha256") or "").strip()
            if not ph:
                return None
            return self._load_or_init_onboarding_draft(
                ph=ph, masked=str(ch_row.get("phone_masked") or ""), force_reset=False
            )

        with self._lock:
            ch = self.challenges_by_hash.get(claim_hash)
            if (
                not ch
                or ch.challenge_type != "WA_PROVISIONAL"
                or ch.used
                or ch.attempts >= 5
                or now_dt >= ch.expires_at
            ):
                return None
            return self.whatsapp_drafts_by_phone_hash.get(ch.phone_sha256)

    def _sync_weekly_goals_snapshot(
        self, entrepreneur_id: Optional[str] = None
    ) -> None:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if not self._remote_for(target_eid):
            return
        prof = self.get_entrepreneur(target_eid)
        movs = self.list_movements(entrepreneur_id=target_eid)
        weekly_summaries = compute_weekly_summaries(movs, prof)
        supabase_adapter.sync_weekly_goals(target_eid, weekly_summaries)

    def reset_to_demo_seed(self) -> None:
        from app.services import engagement as _eng
        _eng.reset_all()
        with self._lock:
            self._init_memory_state()
        if self._is_supabase_active():
            weekly_summaries = compute_weekly_summaries(
                self.movements, self.entrepreneur
            )
            supabase_adapter.reset_demo_in_supabase(
                self.entrepreneur,
                self.movements,
                self.chat_history,
                weekly_summaries,
            )

    def is_message_sid_processed(
        self,
        message_sid: str,
        sender_phone: str = "",
        raw_body: str = "",
        entrepreneur_id: Optional[str] = None,
    ) -> bool:
        """Comprueba y registra MessageSid con idempotencia segura.
        Para teléfonos no vinculados, `entrepreneur_id` es `None` (jamás 'rosa-huamanga-001').
        """
        if not message_sid:
            return False
        norm_phone = normalize_whatsapp_phone(sender_phone)
        phone_hash = hash_phone_number(norm_phone or sender_phone)
        if self._remote_for(entrepreneur_id) and not (
            self.demo_autolink_enabled() and entrepreneur_id is None
        ):
            try:
                return supabase_adapter.check_and_record_message_sid(
                    message_sid=message_sid,
                    entrepreneur_id=entrepreneur_id,
                    sender_phone_hash=phone_hash,
                    raw_body=raw_body,
                )
            except SupabasePersistenceError:
                if not self.demo_autolink_enabled():
                    raise
                logging.getLogger("qullqi.whatsapp").exception("Fallo idempotencia MessageSid")
        with self._lock:
            if message_sid in self.processed_message_sids:
                return True
            self.processed_message_sids.add(message_sid)
            return False

    def list_movements(
        self,
        week_number: Optional[int] = None,
        status: Optional[str] = None,
        entrepreneur_id: Optional[str] = None,
    ) -> List[MovementRecord]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if self._remote_for(target_eid):
            remote = supabase_adapter.fetch_movements(
                entrepreneur_id=target_eid,
                week_number=week_number,
                status=status,
            )
            return remote if remote is not None else []
        with self._lock:
            items = [m for m in self.movements if m.entrepreneur_id == target_eid]
        if week_number is not None:
            items = [m for m in items if m.week_number == week_number]
        if status is not None:
            items = [m for m in items if m.status == status]
        return items

    def add_movement(
        self,
        week_number: int,
        movement_type: str,
        amount_pen: float,
        category: str,
        description: str,
        raw_message: str,
        source_channel: str = "WHATSAPP_SIMULATOR",
        ai_confidence: float = 0.96,
        auto_confirm: bool = False,
        entrepreneur_id: Optional[str] = None,
    ) -> MovementRecord:
        target_eid = entrepreneur_id or self.entrepreneur.id
        now_iso = datetime.now(timezone.utc).isoformat()
        status = "CONFIRMADO" if auto_confirm else "PENDIENTE"
        confirmed_at = now_iso if auto_confirm else None
        record = MovementRecord(
            id=f"mov-{uuid.uuid4().hex[:8]}",
            entrepreneur_id=target_eid,
            week_number=week_number,
            movement_type=movement_type,  # type: ignore[arg-type]
            amount_pen=round(float(amount_pen), 2),
            category=category,
            description=description,
            raw_message=raw_message,
            source_channel=source_channel,
            ai_confidence=ai_confidence,
            status=status,  # type: ignore[arg-type]
            created_at=now_iso,
            confirmed_at=confirmed_at,
        )
        if self._remote_for(target_eid):
            supabase_adapter.sync_movement(record)
            self._sync_weekly_goals_snapshot(target_eid)
            supabase_adapter.log_audit_event(
                entrepreneur_id=target_eid,
                action_type="CREATE_MOVEMENT",
                entity_type="movement",
                entity_id=record.id,
                metadata={"status": record.status, "amount_pen": record.amount_pen},
            )
        with self._lock:
            self.movements.append(record)
        return record

    def update_movement_status(
        self,
        movement_id: str,
        new_status: str,
        entrepreneur_id: Optional[str] = None,
    ) -> Optional[MovementRecord]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        now_iso = datetime.now(timezone.utc).isoformat()
        target: Optional[MovementRecord] = None
        if self._remote_for(target_eid):
            updates = {"status": new_status}
            if new_status == "CONFIRMADO":
                updates["confirmed_at"] = now_iso
            target = supabase_adapter.patch_movement_for_entrepreneur(
                movement_id=movement_id,
                entrepreneur_id=target_eid,
                updates=updates,
            )
            if target is not None:
                self._sync_weekly_goals_snapshot(target_eid)
                supabase_adapter.log_audit_event(
                    entrepreneur_id=target_eid,
                    action_type=f"MOVEMENT_{new_status}",
                    entity_type="movement",
                    entity_id=target.id,
                    metadata={"new_status": new_status},
                )
            return target

        with self._lock:
            for idx, mov in enumerate(self.movements):
                if mov.id == movement_id and mov.entrepreneur_id == target_eid:
                    updated = mov.model_copy(
                        update={
                            "status": new_status,
                            "confirmed_at": now_iso
                            if new_status == "CONFIRMADO"
                            else mov.confirmed_at,
                        }
                    )
                    self.movements[idx] = updated
                    target = updated
                    break
        return target

    def confirm_all_pending(
        self,
        week_number: Optional[int] = None,
        entrepreneur_id: Optional[str] = None,
    ) -> List[MovementRecord]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._remote_for(target_eid):
            pending = self.list_movements(
                week_number=week_number, status="PENDIENTE", entrepreneur_id=target_eid
            )
            confirmed_remote: List[MovementRecord] = []
            for m in pending:
                updated = supabase_adapter.patch_movement_for_entrepreneur(
                    movement_id=m.id,
                    entrepreneur_id=target_eid,
                    updates={"status": "CONFIRMADO", "confirmed_at": now_iso},
                )
                if updated is not None:
                    confirmed_remote.append(updated)
                    supabase_adapter.log_audit_event(
                        entrepreneur_id=target_eid,
                        action_type="MOVEMENT_CONFIRMADO",
                        entity_type="movement",
                        entity_id=updated.id,
                        metadata={"new_status": "CONFIRMADO"},
                    )
            if confirmed_remote:
                self._sync_weekly_goals_snapshot(target_eid)
            return confirmed_remote

        confirmed_list: List[MovementRecord] = []
        with self._lock:
            for idx, mov in enumerate(self.movements):
                if (
                    mov.entrepreneur_id == target_eid
                    and mov.status == "PENDIENTE"
                    and (week_number is None or mov.week_number == week_number)
                ):
                    updated = mov.model_copy(
                        update={"status": "CONFIRMADO", "confirmed_at": now_iso}
                    )
                    self.movements[idx] = updated
                    confirmed_list.append(updated)
        return confirmed_list

    def discard_all_pending(
        self,
        week_number: Optional[int] = None,
        entrepreneur_id: Optional[str] = None,
    ) -> List[MovementRecord]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if self._remote_for(target_eid):
            pending = self.list_movements(
                week_number=week_number, status="PENDIENTE", entrepreneur_id=target_eid
            )
            discarded_remote: List[MovementRecord] = []
            for m in pending:
                updated = supabase_adapter.patch_movement_for_entrepreneur(
                    movement_id=m.id,
                    entrepreneur_id=target_eid,
                    updates={"status": "DESCARTADO"},
                )
                if updated is not None:
                    discarded_remote.append(updated)
                    supabase_adapter.log_audit_event(
                        entrepreneur_id=target_eid,
                        action_type="MOVEMENT_DESCARTADO",
                        entity_type="movement",
                        entity_id=updated.id,
                        metadata={"new_status": "DESCARTADO"},
                    )
            if discarded_remote:
                self._sync_weekly_goals_snapshot(target_eid)
            return discarded_remote

        discarded_list: List[MovementRecord] = []
        with self._lock:
            for idx, mov in enumerate(self.movements):
                if (
                    mov.entrepreneur_id == target_eid
                    and mov.status == "PENDIENTE"
                    and (week_number is None or mov.week_number == week_number)
                ):
                    updated = mov.model_copy(update={"status": "DESCARTADO"})
                    self.movements[idx] = updated
                    discarded_list.append(updated)
        return discarded_list

    def add_chat_bubble(
        self, bubble: ChatMessageBubble, entrepreneur_id: Optional[str] = None
    ) -> ChatMessageBubble:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if self._remote_for(target_eid):
            supabase_adapter.sync_chat_bubble(target_eid, bubble)
        with self._lock:
            self.chat_history_by_eid.setdefault(target_eid, []).append(bubble)
        return bubble

    def list_chat_history(
        self, entrepreneur_id: Optional[str] = None
    ) -> List[ChatMessageBubble]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if self._remote_for(target_eid):
            remote = supabase_adapter.fetch_chat_history(target_eid)
            return remote if remote is not None else []
        with self._lock:
            return list(self.chat_history_by_eid.get(target_eid, []))

    def create_consent(
        self,
        recipient_entity: str,
        purpose: str,
        evidence_hash: str,
        expires_in_seconds: Optional[int] = None,
        entrepreneur_id: Optional[str] = None,
    ) -> ConsentRecord:
        target_eid = entrepreneur_id or self.entrepreneur.id
        prof = self.get_entrepreneur(target_eid)
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        delta = (
            timedelta(seconds=expires_in_seconds)
            if expires_in_seconds is not None
            else timedelta(days=7)
        )
        expires_iso = (now_dt + delta).isoformat()
        consent_id = f"cons-{secrets.token_hex(6)}"
        share_token = f"qr-tok-{secrets.token_urlsafe(18)}"
        token_sha256 = hashlib.sha256(share_token.encode("utf-8")).hexdigest()
        statement = (
            f"Yo, {prof.full_name}, autorizo de manera libre, previa, expresa e informada "
            f"a compartir mi Perfil Financiero Operativo de 8 semanas con '{recipient_entity}' "
            f"únicamente para la finalidad: '{purpose}'. Comprendo que puedo revocar este acceso en cualquier momento."
        )
        record = ConsentRecord(
            id=consent_id,
            entrepreneur_id=target_eid,
            recipient_entity=recipient_entity,
            purpose=purpose,
            consent_statement=statement,
            share_token=share_token,
            token_sha256=token_sha256,
            evidence_hash=evidence_hash,
            status="ACTIVO",
            granted_at=now_iso,
            expires_at=expires_iso,
        )
        if self._is_supabase_active():
            supabase_adapter.sync_consent(record)
            supabase_adapter.log_audit_event(
                entrepreneur_id=target_eid,
                action_type="GRANT_CONSENT",
                entity_type="profile_consent",
                entity_id=record.id,
                metadata={
                    "recipient_entity": recipient_entity,
                    "token_sha256": token_sha256,
                },
            )
        with self._lock:
            self.consents.insert(0, record)
        return record

    def revoke_consent(
        self,
        consent_id: str,
        reason: str,
        entrepreneur_id: Optional[str] = None,
    ) -> Optional[ConsentRecord]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        now_iso = datetime.now(timezone.utc).isoformat()
        target: Optional[ConsentRecord] = None
        if self._is_supabase_active():
            target = supabase_adapter.patch_consent_for_entrepreneur(
                consent_id=consent_id,
                entrepreneur_id=target_eid,
                updates={
                    "status": "REVOCADO",
                    "revoked_at": now_iso,
                    "revocation_reason": reason,
                },
            )
            if target is not None:
                supabase_adapter.log_audit_event(
                    entrepreneur_id=target_eid,
                    action_type="REVOKE_CONSENT",
                    entity_type="profile_consent",
                    entity_id=target.id,
                    metadata={"reason": reason},
                )
            return target

        with self._lock:
            for idx, c in enumerate(self.consents):
                if c.id == consent_id and c.entrepreneur_id == target_eid:
                    updated = c.model_copy(
                        update={
                            "status": "REVOCADO",
                            "revoked_at": now_iso,
                            "revocation_reason": reason,
                        }
                    )
                    self.consents[idx] = updated
                    target = updated
                    break
        return target

    def list_consents(self, entrepreneur_id: Optional[str] = None) -> List[ConsentRecord]:
        target_eid = entrepreneur_id or self.entrepreneur.id
        if self._is_supabase_active():
            remote = supabase_adapter.fetch_consents(target_eid)
            return remote if remote is not None else []
        with self._lock:
            return [c for c in self.consents if c.entrepreneur_id == target_eid]

    def get_consent_by_token(self, share_token: str) -> Optional[ConsentRecord]:
        if not share_token or not share_token.strip():
            return None
        target_hash = hashlib.sha256(share_token.strip().encode("utf-8")).hexdigest()
        if self._is_supabase_active():
            remote_consent = supabase_adapter.fetch_consent_by_token_hash(target_hash)
            if remote_consent is not None and hmac.compare_digest(
                remote_consent.token_sha256, target_hash
            ):
                return remote_consent
            return None
        with self._lock:
            for c in self.consents:
                if c.token_sha256 and hmac.compare_digest(c.token_sha256, target_hash):
                    return c
        return None

    def mark_consent_expired_if_needed(self, consent: ConsentRecord) -> ConsentRecord:
        if consent.status != "ACTIVO" or not consent.expires_at:
            return consent
        try:
            exp_dt = datetime.fromisoformat(consent.expires_at.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return consent

        if datetime.now(timezone.utc) >= exp_dt:
            if self._is_supabase_active():
                updated_remote = supabase_adapter.patch_consent_for_entrepreneur(
                    consent_id=consent.id,
                    entrepreneur_id=consent.entrepreneur_id,
                    updates={"status": "EXPIRADO"},
                )
                if updated_remote is not None:
                    consent = updated_remote
            with self._lock:
                for idx, c in enumerate(self.consents):
                    if c.id == consent.id:
                        self.consents[idx] = c.model_copy(update={"status": "EXPIRADO"})
                        consent = self.consents[idx]
                        break
        return consent


store = InMemoryStore(use_supabase=True, use_enriched_demo=False)

"""Repositorio persistente para Supabase PostgreSQL vía PostgREST (`httpx`).

Garantías de seguridad y persistencia:
1. `SUPABASE_SERVICE_ROLE_KEY` jamás se expone al cliente web (`VITE_*`).
2. Cuando `USE_EXTERNAL_SUPABASE=true`, PostgreSQL es la única fuente de verdad:
   - NO existe circuito de caída silenciosa a memoria (`_offline_circuit_open` eliminado).
   - Si PostgreSQL rechaza una operación o falla la conexión de red, se lanza `SupabasePersistenceError`
     (traducido a HTTP 503 Service Unavailable), sin responder éxito jamás ante un fallo de persistencia.
3. Fuente de verdad en PostgreSQL para `entrepreneurs`, `movements`, `weekly_goals`, `profile_consents`,
   `chat_messages`, `processed_messages`, `audit_logs`, `whatsapp_links`, `whatsapp_onboarding_sessions`
   y `whatsapp_link_challenges`.
4. CERO almacenamiento de hashes de contraseñas ni secretos de autenticación en `audit_logs`.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
import httpx

from app.models import (
    ChatMessageBubble,
    ConsentRecord,
    EntrepreneurProfileInfo,
    MovementRecord,
    WeeklySummaryItem,
)


class SupabasePersistenceError(RuntimeError):
    """Error lanzado cuando USE_EXTERNAL_SUPABASE=true y PostgreSQL rechaza una operación o no está disponible."""


ENTREPRENEUR_BASE_DB_COLUMNS = {
    "id",
    "full_name",
    "business_name",
    "trade_sector",
    "market_location",
    "city",
    "region",
    "phone_masked",
    "goal_title",
    "goal_target_pen",
    "goal_weekly_target_pen",
    "goal_weeks",
    "active_week",
}

ENTREPRENEUR_EXTENDED_DB_COLUMNS = ENTREPRENEUR_BASE_DB_COLUMNS | {
    "owner_user_id",
    "preferred_language",
    "data_consent_accepted",
    "data_consent_accepted_at",
    "data_consent_version",
    "whatsapp_linked",
}


def _to_db_entrepreneur_payload(
    profile: EntrepreneurProfileInfo, include_extended: bool = True
) -> Dict[str, Any]:
    raw = profile.model_dump()
    allowed = (
        ENTREPRENEUR_EXTENDED_DB_COLUMNS
        if include_extended
        else ENTREPRENEUR_BASE_DB_COLUMNS
    )
    return {k: v for k, v in raw.items() if k in allowed}


def _normalize_movement_row(row: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(row)
    if "created_at" not in data and "occurred_at" in data:
        data["created_at"] = data.pop("occurred_at")
    return data


def _normalize_chat_row(row: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(row)
    if "text" not in data and "content" in data:
        data["text"] = data.pop("content")
    return data


class SupabaseAdapter:
    @property
    def url(self) -> str:
        return os.getenv(
            "SUPABASE_URL", "https://oqbfuyxoclufkikaddoj.supabase.co"
        ).strip().rstrip("/")

    @property
    def service_key(self) -> str:
        return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    @property
    def is_enabled(self) -> bool:
        use_ext = os.getenv("USE_EXTERNAL_SUPABASE", "false").strip().lower() == "true"
        if not use_ext:
            return False
        key = self.service_key
        if (
            not self.url
            or not key
            or key.startswith("tu_")
            or key.startswith("REEMPLAZAR_")
        ):
            raise SupabasePersistenceError(
                "USE_EXTERNAL_SUPABASE=true pero las credenciales SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY no están configuradas válidamente."
            )
        return True

    def _headers(self, prefer: str = "return=representation") -> Dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    def _raise_persistence_error(self, operation: str, exc: Exception) -> None:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            body_preview = exc.response.text[:300]
            raise SupabasePersistenceError(
                f"PostgreSQL/Supabase rechazó la operación '{operation}' (HTTP {exc.response.status_code}): {body_preview}"
            ) from exc
        raise SupabasePersistenceError(
            f"Fallo de conexión con Supabase PostgreSQL durante '{operation}': {exc}"
        ) from exc

    def ensure_seed_data(
        self,
        entrepreneur: EntrepreneurProfileInfo,
        seed_movements: List[MovementRecord],
        seed_chat: List[ChatMessageBubble],
        weekly_summaries: Optional[List[WeeklySummaryItem]] = None,
    ) -> None:
        """Carga idempotente (sin duplicar ni sobrescribir ni borrar registros existentes) en Supabase."""
        if not self.is_enabled:
            return
        try:
            with httpx.Client(timeout=10.0) as client:
                r1 = client.post(
                    f"{self.url}/rest/v1/entrepreneurs?on_conflict=id",
                    headers=self._headers("resolution=ignore-duplicates,return=minimal"),
                    json=_to_db_entrepreneur_payload(
                        entrepreneur, include_extended=False
                    ),
                )
                r1.raise_for_status()
                r2 = client.post(
                    f"{self.url}/rest/v1/movements?on_conflict=id",
                    headers=self._headers("resolution=ignore-duplicates,return=minimal"),
                    json=[m.model_dump() for m in seed_movements],
                )
                r2.raise_for_status()
                r3 = client.post(
                    f"{self.url}/rest/v1/chat_messages?on_conflict=id",
                    headers=self._headers("resolution=ignore-duplicates,return=minimal"),
                    json=[
                        {
                            **b.model_dump(),
                            "entrepreneur_id": entrepreneur.id,
                        }
                        for b in seed_chat
                    ],
                )
                r3.raise_for_status()
            if weekly_summaries:
                self.sync_weekly_goals(entrepreneur.id, weekly_summaries)
        except Exception as exc:
            self._raise_persistence_error("ensure_seed_data", exc)

    def upsert_entrepreneur(self, entrepreneur: EntrepreneurProfileInfo) -> None:
        if not self.is_enabled:
            return
        if entrepreneur.id == "rosa-huamanga-001" and entrepreneur.owner_user_id is not None:
            raise SupabasePersistenceError(
                "Prohibido asignar owner_user_id a la cuenta ficticia 'rosa-huamanga-001'."
            )
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/entrepreneurs?on_conflict=id",
                    headers=self._headers("resolution=merge-duplicates,return=minimal"),
                    json=_to_db_entrepreneur_payload(
                        entrepreneur, include_extended=True
                    ),
                )
                resp.raise_for_status()
        except Exception as exc:
            self._raise_persistence_error("upsert_entrepreneur", exc)

    def fetch_entrepreneurs(self) -> List[Dict[str, Any]]:
        if not self.is_enabled:
            return []
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/entrepreneurs",
                    params={"order": "created_at.asc"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            self._raise_persistence_error("fetch_entrepreneurs", exc)
            return []

    def fetch_entrepreneur_by_owner_user(
        self, owner_user_id: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/entrepreneurs",
                    params={"owner_user_id": f"eq.{owner_user_id}", "limit": "1"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if rows else None
        except Exception as exc:
            self._raise_persistence_error("fetch_entrepreneur_by_owner_user", exc)
            return None

    def fetch_entrepreneur_by_id(
        self, entrepreneur_id: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/entrepreneurs",
                    params={"id": f"eq.{entrepreneur_id}", "limit": "1"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if rows else None
        except Exception as exc:
            self._raise_persistence_error("fetch_entrepreneur_by_id", exc)
            return None

    # --- Tablas PostgreSQL de WhatsApp (whatsapp_links, whatsapp_onboarding_sessions, whatsapp_link_challenges) ---

    def get_whatsapp_link_by_phone(
        self, phone_sha256: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/whatsapp_links",
                    params={"phone_sha256": f"eq.{phone_sha256}", "limit": "1"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if rows else None
        except Exception as exc:
            self._raise_persistence_error("get_whatsapp_link_by_phone", exc)
            return None

    def insert_whatsapp_link_atomic(
        self, phone_sha256: str, entrepreneur_id: str, phone_masked: str
    ) -> Dict[str, Any]:
        """Inserta atómicamente el vínculo teléfono <-> emprendedora en PostgreSQL.
        Rechaza colisiones concurrentes gracias a PRIMARY KEY (phone_sha256) y UNIQUE (entrepreneur_id).
        """
        if entrepreneur_id == "rosa-huamanga-001":
            raise SupabasePersistenceError(
                "No se permite vincular teléfonos reales a la cuenta ficticia 'rosa-huamanga-001'."
            )
        if not self.is_enabled:
            return {
                "phone_sha256": phone_sha256,
                "entrepreneur_id": entrepreneur_id,
                "phone_masked": phone_masked,
            }
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/whatsapp_links",
                    headers=self._headers("return=representation"),
                    json={
                        "phone_sha256": phone_sha256,
                        "entrepreneur_id": entrepreneur_id,
                        "phone_masked": phone_masked,
                    },
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if isinstance(rows, list) and rows else {}
        except Exception as exc:
            self._raise_persistence_error("insert_whatsapp_link_atomic", exc)
            return {}

    def get_whatsapp_onboarding_session(
        self, phone_sha256: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/whatsapp_onboarding_sessions",
                    params={"phone_sha256": f"eq.{phone_sha256}", "limit": "1"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if rows else None
        except Exception as exc:
            self._raise_persistence_error("get_whatsapp_onboarding_session", exc)
            return None

    def upsert_whatsapp_onboarding_session(
        self, session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self.is_enabled:
            return session_data
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/whatsapp_onboarding_sessions?on_conflict=phone_sha256",
                    headers=self._headers(
                        "resolution=merge-duplicates,return=representation"
                    ),
                    json=session_data,
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if isinstance(rows, list) and rows else session_data
        except Exception as exc:
            self._raise_persistence_error("upsert_whatsapp_onboarding_session", exc)
            return session_data

    def create_whatsapp_link_challenge(
        self, challenge_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self.is_enabled:
            return challenge_data
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/whatsapp_link_challenges",
                    headers=self._headers("return=representation"),
                    json=challenge_data,
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if isinstance(rows, list) and rows else challenge_data
        except Exception as exc:
            self._raise_persistence_error("create_whatsapp_link_challenge", exc)
            return challenge_data

    def get_whatsapp_link_challenge(
        self, code_sha256: str
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/whatsapp_link_challenges",
                    params={"code_sha256": f"eq.{code_sha256}", "limit": "1"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return rows[0] if rows else None
        except Exception as exc:
            self._raise_persistence_error("get_whatsapp_link_challenge", exc)
            return None

    def consume_whatsapp_link_challenge_atomic(
        self,
        code_sha256: str,
        expected_type: str,
        now_dt: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Consume atómicamente un código de un solo uso verificando expiración y límite de intentos (<= 5)."""
        if not self.is_enabled:
            return None
        now_iso = now_dt.isoformat()
        try:
            with httpx.Client(timeout=8.0) as client:
                check_resp = client.get(
                    f"{self.url}/rest/v1/whatsapp_link_challenges",
                    params={"code_sha256": f"eq.{code_sha256}", "limit": "1"},
                    headers=self._headers(),
                )
                check_resp.raise_for_status()
                rows = check_resp.json()
                if not rows:
                    return None
                row = rows[0]
                attempts = int(row.get("attempts") or 0)
                used = bool(row.get("used", False))
                exp_str = str(row.get("expires_at") or "")
                exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)

                if (
                    used
                    or attempts >= 5
                    or now_dt >= exp_dt
                    or row.get("challenge_type") != expected_type
                ):
                    if not used and attempts < 5:
                        client.patch(
                            f"{self.url}/rest/v1/whatsapp_link_challenges",
                            params={
                                "code_sha256": f"eq.{code_sha256}",
                                "used": "is.false",
                            },
                            headers=self._headers("return=minimal"),
                            json={"attempts": min(attempts + 1, 5)},
                        )
                    return None

                # Actualización condicional atómica: solo tiene éxito si used sigue siendo false y attempts < 5
                patch_resp = client.patch(
                    f"{self.url}/rest/v1/whatsapp_link_challenges",
                    params={
                        "code_sha256": f"eq.{code_sha256}",
                        "challenge_type": f"eq.{expected_type}",
                        "used": "is.false",
                        "attempts": "lt.5",
                        "expires_at": f"gt.{now_iso}",
                    },
                    headers=self._headers("return=representation"),
                    json={
                        "used": True,
                        "used_at": now_iso,
                        "attempts": attempts + 1,
                    },
                )
                patch_resp.raise_for_status()
                updated_rows = patch_resp.json()
                if not updated_rows:
                    return None
                return updated_rows[0]
        except Exception as exc:
            self._raise_persistence_error("consume_whatsapp_link_challenge_atomic", exc)
            return None

    def fetch_audit_logs(
        self, action_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not self.is_enabled:
            return []
        params: Dict[str, str] = {"order": "created_at.asc"}
        if action_type:
            params["action_type"] = f"eq.{action_type}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/audit_logs",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            self._raise_persistence_error("fetch_audit_logs", exc)
            return []

    def sync_weekly_goals(
        self, entrepreneur_id: str, weeks: List[WeeklySummaryItem]
    ) -> None:
        """Sincroniza de forma no destructiva `public.weekly_goals` usando `weekly_target_pen`."""
        if not self.is_enabled or not weeks:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = [
            {
                "id": f"wg-{entrepreneur_id}-w{w.week_number}",
                "entrepreneur_id": entrepreneur_id,
                "week_number": w.week_number,
                "week_label": w.week_label,
                "weekly_target_pen": round(float(w.weekly_target_pen), 2),
                "total_sales_pen": round(float(w.total_sales_pen), 2),
                "total_expenses_pen": round(float(w.total_expenses_pen), 2),
                "net_margin_pen": round(float(w.net_margin_pen), 2),
                "status_badge": w.status_badge,
                "updated_at": now_iso,
            }
            for w in weeks
        ]
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/weekly_goals?on_conflict=id",
                    headers=self._headers("resolution=merge-duplicates,return=minimal"),
                    json=payload,
                )
                resp.raise_for_status()
        except Exception as exc:
            self._raise_persistence_error("sync_weekly_goals", exc)

    def reset_demo_in_supabase(
        self,
        entrepreneur: EntrepreneurProfileInfo,
        seed_movements: List[MovementRecord],
        seed_chat: List[ChatMessageBubble],
        weekly_summaries: Optional[List[WeeklySummaryItem]] = None,
    ) -> None:
        """Restaura el estado demo en Supabase (solo cuando es invocado explícitamente por un admin autorizado)."""
        if not self.is_enabled:
            return
        try:
            with httpx.Client(timeout=10.0) as client:
                client.delete(
                    f"{self.url}/rest/v1/movements",
                    params={
                        "entrepreneur_id": f"eq.{entrepreneur.id}",
                        "week_number": "eq.8",
                    },
                    headers=self._headers("return=minimal"),
                ).raise_for_status()
                client.delete(
                    f"{self.url}/rest/v1/profile_consents",
                    params={"entrepreneur_id": f"eq.{entrepreneur.id}"},
                    headers=self._headers("return=minimal"),
                ).raise_for_status()
                client.delete(
                    f"{self.url}/rest/v1/processed_messages",
                    params={"entrepreneur_id": f"eq.{entrepreneur.id}"},
                    headers=self._headers("return=minimal"),
                ).raise_for_status()
                client.delete(
                    f"{self.url}/rest/v1/chat_messages",
                    params={"entrepreneur_id": f"eq.{entrepreneur.id}"},
                    headers=self._headers("return=minimal"),
                ).raise_for_status()
            self.ensure_seed_data(
                entrepreneur, seed_movements, seed_chat, weekly_summaries
            )
        except Exception as exc:
            self._raise_persistence_error("reset_demo_in_supabase", exc)

    def fetch_movements(
        self,
        entrepreneur_id: str,
        week_number: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Optional[List[MovementRecord]]:
        if not self.is_enabled:
            return None
        params: Dict[str, str] = {
            "entrepreneur_id": f"eq.{entrepreneur_id}",
            "order": "created_at.asc,id.asc",
        }
        if week_number is not None:
            params["week_number"] = f"eq.{week_number}"
        if status is not None:
            params["status"] = f"eq.{status}"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/movements",
                    params=params,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return [
                    MovementRecord.model_validate(_normalize_movement_row(r))
                    for r in rows
                ]
        except Exception as exc:
            self._raise_persistence_error("fetch_movements", exc)
            return None

    def sync_movement(self, record: MovementRecord) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/movements?on_conflict=id",
                    headers=self._headers(
                        "resolution=merge-duplicates,return=representation"
                    ),
                    json=record.model_dump(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data[0] if isinstance(data, list) and data else None
        except Exception as exc:
            self._raise_persistence_error("sync_movement", exc)
            return None

    def patch_movement_for_entrepreneur(
        self,
        movement_id: str,
        entrepreneur_id: str,
        updates: Dict[str, Any],
    ) -> Optional[MovementRecord]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.patch(
                    f"{self.url}/rest/v1/movements",
                    params={
                        "id": f"eq.{movement_id}",
                        "entrepreneur_id": f"eq.{entrepreneur_id}",
                    },
                    headers=self._headers("return=representation"),
                    json=updates,
                )
                resp.raise_for_status()
                rows = resp.json()
                if not rows:
                    return None
                return MovementRecord.model_validate(_normalize_movement_row(rows[0]))
        except Exception as exc:
            self._raise_persistence_error("patch_movement_for_entrepreneur", exc)
            return None

    def fetch_consents(self, entrepreneur_id: str) -> Optional[List[ConsentRecord]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/profile_consents",
                    params={
                        "entrepreneur_id": f"eq.{entrepreneur_id}",
                        "order": "granted_at.desc",
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return [ConsentRecord.model_validate(r) for r in rows]
        except Exception as exc:
            self._raise_persistence_error("fetch_consents", exc)
            return None

    def fetch_consent_by_token_hash(
        self, token_sha256: str
    ) -> Optional[ConsentRecord]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/profile_consents",
                    params={"token_sha256": f"eq.{token_sha256}", "limit": "1"},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return ConsentRecord.model_validate(rows[0]) if rows else None
        except Exception as exc:
            self._raise_persistence_error("fetch_consent_by_token_hash", exc)
            return None

    def sync_consent(self, consent: ConsentRecord) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/profile_consents?on_conflict=id",
                    headers=self._headers(
                        "resolution=merge-duplicates,return=representation"
                    ),
                    json=consent.model_dump(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data[0] if isinstance(data, list) and data else None
        except Exception as exc:
            self._raise_persistence_error("sync_consent", exc)
            return None

    def patch_consent_for_entrepreneur(
        self,
        consent_id: str,
        entrepreneur_id: str,
        updates: Dict[str, Any],
    ) -> Optional[ConsentRecord]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.patch(
                    f"{self.url}/rest/v1/profile_consents",
                    params={
                        "id": f"eq.{consent_id}",
                        "entrepreneur_id": f"eq.{entrepreneur_id}",
                    },
                    headers=self._headers("return=representation"),
                    json=updates,
                )
                resp.raise_for_status()
                rows = resp.json()
                if not rows:
                    return None
                return ConsentRecord.model_validate(rows[0])
        except Exception as exc:
            self._raise_persistence_error("patch_consent_for_entrepreneur", exc)
            return None

    def fetch_chat_history(
        self, entrepreneur_id: str
    ) -> Optional[List[ChatMessageBubble]]:
        if not self.is_enabled:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(
                    f"{self.url}/rest/v1/chat_messages",
                    params={
                        "entrepreneur_id": f"eq.{entrepreneur_id}",
                        "order": "timestamp.asc,id.asc",
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()
                rows = resp.json()
                return [
                    ChatMessageBubble.model_validate(_normalize_chat_row(r))
                    for r in rows
                ]
        except Exception as exc:
            self._raise_persistence_error("fetch_chat_history", exc)
            return None

    def sync_chat_bubble(
        self, entrepreneur_id: str, bubble: ChatMessageBubble
    ) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        payload = {**bubble.model_dump(), "entrepreneur_id": entrepreneur_id}
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/chat_messages?on_conflict=id",
                    headers=self._headers(
                        "resolution=merge-duplicates,return=representation"
                    ),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data[0] if isinstance(data, list) and data else None
        except Exception as exc:
            self._raise_persistence_error("sync_chat_bubble", exc)
            return None

    def check_and_record_message_sid(
        self,
        message_sid: str,
        entrepreneur_id: Optional[str],
        sender_phone_hash: str,
        raw_body: str,
    ) -> bool:
        """Devuelve True si el MessageSid ya existía en Supabase; si no, lo inserta y devuelve False.
        Para teléfonos no vinculados, `entrepreneur_id` se almacena como `None` (jamás 'rosa-huamanga-001').
        """
        if not self.is_enabled:
            return False
        try:
            with httpx.Client(timeout=8.0) as client:
                check = client.get(
                    f"{self.url}/rest/v1/processed_messages",
                    params={
                        "message_sid": f"eq.{message_sid}",
                        "select": "message_sid",
                    },
                    headers=self._headers(),
                )
                check.raise_for_status()
                if check.json():
                    return True
                insert_resp = client.post(
                    f"{self.url}/rest/v1/processed_messages",
                    headers=self._headers("return=minimal"),
                    json={
                        "message_sid": message_sid,
                        "entrepreneur_id": entrepreneur_id,
                        "sender_phone_hash": sender_phone_hash,
                        "raw_body": raw_body,
                    },
                )
                if insert_resp.status_code == 409:
                    return True
                insert_resp.raise_for_status()
                return False
        except Exception as exc:
            self._raise_persistence_error("check_and_record_message_sid", exc)
            return False

    def log_audit_event(
        self,
        entrepreneur_id: str,
        action_type: str,
        entity_type: str,
        entity_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        if not self.is_enabled:
            return
        # Sanitización preventiva: jamás escribir hashes de contraseñas ni tokens en audit_logs
        sanitized_meta = {
            k: v
            for k, v in metadata.items()
            if k not in ("password", "password_hash", "password_salt", "access_token")
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.url}/rest/v1/audit_logs",
                    headers=self._headers("return=minimal"),
                    json={
                        "entrepreneur_id": entrepreneur_id,
                        "action_type": action_type,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "metadata": sanitized_meta,
                    },
                )
                resp.raise_for_status()
        except Exception as exc:
            self._raise_persistence_error("log_audit_event", exc)


supabase_adapter = SupabaseAdapter()

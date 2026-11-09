"""Pruebas integrales de las 10 funciones principales, JWT real (iss, aud, exp, firma),
prohibición de reclamo de titularidad por user_metadata, consentimiento expreso (fecha + versión),
persistencia PostgreSQL de WhatsApp (onboarding, links, challenges), idempotencia MessageSid sin
referencia a Rosa, fallo estricto ante caída de Supabase (503) y sandbox demo de 133 movimientos."""

from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import time
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, validate_runtime_security_settings
from app.main import app
from app.models import EntrepreneurProfileInfo
from app.security import create_signed_jwt
from app.seed_rosa import get_initial_chat_history, get_initial_movements
from app.services.demo_sandbox import demo_sandbox_manager
from app.services.store import InMemoryStore, store
from app.services.supabase_adapter import supabase_adapter

client = TestClient(app)


@pytest.fixture()
def auth_headers(monkeypatch) -> dict[str, str]:
    """Configura un secreto JWT efímero por prueba y registra una emprendedora de prueba verificada
    con las 7 semanas base (28 movimientos), manteniendo a 'rosa-huamanga-001' sin owner_user_id.
    """
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    ephemeral_jwt_secret = secrets.token_hex(32)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", ephemeral_jwt_secret)
    store.reset_to_demo_seed()

    owner_user_id = str(uuid.uuid4())
    test_eid = "emp-test-verified-001"
    now_iso = datetime.now(timezone.utc).isoformat()
    test_profile = EntrepreneurProfileInfo(
        id=test_eid,
        full_name="Rosa Quispe (Cuenta de Prueba Verificada)",
        business_name="Frutería La Huamanguina",
        trade_sector="Comercio minorista de frutas",
        market_location="Mercado Nery García Zárate",
        city="Huamanga",
        region="Ayacucho",
        phone_masked="+51 966 *** 418",
        goal_title="Comprar vitrina exhibidora refrigerada",
        goal_target_pen=2000.00,
        goal_weekly_target_pen=250.00,
        goal_weeks=8,
        active_week=8,
        preferred_language="es",
        owner_user_id=owner_user_id,
        data_consent_accepted=True,
        data_consent_accepted_at=now_iso,
        data_consent_version="v1.0-2026-11",
        whatsapp_linked=True,
        is_fictional_demo=False,
    )
    store.entrepreneurs_by_id[test_eid] = test_profile
    store.owner_by_entrepreneur[test_eid] = owner_user_id
    for m in get_initial_movements():
        store.movements.append(
            m.model_copy(update={"id": f"{m.id}-t", "entrepreneur_id": test_eid})
        )
    store.chat_history_by_eid[test_eid] = get_initial_chat_history()

    token = create_signed_jwt(
        {
            "sub": owner_user_id,
            "role": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        ephemeral_jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


def test_disabled_twilio_rejects_unsigned_webhook(monkeypatch):
    from app.services import twilio_adapter
    from types import SimpleNamespace

    monkeypatch.setattr(twilio_adapter, "settings", SimpleNamespace(use_external_twilio=False))
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", "https://example.trycloudflare.com/api/twilio/webhook")
    response = client.post("/api/twilio/webhook", data={"From": "whatsapp:+51999999999", "Body": "Hola"})
    assert response.status_code == 403


def test_twilio_signature_uses_configured_https_url(monkeypatch):
    import base64
    import hmac
    from types import SimpleNamespace
    from app.services import twilio_adapter

    url = "https://example.trycloudflare.com/api/twilio/webhook"
    token = "test-token-for-signature"
    payload = {"From": "whatsapp:+51999999999", "Body": "Hola", "MessageSid": "SM-test"}
    signed = url + "".join(key + payload[key] for key in sorted(payload))
    signature = base64.b64encode(hmac.new(token.encode(), signed.encode(), hashlib.sha1).digest()).decode()
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", url)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", token)
    monkeypatch.setattr(twilio_adapter, "settings", SimpleNamespace(use_external_twilio=True))
    # Avoid any external writes while checking that a valid request reaches the handler.
    monkeypatch.setattr("app.routers.twilio_webhook.store.get_verified_entrepreneur_by_phone", lambda _: None)
    monkeypatch.setattr("app.routers.twilio_webhook.store.is_message_sid_processed", lambda **_: True)
    headers = {"X-Twilio-Signature": signature, "X-Forwarded-Proto": "http", "X-Forwarded-Host": "attacker.invalid"}
    assert client.post("/api/twilio/webhook", data=payload, headers=headers).status_code == 200
    assert client.post("/api/twilio/webhook", data={**payload, "Body": "Alterado"}, headers=headers).status_code == 403
    assert client.post("/api/twilio/webhook", data=payload).status_code == 403
    assert client.post("/api/twilio/webhook?x=1", data=payload, headers=headers).status_code == 503


def test_health_and_rosa_seed_state(monkeypatch):
    """Verifica que el backend inicie con Rosa de Huamanga y que Rosa NO tenga consentimiento presupuesto ni owner_user_id."""
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    store.reset_to_demo_seed()
    res_root = client.get("/health")
    assert res_root.status_code == 200
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "Rosa Quispe" in data["demo_entrepreneur"]
    assert data["city"] == "Huamanga"
    assert data["total_movements"] == 28

    rosa = store.get_entrepreneur("rosa-huamanga-001")
    assert rosa.owner_user_id is None
    assert rosa.data_consent_accepted is False
    assert rosa.data_consent_accepted_at is None
    assert rosa.data_consent_version is None


def test_rosa_orange_kg_multiplication_and_confirmation_flow(auth_headers):
    """Verifica el caso exacto de Fase 1: 'Vendí 20 kg de naranja a 4 y gasté 6 en pasaje' -> S/ 80 venta y S/ 6 gasto."""
    msg_res = client.post(
        "/api/simulator/message",
        headers=auth_headers,
        json={
            "message": "Vendí 20 kg de naranja a 4 y gasté 6 en pasaje",
            "week_number": 8,
        },
    )
    assert msg_res.status_code == 200
    payload = msg_res.json()
    structured = payload["bot_bubble"]["structured_json"]
    assert structured["detected_intent"] == "REGISTRAR_MOVIMIENTO"
    assert structured["requires_confirmation"] is True
    assert len(structured["items"]) == 2
    assert structured["items"][0]["movement_type"] == "VENTA"
    assert structured["items"][0]["amount_pen"] == 80.0
    assert structured["items"][1]["movement_type"] == "GASTO"
    assert structured["items"][1]["amount_pen"] == 6.0

    pending = payload["created_pending_movements"]
    assert len(pending) == 2
    assert all(m["status"] == "PENDIENTE" for m in pending)

    goal_data = client.get("/api/analytics/goal", headers=auth_headers).json()
    assert "02 nov – 08 nov 2026" in goal_data["weeks"][7]["week_label"]


def test_seven_preloaded_weeks_and_eight_week_goal_math(auth_headers):
    """Verifica Funciones 4, 5 y 6: Cálculos en Python, explicación sencilla y meta de 8 semanas."""
    res = client.get("/api/analytics/goal", headers=auth_headers)
    assert res.status_code == 200
    goal = res.json()
    assert goal["total_weeks"] == 8
    assert goal["completed_weeks_count"] == 7
    assert goal["accumulated_net_pen"] == 1795.0
    assert goal["remaining_pen"] == 205.0
    assert goal["goal_achieved"] is False
    assert "S/ 1795.00" in goal["plain_spanish_coaching"]

    week8 = goal["weeks"][7]
    assert week8["week_number"] == 8
    assert week8["total_sales_pen"] == 0.0
    assert week8["total_expenses_pen"] == 0.0
    assert week8["net_margin_pen"] == 0.0


def test_simulator_ai_structured_json_and_confirmation_flow(auth_headers):
    """Verifica Funciones 1, 2, 3 y 10: Simulador WhatsApp, JSON estructurado y confirmación en 2 pasos."""
    msg_res = client.post(
        "/api/simulator/message",
        headers=auth_headers,
        json={
            "message": "Casera hoy vendí 290 soles de palta fuerte y lúcuma, y gasté 45 soles en jabas y transporte",
            "week_number": 8,
        },
    )
    assert msg_res.status_code == 200
    payload = msg_res.json()

    structured = payload["bot_bubble"]["structured_json"]
    assert structured["detected_intent"] == "REGISTRAR_MOVIMIENTO"
    assert structured["requires_confirmation"] is True
    assert len(structured["items"]) == 2
    assert structured["items"][0]["movement_type"] == "VENTA"
    assert structured["items"][0]["amount_pen"] == 290.0
    assert structured["items"][1]["movement_type"] == "GASTO"
    assert structured["items"][1]["amount_pen"] == 45.0

    goal_before = client.get("/api/analytics/goal", headers=auth_headers).json()
    assert goal_before["accumulated_net_pen"] == 1795.0
    assert goal_before["weeks"][7]["pending_movements_count"] == 2

    confirm_res = client.post(
        "/api/simulator/message",
        headers=auth_headers,
        json={"message": "Sí confirmo", "week_number": 8},
    )
    assert confirm_res.status_code == 200
    updated = confirm_res.json()["updated_movements"]
    assert len(updated) == 2
    assert all(m["status"] == "CONFIRMADO" for m in updated)

    goal_after = client.get("/api/analytics/goal", headers=auth_headers).json()
    assert goal_after["weeks"][7]["net_margin_pen"] == 245.0
    assert goal_after["accumulated_net_pen"] == 2040.0
    assert goal_after["completed_weeks_count"] == 8
    assert goal_after["goal_achieved"] is True


def test_profile_generation_consent_grant_and_revocation_guardrails(auth_headers):
    """Verifica Funciones 7, 8, 9 y Seguridad: Perfil sin falsas aprobaciones BCP, consentimiento, minimización y revocación."""
    prof_res = client.get("/api/profile", headers=auth_headers)
    assert prof_res.status_code == 200
    profile = prof_res.json()
    assert profile["bcp_approval_claim"] is False
    assert "NO constituye una aprobación crediticia" in profile["regulatory_disclaimer"]
    assert len(profile["evidence_integrity_hash"]) == 64

    bad_grant = client.post(
        "/api/consents/grant",
        headers=auth_headers,
        json={
            "recipient_entity": "Programa Mujeres Emprendedoras BCP",
            "purpose": "Evaluación de historial operativo de 8 semanas",
            "accepted_terms": False,
        },
    )
    assert bad_grant.status_code == 400

    grant_res = client.post(
        "/api/consents/grant",
        headers=auth_headers,
        json={
            "recipient_entity": "Programa Mujeres Emprendedoras BCP",
            "purpose": "Evaluación de historial operativo de 8 semanas",
            "accepted_terms": True,
        },
    )
    assert grant_res.status_code == 201
    consent = grant_res.json()
    assert consent["status"] == "ACTIVO"
    token = consent["share_token"]

    shared_ok = client.get(f"/api/consents/shared/{token}")
    assert shared_ok.status_code == 200
    shared_body = shared_ok.json()
    assert shared_body["shared_profile"]["bcp_approval_claim"] is False
    assert "share_token" not in shared_body["consent"]
    assert "token_sha256" not in shared_body["consent"]
    assert shared_body["shared_profile"]["entrepreneur"]["id"] == "TITULAR-VERIFICADA"

    revoke_res = client.post(
        f"/api/consents/{consent['id']}/revoke",
        headers=auth_headers,
        json={"reason": "Rosa decidió revocar el acceso tras la reunión informativa"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOCADO"

    shared_blocked = client.get(f"/api/consents/shared/{token}")
    assert shared_blocked.status_code == 403
    assert "ACCESO REVOCADO" in shared_blocked.json()["detail"]
    assert len(consent["token_sha256"]) == 64
    assert consent["expires_at"] is not None


def test_shared_consent_expiration_enforcement(auth_headers):
    """Verifica que un consentimiento vencido (expires_at <= now) sea rechazado con 403 Forbidden y estado EXPIRADO."""
    expired_consent = store.create_consent(
        recipient_entity="Entidad Temporal",
        purpose="Prueba de caducidad automática",
        evidence_hash="a" * 64,
        expires_in_seconds=-10,
        entrepreneur_id="emp-test-verified-001",
    )
    res = client.get(f"/api/consents/shared/{expired_consent.share_token}")
    assert res.status_code == 403
    assert "ACCESO EXPIRADO" in res.json()["detail"]
    assert store.list_consents(entrepreneur_id="emp-test-verified-001")[0].status == "EXPIRADO"


def test_anonymous_and_unverified_jwt_rejected_and_jwt_claims_validated(
    monkeypatch,
):
    """Verifica validación de iss, aud, exp, firma y rechazo de usuarios sin titularidad."""
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    ephemeral_secret = secrets.token_hex(32)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", ephemeral_secret)
    monkeypatch.setenv("SUPABASE_URL", "https://oqbfuyxoclufkikaddoj.supabase.co")
    store.reset_to_demo_seed()

    unlinked_user_jwt = create_signed_jwt(
        {
            "sub": str(uuid.uuid4()),
            "role": "authenticated",
            "exp": int(time.time()) + 3600,
        },
        ephemeral_secret,
    )
    unlinked_res = client.get(
        "/api/movements", headers={"Authorization": f"Bearer {unlinked_user_jwt}"}
    )
    assert unlinked_res.status_code == 403

    # Expirado -> 401
    expired_jwt = create_signed_jwt(
        {
            "sub": str(uuid.uuid4()),
            "role": "authenticated",
            "exp": int(time.time()) - 60,
        },
        ephemeral_secret,
    )
    assert (
        client.get(
            "/api/movements", headers={"Authorization": f"Bearer {expired_jwt}"}
        ).status_code
        == 401
    )

    # Emisor ('iss') inválido -> 401
    bad_iss_jwt = create_signed_jwt(
        {
            "sub": str(uuid.uuid4()),
            "role": "authenticated",
            "iss": "https://proyecto-atacante.supabase.co/auth/v1",
            "exp": int(time.time()) + 3600,
        },
        ephemeral_secret,
    )
    res_bad_iss = client.get(
        "/api/movements", headers={"Authorization": f"Bearer {bad_iss_jwt}"}
    )
    assert res_bad_iss.status_code == 401
    assert "iss" in res_bad_iss.json()["detail"]

    # Audiencia ('aud') inválida -> 401
    bad_aud_jwt = create_signed_jwt(
        {
            "sub": str(uuid.uuid4()),
            "role": "authenticated",
            "aud": "anon",
            "exp": int(time.time()) + 3600,
        },
        ephemeral_secret,
    )
    res_bad_aud = client.get(
        "/api/movements", headers={"Authorization": f"Bearer {bad_aud_jwt}"}
    )
    assert res_bad_aud.status_code == 401
    assert "aud" in res_bad_aud.json()["detail"]

    private_gets = [
        "/api/movements",
        "/api/analytics/weekly",
        "/api/analytics/goal",
        "/api/simulator/history",
        "/api/profile",
        "/api/consents",
    ]
    for path in private_gets:
        res_anon = client.get(path)
        assert res_anon.status_code == 401, f"GET {path} permitió acceso anónimo"
        res_bad = client.get(path, headers={"Authorization": "Bearer token-falso"})
        assert res_bad.status_code == 401, f"GET {path} aceptó token inválido"


def test_malicious_user_metadata_cannot_claim_rosa_huamanga_001(monkeypatch):
    """Requisito 1: Intenta reclamar 'rosa-huamanga-001' desde una cuenta recién creada con
    user_metadata manipulado. Debe devolver 403 Acceso Denegado sin modificar memoria ni Supabase.
    """
    from app.routers import auth_onboarding

    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    ephemeral_secret = secrets.token_hex(32)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", ephemeral_secret)
    store.reset_to_demo_seed()

    supabase_upserts = []
    monkeypatch.setattr(
        supabase_adapter,
        "upsert_entrepreneur",
        lambda prof: supabase_upserts.append(prof),
    )

    attacker_uid = str(uuid.uuid4())
    forged_jwt = create_signed_jwt(
        {
            "sub": attacker_uid,
            "email": "atacante@malicioso.pe",
            "role": "authenticated",
            "exp": int(time.time()) + 3600,
            "user_metadata": {"entrepreneur_id": "rosa-huamanga-001"},
            "app_metadata": {"entrepreneur_id": "rosa-huamanga-001"},
        },
        ephemeral_secret,
    )

    # 1. Intentar leer o modificar endpoints privados con el JWT que lleva user_metadata="rosa-huamanga-001"
    for endpoint in ("/api/movements", "/api/auth/me", "/api/profile", "/api/consents"):
        res = client.get(
            endpoint,
            headers={
                "Authorization": f"Bearer {forged_jwt}",
                "X-Entrepreneur-Id": "rosa-huamanga-001",
            },
        )
        assert res.status_code == 403, f"El endpoint {endpoint} no bloqueó el reclamo de rosa-huamanga-001"

    # 2. Intentar activar sesión mediante /api/auth/login con user_metadata manipulado sin registro backend
    monkeypatch.setattr(
        auth_onboarding,
        "_supabase_auth_login_password",
        lambda email, password: {
            "access_token": forged_jwt,
            "expires_in": 3600,
            "user": {
                "id": attacker_uid,
                "email": email,
                "email_confirmed_at": "2026-11-08T20:00:00Z",
                "user_metadata": {"entrepreneur_id": "rosa-huamanga-001"},
            },
        },
    )
    login_attempt = client.post(
        "/api/auth/login",
        json={"email": "atacante@malicioso.pe", "password": "Password1234!"},
    )
    assert login_attempt.status_code == 403

    # 3. Verificar que NI la memoria NI Supabase sufrieron modificaciones
    assert "rosa-huamanga-001" not in store.owner_by_entrepreneur
    rosa_after = store.entrepreneurs_by_id["rosa-huamanga-001"]
    assert rosa_after.owner_user_id is None
    assert rosa_after.data_consent_accepted is False
    assert supabase_upserts == []


def test_admin_reset_blocked_for_normal_user_and_in_production(auth_headers, monkeypatch):
    """Verifica que /api/demo/reset rechace usuarios sin rol admin y esté desactivado en producción."""
    res_non_admin = client.post("/api/demo/reset", headers=auth_headers)
    assert res_non_admin.status_code == 403

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_ADMIN_DEMO_RESET", "false")
    res_prod = client.post("/api/demo/reset", headers=auth_headers)
    assert res_prod.status_code == 403


def test_isolated_demo_sandbox_enriched_133_movements_and_categories(auth_headers):
    """Requisito 7: Verifica que la demostración ficticia de Rosa cargue 133 movimientos, 6 categorías
    y permita registrar un movimiento en la Semana 8 sin alterar cuentas reales.
    """
    v1_headers = {"X-Demo-Visitor-Id": "vis-jurado-bcp-001"}
    v2_headers = {"X-Demo-Visitor-Id": "vis-jurado-bcp-002"}
    demo_sandbox_manager.reset_sandbox("vis-jurado-bcp-001")
    demo_sandbox_manager.reset_sandbox("vis-jurado-bcp-002")

    v2_movs = client.get("/api/demo-sandbox/movements", headers=v2_headers).json()
    assert len(v2_movs) == 133

    v2_goal = client.get("/api/demo-sandbox/analytics/goal", headers=v2_headers).json()
    assert v2_goal["accumulated_net_pen"] == 1795.0
    assert v2_goal["remaining_pen"] == 205.0
    categories_present = {c["category"] for c in v2_goal["category_breakdown"]}
    assert categories_present == {
        "Ventas de frutas",
        "Compra de mercadería",
        "Transporte",
        "Empaques",
        "Gastos del puesto",
        "Mermas",
    }

    # Visitante 1 registra y confirma 2 movimientos en la Semana 8
    v1_msg = client.post(
        "/api/demo-sandbox/simulator/message",
        headers=v1_headers,
        json={"message": "Vendí 20 kg de naranja a 4 y gasté 6 en pasaje", "week_number": 8},
    )
    assert v1_msg.status_code == 200
    v1_conf = client.post(
        "/api/demo-sandbox/simulator/message",
        headers=v1_headers,
        json={"message": "Sí confirmo", "week_number": 8},
    )
    assert v1_conf.status_code == 200

    v1_movs = client.get("/api/demo-sandbox/movements", headers=v1_headers).json()
    assert len(v1_movs) == 135

    v2_movs_after = client.get("/api/demo-sandbox/movements", headers=v2_headers).json()
    assert len(v2_movs_after) == 133

    private_movs = client.get("/api/movements", headers=auth_headers).json()
    assert len(private_movs) == 28


def test_production_startup_rejects_missing_or_default_secrets(monkeypatch):
    """Verifica que el backend no pueda iniciar en producción con secretos faltantes o predeterminados."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Fallo de seguridad al iniciar en producción"):
        validate_runtime_security_settings(
            Settings(
                app_env="production",
                frontend_origin="https://qullqi-rimay.vercel.app",
                consent_signing_secret="qullqi-rimay-local-dev-signing-key-2026",
                supabase_jwt_secret="",
            )
        )

    with pytest.raises(RuntimeError, match="FRONTEND_ORIGIN"):
        validate_runtime_security_settings(
            Settings(
                app_env="production",
                frontend_origin="http://localhost:5173",
                consent_signing_secret=secrets.token_hex(32),
                supabase_jwt_secret=secrets.token_hex(32),
            )
        )


def test_three_identities_acceptance_rosa_maria_and_juana_bidirectional_sync(monkeypatch):
    """Prueba integral con 3 identidades (Rosa, María y Juana), consentimiento expreso (fecha + versión),
    uso único y límite de intentos de códigos, y deduplicación MessageSid sin usar rosa-huamanga-001.
    """
    # La simulación no debe convertir el webhook real en un endpoint sin firma.
    monkeypatch.setattr("app.routers.twilio_webhook.verify_twilio_signature", lambda *_: True)
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", "https://example.trycloudflare.com/api/twilio/webhook")
    from fastapi import HTTPException
    from app.routers import auth_onboarding

    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    ephemeral_jwt_secret = secrets.token_hex(32)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", ephemeral_jwt_secret)
    store.reset_to_demo_seed()

    supabase_auth_users: dict[str, dict] = {}
    simulated_email_inbox_otp: dict[str, str] = {}
    simulate_smtp_429 = {"active": False}

    def fake_supabase_signup(email: str, password: str, metadata: dict) -> dict:
        if simulate_smtp_429["active"]:
            raise HTTPException(
                status_code=429,
                detail="Límite de envío de correos de Supabase Auth alcanzado (HTTP 429).",
            )
        uid = str(uuid.uuid4())
        otp = f"{secrets.randbelow(900000) + 100000}"
        supabase_auth_users[email] = {
            "id": uid,
            "email": email,
            "password": password,
            "user_metadata": metadata,
            "email_confirmed_at": None,
        }
        simulated_email_inbox_otp[email] = otp
        return {"user": supabase_auth_users[email], "session": None}

    def fake_supabase_verify_otp(email: str, token: str) -> dict:
        u = supabase_auth_users.get(email)
        expected_otp = simulated_email_inbox_otp.get(email)
        if not u or not expected_otp or token != expected_otp:
            raise HTTPException(status_code=400, detail="OTP inválido en Supabase Auth")
        u["email_confirmed_at"] = "2026-11-08T23:59:00Z"
        jwt_tok = create_signed_jwt(
            {
                "sub": u["id"],
                "email": email,
                "role": "authenticated",
                "exp": int(time.time()) + 3600,
                "user_metadata": u["user_metadata"],
            },
            ephemeral_jwt_secret,
        )
        return {"access_token": jwt_tok, "expires_in": 3600, "user": u}

    def fake_supabase_login(email: str, password: str) -> dict:
        u = supabase_auth_users.get(email)
        if not u or u["password"] != password or not u["email_confirmed_at"]:
            raise HTTPException(
                status_code=401,
                detail="Credenciales inválidas o correo aún no confirmado en Supabase Auth.",
            )
        jwt_tok = create_signed_jwt(
            {
                "sub": u["id"],
                "email": email,
                "role": "authenticated",
                "exp": int(time.time()) + 3600,
                "user_metadata": u["user_metadata"],
            },
            ephemeral_jwt_secret,
        )
        return {"access_token": jwt_tok, "expires_in": 3600, "user": u}

    monkeypatch.setattr(auth_onboarding, "_supabase_auth_signup", fake_supabase_signup)
    monkeypatch.setattr(auth_onboarding, "_supabase_auth_verify_otp", fake_supabase_verify_otp)
    monkeypatch.setattr(auth_onboarding, "_supabase_auth_login_password", fake_supabase_login)

    # Rechazo si no acepta consentimiento expreso
    res_no_consent = client.post(
        "/api/auth/register",
        json={
            "email": "sin.consentimiento@ayacucho.pe",
            "password": "ClaveSegura2026!",
            "full_name": "Sin Consentimiento",
            "business_name": "Puesto 0",
            "accepted_data_consent": False,
        },
    )
    assert res_no_consent.status_code == 400

    # Comprobar que si Supabase Auth devuelve HTTP 429 (límite SMTP), NO se genera código local ni bypass
    simulate_smtp_429["active"] = True
    res_429 = client.post(
        "/api/auth/register",
        json={
            "email": "bloqueada.smtp@ayacucho.pe",
            "password": "ClaveSegura2026!",
            "full_name": "Usuaria Bloqueada",
            "business_name": "Puesto 1",
            "accepted_data_consent": True,
        },
    )
    assert res_429.status_code == 429
    simulate_smtp_429["active"] = False

    # =========================================================================
    # IDENTIDAD 2: MARÍA CONDORI (Cuenta creada desde la Web + Vínculo WhatsApp)
    # =========================================================================
    reg_maria = client.post(
        "/api/auth/register",
        json={
            "email": "maria.condori@ayacucho.pe",
            "password": "ClaveSeguraMaria2026!",
            "full_name": "María Condori",
            "business_name": "Bodega Sumaq Kawsay",
            "trade_sector": "Abarrotes y granos andinos",
            "market_location": "Mercado Nery García, Puesto 12",
            "city": "Huamanga",
            "region": "Ayacucho",
            "goal_title": "Reunir S/ 1,600 en 8 semanas para vitrina exhibidora",
            "goal_target_pen": 1600.0,
            "preferred_language": "es",
            "accepted_data_consent": True,
            "consent_version": "v1.0-2026-11",
        },
    )
    assert reg_maria.status_code == 201
    reg_maria_data = reg_maria.json()
    assert reg_maria_data["email_verification_required"] is True
    assert "verification_challenge_code" not in reg_maria_data

    # Verificar que no se almacenan hashes de contraseñas en RegisteredUserAccount
    maria_acc = store.users_by_email["maria.condori@ayacucho.pe"]
    assert not hasattr(maria_acc, "password_hash")
    assert not hasattr(maria_acc, "password_salt")

    # Intento de login antes de verificar correo en Supabase Auth debe fallar con 401
    login_unverified = client.post(
        "/api/auth/login",
        json={"email": "maria.condori@ayacucho.pe", "password": "ClaveSeguraMaria2026!"},
    )
    assert login_unverified.status_code == 401

    # María lee el OTP de su buzón de correo y verifica contra Supabase Auth
    maria_inbox_otp = simulated_email_inbox_otp["maria.condori@ayacucho.pe"]
    verify_maria = client.post(
        "/api/auth/verify-email",
        json={
            "email": "maria.condori@ayacucho.pe",
            "verification_code": maria_inbox_otp,
        },
    )
    assert verify_maria.status_code == 200
    maria_session = verify_maria.json()
    maria_headers = {"Authorization": f"Bearer {maria_session['access_token']}"}
    maria_eid = maria_session["entrepreneur"]["id"]
    assert maria_eid != "rosa-huamanga-001"
    assert maria_session["entrepreneur"]["data_consent_accepted"] is True
    assert maria_session["entrepreneur"]["data_consent_accepted_at"] is not None
    assert maria_session["entrepreneur"]["data_consent_version"] == "v1.0-2026-11"

    # María empieza con 0 movimientos y NO ve los de Rosa
    maria_movs_initial = client.get("/api/movements", headers=maria_headers).json()
    assert maria_movs_initial == []

    # Generar código único VINC-XXXXXX desde la web de María y vincular su WhatsApp
    gen_code_res = client.post("/api/auth/whatsapp/generate-code", headers=maria_headers)
    assert gen_code_res.status_code == 200
    vinc_code = gen_code_res.json()["link_code"]
    assert vinc_code.startswith("VINC-")

    maria_phone = "whatsapp:+51988111222"
    wa_link_res = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_MARIA_LINK_01",
            "From": maria_phone,
            "Body": vinc_code,
        },
    )
    assert wa_link_res.status_code == 200
    assert "Vínculo completado, María Condori" in wa_link_res.text

    # Un segundo intento de usar el mismo código VINC-XXXXXX desde otro teléfono falla (un solo uso)
    wa_reuse_res = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_MARIA_LINK_REUSE",
            "From": "whatsapp:+51999000999",
            "Body": vinc_code,
        },
    )
    assert "inválido, ya fue usado" in wa_reuse_res.text

    # Sincronización WhatsApp -> Web: María envía una venta de S/ 150 por WhatsApp y la confirma
    wa_sale = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_MARIA_SALE_01",
            "From": maria_phone,
            "Body": "Vendí 150 soles de quinua y kiwicha",
        },
    )
    assert "S/ 150.00" in wa_sale.text
    assert "PENDIENTE" in wa_sale.text

    wa_confirm = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_MARIA_CONFIRM_01",
            "From": maria_phone,
            "Body": "Sí confirmo",
        },
    )
    assert "Guardé 1 movimiento(s) por S/ 150.00" in wa_confirm.text

    maria_movs_web = client.get("/api/movements", headers=maria_headers).json()
    assert len(maria_movs_web) == 1
    assert maria_movs_web[0]["amount_pen"] == 150.0
    assert maria_movs_web[0]["status"] == "CONFIRMADO"
    assert maria_movs_web[0]["source_channel"] == "TWILIO_WHATSAPP"

    # Sincronización Web -> WhatsApp: María registra y confirma un gasto de S/ 30 en la web
    web_exp = client.post(
        "/api/movements",
        headers=maria_headers,
        json={
            "week_number": 1,
            "movement_type": "GASTO",
            "amount_pen": 30.0,
            "category": "Transporte",
            "description": "Flete de sacos de quinua",
            "auto_confirm": False,
        },
    )
    assert web_exp.status_code == 201
    exp_id = web_exp.json()["id"]
    client.post(f"/api/movements/{exp_id}/confirm", headers=maria_headers)

    wa_summary = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_MARIA_SUMMARY_01",
            "From": maria_phone,
            "Body": "¿Cómo voy con mi meta?",
        },
    )
    assert "S/ 120.00" in wa_summary.text

    # =========================================================================
    # IDENTIDAD 3: JUANA MENDOZA (Registro iniciado por WhatsApp en Quechua + Web)
    # =========================================================================
    juana_phone = "whatsapp:+51977333444"

    step0 = client.post(
        "/api/twilio/webhook",
        data={"MessageSid": "SM_JUANA_00", "From": juana_phone, "Body": "Hola"},
    )
    assert "Paso 1 de 3" in step0.text

    # Duplicado de MessageSid durante el onboarding provisional (teléfono no vinculado)
    step0_dup = client.post(
        "/api/twilio/webhook",
        data={"MessageSid": "SM_JUANA_00", "From": juana_phone, "Body": "Hola"},
    )
    assert "idempotencia MessageSid activa" in step0_dup.text

    step1 = client.post(
        "/api/twilio/webhook",
        data={"MessageSid": "SM_JUANA_01", "From": juana_phone, "Body": "2"},
    )
    assert "Quechua Ayacuchano (Chanka)" in step1.text
    assert "Paso 2 de 3" in step1.text

    step2 = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_JUANA_02",
            "From": juana_phone,
            "Body": "Juana Mendoza - Verdulería Sumaq - Huamanga",
        },
    )
    assert "Paso 3 de 3" in step2.text
    assert "Juana Mendoza" in step2.text

    step3 = client.post(
        "/api/twilio/webhook",
        data={"MessageSid": "SM_JUANA_03", "From": juana_phone, "Body": "ARI"},
    )
    claim_match = re.search(r"(WA-LINK-[A-F0-9]{8})", step3.text)
    assert claim_match is not None
    juana_claim_code = claim_match.group(1)

    inspect_res = client.get(f"/api/auth/whatsapp/provisional/{juana_claim_code}")
    assert inspect_res.status_code == 200
    assert inspect_res.json()["full_name"] == "Juana Mendoza"
    assert inspect_res.json()["preferred_language"] == "qu"

    reg_juana = client.post(
        "/api/auth/register",
        json={
            "email": "juana.mendoza@ayacucho.pe",
            "password": "ClaveSeguraJuana2026!",
            "full_name": "Juana Mendoza",
            "business_name": "Verdulería Sumaq",
            "trade_sector": "Verduras y tubérculos",
            "market_location": "Mercado Magdalena",
            "city": "Huamanga",
            "region": "Ayacucho",
            "goal_title": "Reunir S/ 1,200 en 8 semanas",
            "goal_target_pen": 1200.0,
            "preferred_language": "qu",
            "accepted_data_consent": True,
            "consent_version": "v1.0-2026-11",
            "whatsapp_claim_code": juana_claim_code,
        },
    )
    assert reg_juana.status_code == 201
    assert "verification_challenge_code" not in reg_juana.json()

    # Intentar reutilizar el mismo código WA-LINK-XXXXXXXX en otro registro web debe fallar (uso único)
    reuse_claim = client.post(
        "/api/auth/register",
        json={
            "email": "otra.persona@ayacucho.pe",
            "password": "ClaveSeguraOtra2026!",
            "full_name": "Otra Persona",
            "business_name": "Otro Negocio",
            "accepted_data_consent": True,
            "whatsapp_claim_code": juana_claim_code,
        },
    )
    assert reuse_claim.status_code == 400

    juana_inbox_otp = simulated_email_inbox_otp["juana.mendoza@ayacucho.pe"]
    juana_verify = client.post(
        "/api/auth/verify-email",
        json={
            "email": "juana.mendoza@ayacucho.pe",
            "verification_code": juana_inbox_otp,
        },
    )
    assert juana_verify.status_code == 200
    juana_session = juana_verify.json()
    juana_headers = {"Authorization": f"Bearer {juana_session['access_token']}"}
    assert juana_session["entrepreneur"]["whatsapp_linked"] is True
    assert juana_session["entrepreneur"]["preferred_language"] == "qu"
    assert juana_session["entrepreneur"]["data_consent_version"] == "v1.0-2026-11"

    uncertain_qu = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_JUANA_UNCERTAIN",
            "From": juana_phone,
            "Body": "Kunan punchaw 80 qullqi ruru",
        },
    )
    assert "Pampachaway casera, manam allintachu" in uncertain_qu.text
    assert client.get("/api/movements", headers=juana_headers).json() == []

    clear_qu = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_JUANA_SALE_QU",
            "From": juana_phone,
            "Body": "Rantikurqani 90 soles papata",
        },
    )
    assert "S/ 90.00" in clear_qu.text
    assert "revisión lingüística" in clear_qu.text

    conf_qu = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_JUANA_CONF_QU",
            "From": juana_phone,
            "Body": "Ari takyachini",
        },
    )
    assert "S/ 90.00" in conf_qu.text
    assert "CONFIRMADO" in conf_qu.text

    juana_movs = client.get("/api/movements", headers=juana_headers).json()
    assert len(juana_movs) == 1
    assert juana_movs[0]["amount_pen"] == 90.0

    maria_final_movs = client.get("/api/movements", headers=maria_headers).json()
    assert len(maria_final_movs) == 2
    assert {m["amount_pen"] for m in maria_final_movs} == {150.0, 30.0}

    cross_attempt = client.get(
        "/api/movements",
        headers={**juana_headers, "X-Entrepreneur-Id": maria_eid},
    )
    assert cross_attempt.status_code == 403

    dup_webhook = client.post(
        "/api/twilio/webhook",
        data={
            "MessageSid": "SM_JUANA_SALE_QU",
            "From": juana_phone,
            "Body": "Rantikurqani 90 soles papata",
        },
    )
    assert "idempotencia MessageSid activa" in dup_webhook.text


def test_whatsapp_onboarding_restart_persistence_and_challenge_limits_in_postgres(monkeypatch):
    """Requisitos 3, 4 y 6: Verifica que whatsapp_onboarding_sessions, whatsapp_links,
    whatsapp_link_challenges y processed_messages usen PostgreSQL como fuente de verdad,
    sobrevivan a reinicios a mitad del onboarding, respeten expiración/intentos y nunca
    usen 'rosa-huamanga-001' en MessageSid de teléfonos no vinculados ni guarden hashes de contraseñas.
    """
    pg_entrepreneurs: dict[str, dict] = {}
    pg_onboarding_sessions: dict[str, dict] = {}
    pg_challenges: dict[str, dict] = {}
    pg_whatsapp_links: dict[str, dict] = {}
    pg_processed_messages: dict[str, dict] = {}
    pg_audit_logs: list[dict] = []
    pg_movements: list = []

    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://oqbfuyxoclufkikaddoj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)

    monkeypatch.setattr(supabase_adapter, "ensure_seed_data", lambda *a, **kw: None)
    monkeypatch.setattr(supabase_adapter, "sync_weekly_goals", lambda *a, **kw: None)
    monkeypatch.setattr(supabase_adapter, "sync_chat_bubble", lambda *a, **kw: None)
    monkeypatch.setattr(
        supabase_adapter,
        "upsert_entrepreneur",
        lambda prof: pg_entrepreneurs.__setitem__(prof.id, prof.model_dump()),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "fetch_entrepreneur_by_owner_user",
        lambda uid: next(
            (r for r in pg_entrepreneurs.values() if r.get("owner_user_id") == uid),
            None,
        ),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "fetch_entrepreneur_by_id",
        lambda eid: pg_entrepreneurs.get(eid),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "get_whatsapp_onboarding_session",
        lambda ph: pg_onboarding_sessions.get(ph),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "upsert_whatsapp_onboarding_session",
        lambda row: pg_onboarding_sessions.__setitem__(row["phone_sha256"], dict(row)) or dict(row),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "create_whatsapp_link_challenge",
        lambda row: pg_challenges.__setitem__(row["code_sha256"], dict(row)) or dict(row),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "get_whatsapp_link_challenge",
        lambda ch_hash: pg_challenges.get(ch_hash),
    )

    def fake_consume_challenge_atomic(code_sha256: str, expected_type: str, now_dt: datetime):
        row = pg_challenges.get(code_sha256)
        if not row:
            return None
        exp_dt = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if (
            row.get("used")
            or int(row.get("attempts") or 0) >= 5
            or now_dt >= exp_dt
            or row.get("challenge_type") != expected_type
        ):
            if not row.get("used") and int(row.get("attempts") or 0) < 5:
                row["attempts"] = int(row.get("attempts") or 0) + 1
            return None
        row["attempts"] = int(row.get("attempts") or 0) + 1
        row["used"] = True
        row["used_at"] = now_dt.isoformat()
        return dict(row)

    monkeypatch.setattr(
        supabase_adapter,
        "consume_whatsapp_link_challenge_atomic",
        fake_consume_challenge_atomic,
    )
    monkeypatch.setattr(
        supabase_adapter,
        "insert_whatsapp_link_atomic",
        lambda phone_sha256, entrepreneur_id, phone_masked: pg_whatsapp_links.__setitem__(
            phone_sha256,
            {
                "phone_sha256": phone_sha256,
                "entrepreneur_id": entrepreneur_id,
                "phone_masked": phone_masked,
            },
        )
        or pg_whatsapp_links[phone_sha256],
    )
    monkeypatch.setattr(
        supabase_adapter,
        "get_whatsapp_link_by_phone",
        lambda ph: pg_whatsapp_links.get(ph),
    )

    def fake_check_and_record_sid(message_sid, entrepreneur_id, sender_phone_hash, raw_body):
        if message_sid in pg_processed_messages:
            return True
        pg_processed_messages[message_sid] = {
            "message_sid": message_sid,
            "entrepreneur_id": entrepreneur_id,
            "sender_phone_hash": sender_phone_hash,
            "raw_body": raw_body,
        }
        return False

    monkeypatch.setattr(
        supabase_adapter,
        "check_and_record_message_sid",
        fake_check_and_record_sid,
    )
    monkeypatch.setattr(
        supabase_adapter,
        "log_audit_event",
        lambda entrepreneur_id, action_type, entity_type, entity_id, metadata: pg_audit_logs.append(
            {
                "entrepreneur_id": entrepreneur_id,
                "action_type": action_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata,
            }
        ),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "sync_movement",
        lambda mov: pg_movements.append(mov),
    )
    monkeypatch.setattr(
        supabase_adapter,
        "fetch_movements",
        lambda entrepreneur_id, week_number=None, status=None: [
            m for m in pg_movements if m.entrepreneur_id == entrepreneur_id
        ],
    )

    # 1. Proceso FastAPI #1: Usuaria inicia onboarding por WhatsApp (Pasos 1 y 2)
    store_proc_1 = InMemoryStore(use_supabase=True, use_enriched_demo=False)
    phone = "whatsapp:+51955444333"
    assert (
        store_proc_1.is_message_sid_processed(
            "SM_ONBOARD_1", sender_phone=phone, raw_body="HOLA", entrepreneur_id=None
        )
        is False
    )
    # Verificar que processed_messages guardó entrepreneur_id=None y NUNCA 'rosa-huamanga-001'
    assert pg_processed_messages["SM_ONBOARD_1"]["entrepreneur_id"] is None

    r1 = store_proc_1.handle_unlinked_whatsapp_message(phone, "HOLA", message_sid="SM_ONBOARD_1")
    assert "Paso 1 de 3" in r1
    r2 = store_proc_1.handle_unlinked_whatsapp_message(phone, "1", message_sid="SM_ONBOARD_2")
    assert "Paso 2 de 3" in r2
    r3 = store_proc_1.handle_unlinked_whatsapp_message(
        phone, "Carmen Quispe - Tejidos Ayacucho - Huamanga", message_sid="SM_ONBOARD_3"
    )
    assert "Paso 3 de 3" in r3

    # 2. Simular reinicio completo de FastAPI a mitad del onboarding (memoria vacía en Proceso #2)
    store_proc_2 = InMemoryStore(use_supabase=True, use_enriched_demo=False)
    assert store_proc_2.whatsapp_drafts_by_phone_hash == {}

    # Proceso #2 recupera la sesión desde PostgreSQL (whatsapp_onboarding_sessions) y completa Paso 3
    r4 = store_proc_2.handle_unlinked_whatsapp_message(phone, "ACEPTO", message_sid="SM_ONBOARD_4")
    match_code = re.search(r"(WA-LINK-[A-F0-9]{8})", r4)
    assert match_code is not None
    wa_claim_code = match_code.group(1)

    # 3. Simular otro reinicio antes del registro web: Proceso #3 vincula desde PostgreSQL
    store_proc_3 = InMemoryStore(use_supabase=True, use_enriched_demo=False)
    carmen_uid = str(uuid.uuid4())
    acc, prof = store_proc_3.initiate_web_registration(
        email="carmen.quispe@ayacucho.pe",
        full_name="Carmen Quispe",
        business_name="Tejidos Ayacucho",
        trade_sector="Artesanía textil",
        market_location=" Feria Artesanal",
        city="Huamanga",
        region="Ayacucho",
        goal_title="Comprar telar",
        goal_target_pen=1600.0,
        preferred_language="es",
        accepted_data_consent=True,
        consent_version="v1.0-2026-11",
        whatsapp_claim_code=wa_claim_code,
        supabase_user_id=carmen_uid,
    )
    assert prof.whatsapp_linked is True
    assert prof.data_consent_accepted is True
    assert prof.data_consent_version == "v1.0-2026-11"

    # Verificar que en audit_logs NO exista ningún hash de contraseña ni referencia a rosa-huamanga-001
    for log in pg_audit_logs:
        assert log["entrepreneur_id"] != "rosa-huamanga-001"
        meta_str = str(log["metadata"]).lower()
        assert "password" not in meta_str

    # 4. Verificar que en un Proceso #4 el teléfono ya resuelve a Carmen desde whatsapp_links en PostgreSQL
    store_proc_4 = InMemoryStore(use_supabase=True, use_enriched_demo=False)
    assert store_proc_4.get_verified_entrepreneur_by_phone(phone) == prof.id
    assert store_proc_4.get_entrepreneur_id_by_owner_user(carmen_uid) == prof.id

    # 5. Verificar expiración y límite de 5 intentos en whatsapp_link_challenges
    vinc_code, _ = store_proc_4.generate_whatsapp_link_code(prof.id)
    vinc_hash = hashlib.sha256(vinc_code.encode("utf-8")).hexdigest()
    pg_challenges[vinc_hash]["attempts"] = 5
    blocked_msg = store_proc_4.handle_unlinked_whatsapp_message(
        "whatsapp:+51911222333", vinc_code
    )
    assert "superó el límite de intentos" in blocked_msg or "inválido" in blocked_msg


def test_supabase_connection_failure_returns_503_without_silent_memory_fallback(
    auth_headers, monkeypatch
):
    """Requisito 4 y 6: Cuando USE_EXTERNAL_SUPABASE=true y PostgreSQL rechaza una operación o cae la red,
    el backend NO regresa silenciosamente a memoria ni responde 200/201; devuelve 503 Service Unavailable.
    """
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://oqbfuyxoclufkikaddoj.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)

    def failing_fetch_owner(_uid: str):
        raise httpx.ConnectError("Simulated Supabase PostgreSQL connection outage")

    monkeypatch.setattr(
        supabase_adapter,
        "fetch_entrepreneur_by_owner_user",
        lambda uid: {
            "id": "emp-test-verified-001",
            "full_name": "Rosa Test",
            "business_name": "Frutería",
            "trade_sector": "Frutas",
            "market_location": "Mercado",
            "city": "Huamanga",
            "region": "Ayacucho",
            "phone_masked": "+51 966 *** 418",
            "goal_title": "Meta",
            "goal_target_pen": 2000.0,
            "goal_weekly_target_pen": 250.0,
            "goal_weeks": 8,
            "active_week": 8,
            "preferred_language": "es",
            "owner_user_id": uid,
            "data_consent_accepted": True,
            "data_consent_accepted_at": "2026-11-08T12:00:00Z",
            "data_consent_version": "v1.0-2026-11",
            "whatsapp_linked": True,
        },
    )

    orig_post = httpx.Client.post

    def failing_post(self_client, url, *args, **kwargs):
        if "/rest/v1/" in str(url):
            raise httpx.ConnectError("PostgreSQL connection refused")
        return orig_post(self_client, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", failing_post)

    # Intentar registrar un movimiento cuando PostgreSQL falla debe devolver 503 y NO guardar en memoria
    count_before = len(store.movements)
    res_fail = client.post(
        "/api/movements",
        headers=auth_headers,
        json={
            "week_number": 8,
            "movement_type": "VENTA",
            "amount_pen": 99.0,
            "category": "Ventas de frutas",
            "description": "Venta durante caída de red",
            "auto_confirm": True,
        },
    )
    assert res_fail.status_code == 503
    assert "Supabase" in res_fail.json()["detail"]
    assert len(store.movements) == count_before

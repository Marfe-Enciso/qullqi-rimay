"""Flujo completo por WhatsApp en modo demo (registro → venta → SÍ → resumen → no entendí)."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.store import store

client = TestClient(app)
PHONE = "whatsapp:+51987654321"


def _send(body: str, sid: str) -> str:
    r = client.post("/api/twilio/webhook", data={"From": PHONE, "Body": body, "MessageSid": sid})
    assert r.status_code == 200, r.text
    return r.text


def test_full_demo_flow(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    monkeypatch.setenv("WHATSAPP_DEMO_AUTOLINK", "true")
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", "https://example.trycloudflare.com/api/twilio/webhook")
    monkeypatch.setattr("app.routers.twilio_webhook.verify_twilio_signature", lambda *_: True)
    store.reset_to_demo_seed()

    assert "Paso 1 de 3" in _send("Hola", "SM1")
    assert "Paso 2 de 3" in _send("1", "SM2")
    assert "Paso 3 de 3" in _send("Juana Mendoza - Verdulería Sumaq - Huamanga", "SM3")
    done = _send("acepto", "SM4")
    assert "Tu cuenta ya está creada" in done and "MENÚ" in done
    menu = _send("menú", "SM5")
    assert "Hola Juana" in menu and "RESUMEN" in menu
    pend = _send("Vendí 50 soles de fruta", "SM6")
    assert "PENDIENTE" in pend and "50.00" in pend
    conf = _send("Sí", "SM7")
    assert "Guardé" in conf
    summ = _send("resumen", "SM8")
    assert "Semana 1" in summ
    again = _send("no entendí", "SM9")
    assert "S/ 10" in again or "10" in again
    # REINICIAR permite repetir el registro en la demo
    assert "Paso 1 de 3" in _send("REINICIAR", "SM10")


def _send_media(ctype: str, sid: str, body: str = "") -> str:
    r = client.post(
        "/api/twilio/webhook",
        data={"From": PHONE, "Body": body, "MessageSid": sid, "NumMedia": "1",
              "MediaUrl0": "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1",
              "MediaContentType0": ctype},
    )
    assert r.status_code == 200, r.text
    return r.text


def test_audio_and_photo_become_pending_movements(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    monkeypatch.setenv("WHATSAPP_DEMO_AUTOLINK", "true")
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", "https://example.trycloudflare.com/api/twilio/webhook")
    monkeypatch.setattr("app.routers.twilio_webhook.verify_twilio_signature", lambda *_: True)
    store.reset_to_demo_seed()
    for i, b in enumerate(["Hola", "1", "Juana Mendoza - Verdulería Sumaq - Huamanga", "acepto"]):
        _send(b, f"SA{i}")

    # Sin clave de Gemini: responde con una indicación amable
    monkeypatch.setattr("app.routers.twilio_webhook.media_ai_enabled", lambda: False)
    assert "aún no está activada" in _send_media("audio/ogg", "SB0")

    monkeypatch.setattr("app.routers.twilio_webhook.media_ai_enabled", lambda: True)
    monkeypatch.setattr("app.routers.twilio_webhook.ASYNC_MEDIA", False)
    monkeypatch.setattr(
        "app.routers.twilio_webhook.media_to_message",
        lambda url, ct: ("audio", "Hoy vendí 80 soles de naranja y gasté 10 en pasaje"),
    )
    audio = _send_media("audio/ogg", "SB1")
    assert "Escuché" in audio and "PENDIENTE" in audio and "80.00" in audio
    assert "Guardé" in _send("sí", "SB2")

    monkeypatch.setattr(
        "app.routers.twilio_webhook.media_to_message",
        lambda url, ct: ("image", "Gasté 45.90 en mercadería\nGasté 3 en bolsas"),
    )
    photo = _send_media("image/jpeg", "SB3")
    assert "En tu foto leí" in photo and "45.90" in photo and "3.00" in photo

    monkeypatch.setattr("app.routers.twilio_webhook.media_to_message", lambda url, ct: ("image", ""))
    assert "no pude leer montos" in _send_media("image/jpeg", "SB4")


def test_media_download_only_from_twilio():
    import pytest
    from app.services.media_reader import download_twilio_media
    with pytest.raises(ValueError):
        download_twilio_media("https://evil.example.com/x.ogg")


def test_numeric_menu_and_async_audio(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    monkeypatch.setenv("WHATSAPP_DEMO_AUTOLINK", "true")
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", "https://example.trycloudflare.com/api/twilio/webhook")
    monkeypatch.setattr("app.routers.twilio_webhook.verify_twilio_signature", lambda *_: True)
    store.reset_to_demo_seed()
    for i, b in enumerate(["Hola", "1", "Juana Mendoza - Verdulería Sumaq - Huamanga", "acepto"]):
        _send(b, f"SN{i}")
    assert "Vendí 50 soles" in _send("1", "SN5")
    assert "Semana 1" in _send("3", "SN6")
    assert "Te lo explico" in _send("4", "SN7")
    assert "RESUMEN" in _send("6", "SN8")

    sent = []
    monkeypatch.setattr("app.routers.twilio_webhook.media_ai_enabled", lambda: True)
    monkeypatch.setattr("app.routers.twilio_webhook.send_whatsapp_message", lambda to, body: sent.append(body))
    # Rápido: la respuesta llega en el mismo mensaje
    monkeypatch.setattr("app.routers.twilio_webhook.media_to_message", lambda u, c: ("audio", "vendí 30 soles de palta"))
    fast = _send_media("audio/ogg", "SN9")
    assert "Escuché" in fast and "30.00" in fast and not sent
    _send("no", "SN10")
    # Lento: primero "lo estoy escuchando", luego llega por la API de Twilio
    import time
    def slow(u, c):
        time.sleep(0.5)
        return ("audio", "vendí 20 soles de palta")
    monkeypatch.setattr("app.routers.twilio_webhook.media_to_message", slow)
    monkeypatch.setattr("app.routers.twilio_webhook.MEDIA_INLINE_WAIT_S", 0.05)
    ack = _send_media("audio/ogg", "SN11")
    assert "lo estoy escuchando" in ack
    for _ in range(40):
        if sent:
            break
        time.sleep(0.05)
    assert sent and "20.00" in sent[0]


def test_cuadre_points_and_advisor(monkeypatch):
    monkeypatch.setenv("USE_EXTERNAL_SUPABASE", "false")
    monkeypatch.setenv("WHATSAPP_DEMO_AUTOLINK", "true")
    monkeypatch.setenv("TWILIO_WEBHOOK_URL", "https://example.trycloudflare.com/api/twilio/webhook")
    monkeypatch.setattr("app.routers.twilio_webhook.verify_twilio_signature", lambda *_: True)
    store.reset_to_demo_seed()
    for i, b in enumerate(["Hola", "1", "Juana Mendoza - Verdulería Sumaq - Huamanga", "acepto"]):
        _send(b, f"SC{i}")
    assert "CUADRE" in _send("menú", "SC4")
    _send("Hoy vendí 180 soles de naranja, compré 110 de fruta y gasté 6 en pasaje", "SC5")
    ok = _send("Sí", "SC6")
    assert "Qullqi puntos" in ok and "Racha: 1" in ok
    assert "1/2" in _send("cuadre", "SC7")
    assert "2/2" in _send("50", "SC8")
    res = _send("100", "SC9")  # esperado 50+180-116=114 → 14 hormiga
    assert "S/ 14.00 se fueron sin anotar" in res and "gastos hormiga" in res
    assert "Guardé" in _send("sí", "SC10")
    assert "Nivel" in _send("puntos", "SC11")
    adv = _send("quiero un préstamo", "SC12")
    assert "Agente Móvil" in adv and "*A*" in adv
    done = _send("B", "SC13")
    assert "Solicitud" in done and "Visita del Agente Móvil" in done

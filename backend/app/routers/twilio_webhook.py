"""Webhook para Twilio WhatsApp Sandbox (`POST /api/twilio/webhook`).

- Sin ninguna dependencia de DEMO_ENTREPRENEUR_ID.
- Normaliza el teléfono remitente (`From`), comprueba si existe un vínculo verificado con
  una cuenta de emprendedora (`entrepreneur_id`), o inicia el registro conversacional
  provisional de 3 pasos con emisión de código único (`WA-LINK-XXXXXXXX`) / vinculación (`VINC-XXXXXX`).
"""

import logging
import os
import threading
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from fastapi import APIRouter, HTTPException, Request, Response

from app.models import SimulatorMessageRequest
from app.routers.simulator import process_whatsapp_message_for_entrepreneur
from app.services.media_reader import (
    media_ai_enabled,
    media_kind,
    media_to_message,
    send_whatsapp_message,
)
from app.services import engagement
from app.services.finance_engine import compute_eight_week_goal
from app.services.store import store
from app.services.twilio_adapter import build_twiml_message, verify_twilio_signature

router = APIRouter(prefix="/api/twilio", tags=["Twilio WhatsApp Sandbox"])

_log = logging.getLogger("qullqi.whatsapp")
if not _log.handlers:
    try:
        _fh = logging.FileHandler(
            Path(__file__).resolve().parents[2] / "whatsapp_log.txt", encoding="utf-8"
        )
        _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _log.addHandler(_fh)
        _log.setLevel(logging.INFO)
    except OSError:
        pass

# Audios y fotos se procesan en segundo plano y la respuesta llega por la API de Twilio,
# porque Twilio solo espera 15 segundos la respuesta del webhook.
ASYNC_MEDIA = True
MEDIA_INLINE_WAIT_S = 11.0

MENU_WORDS = {"MENU", "MENÚ", "AYUDA", "OPCIONES", "HOLA", "INICIO", "BUENAS", "HELP"}
FRIENDLY_ERROR = (
    "😅 Tuve un problema para procesar tu mensaje. Inténtalo otra vez en un momento "
    "o escribe *MENÚ* para ver las opciones."
)


@router.post("/webhook")
async def twilio_whatsapp_webhook(request: Request) -> Response:
    content_type = request.headers.get("content-type", "")
    form_dict: dict[str, str] = {}

    if content_type.split(';', 1)[0].strip().lower() == "application/x-www-form-urlencoded":
        raw_body = (await request.body()).decode("utf-8", errors="replace")
        pairs = parse_qsl(raw_body, keep_blank_values=True)
        if len({key for key, _ in pairs}) != len(pairs):
            raise HTTPException(status_code=400, detail="Parámetros duplicados no admitidos.")
        form_dict = dict(pairs)
    else:
        raise HTTPException(status_code=415, detail="Se requiere un formulario de Twilio.")

    signature = request.headers.get("X-Twilio-Signature", "")
    public_url = os.getenv("TWILIO_WEBHOOK_URL", "").strip()
    parts = urlsplit(public_url)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.path != "/api/twilio/webhook" or parts.query or parts.fragment
            or request.scope.get("query_string")):
        raise HTTPException(status_code=503, detail="URL pública de Twilio no configurada correctamente.")
    if not verify_twilio_signature(public_url, form_dict, signature):
        raise HTTPException(status_code=403, detail="Firma X-Twilio-Signature inválida.")

    try:
        twiml_text = _process_message(form_dict)
    except Exception:
        _log.exception("Error procesando mensaje de WhatsApp")
        if not store.demo_autolink_enabled():
            raise
        twiml_text = FRIENDLY_ERROR
    _log.info("Respuesta enviada: %s", twiml_text[:90].replace("\n", " "))
    return Response(content=build_twiml_message(twiml_text), media_type="application/xml")


def _process_message(form_dict: dict) -> str:
    message_sid = (form_dict.get("MessageSid") or "").strip()
    sender_from = (form_dict.get("From") or "").strip()
    incoming_body = (form_dict.get("Body") or "").strip()
    try:
        num_media = int(form_dict.get("NumMedia") or 0)
    except ValueError:
        num_media = 0
    media_url = (form_dict.get("MediaUrl0") or "").strip() if num_media > 0 else ""
    media_type = (form_dict.get("MediaContentType0") or "").strip() if num_media > 0 else ""

    if not sender_from:
        twiml = (
            "No se recibió el número remitente ('From') en el mensaje de WhatsApp."
        )
        return twiml

    verified_entrepreneur_id = store.get_verified_entrepreneur_by_phone(sender_from)
    _log.info("Mensaje recibido (vinculada=%s): %s", bool(verified_entrepreneur_id), incoming_body[:60])
    upper_body = incoming_body.upper().strip(" .!¡,?¿")

    # Modo demo: REINICIAR desvincula la cuenta creada en memoria para repetir el registro
    if verified_entrepreneur_id and store.demo_autolink_enabled() and upper_body in ("REINICIAR", "REINICIAR REGISTRO", "SALIR"):
        if store.demo_unlink_phone(sender_from):
            verified_entrepreneur_id = None
            incoming_body = "HOLA"

    if message_sid:
        if store.is_message_sid_processed(
            message_sid=message_sid,
            sender_phone=sender_from,
            raw_body=incoming_body,
            entrepreneur_id=verified_entrepreneur_id,
        ):
            twiml = (
                "Mensaje ya procesado anteriormente (idempotencia MessageSid activa)."
            )
            return twiml

    # Si el teléfono aún no está vinculado a una cuenta verificada, ejecutar onboarding o vinculación por código
    if not verified_entrepreneur_id and media_url and not incoming_body:
        return (
            "📎 ¡Recibí tu archivo! Primero completemos tu registro (toma 1 minuto). "
            "Escribe *HOLA* para empezar."
        )
    if not verified_entrepreneur_id:
        onboarding_reply = store.handle_unlinked_whatsapp_message(
            raw_phone=sender_from,
            incoming_body=incoming_body or "HOLA",
            message_sid=message_sid or None,
        )
        twiml = (onboarding_reply)
        return twiml

    entrepreneur = store.get_entrepreneur(verified_entrepreneur_id)
    active_week = entrepreneur.active_week or 1

    # Audios y fotos → texto → mismo flujo (PENDIENTE → SÍ / NO)
    media_prefix = ""
    qu = entrepreneur.preferred_language == "qu"
    if media_url and ASYNC_MEDIA and media_ai_enabled() and media_kind(media_type) in ("audio", "image"):
        # Intentamos responder en la misma conversación (≤ 11 s). Si tarda más, respondemos
        # "lo estoy escuchando" y el resultado llega después por la API de Twilio.
        result: dict = {}
        done = threading.Event()

        def _job() -> None:
            result["reply"] = _media_reply(verified_entrepreneur_id, media_url, media_type, incoming_body)
            done.set()
            if result.get("late"):
                _send_late(sender_from, result["reply"])

        threading.Thread(target=_job, daemon=True).start()
        if done.wait(MEDIA_INLINE_WAIT_S):
            return result["reply"]
        result["late"] = True
        if done.is_set():  # terminó justo ahora
            result["late"] = False
            return result["reply"]
        if media_kind(media_type) == "audio":
            return (
                "🎧 Audioykita chaskiniña, uyarichkani… kunallan kutichisqayki."
                if qu
                else "🎧 Recibí tu audio, lo estoy escuchando… te respondo en unos segundos."
            )
        return (
            "📷 Fotoykita chaskiniña, liyichkani… kunallan kutichisqayki."
            if qu
            else "📷 Recibí tu foto, la estoy leyendo… te respondo en unos segundos."
        )
    if media_url:
        media_prefix, media_text = _read_media(media_url, media_type, entrepreneur.preferred_language)
        if media_text is None:
            return media_prefix
        incoming_body = (media_text + " " + incoming_body).strip()
        upper_body = incoming_body.upper().strip(" .!¡,?¿")

    first_name = entrepreneur.full_name.split()[0] if entrepreneur.full_name else "casera"

    # Conversaciones en curso: cuadre de caja y conexión con asesor
    if not media_url and engagement.cuadre_active(verified_entrepreneur_id):
        res = engagement.continue_cuadre(
            verified_entrepreneur_id, incoming_body, store.list_movements(entrepreneur_id=verified_entrepreneur_id)
        )
        if res["hormiga"]:
            store.add_movement(
                week_number=active_week,
                movement_type="GASTO",
                amount_pen=res["hormiga"],
                category="Gastos hormiga",
                description="Diferencia encontrada en el cuadre de caja",
                raw_message="CUADRE DE CAJA",
                source_channel="TWILIO_WHATSAPP",
                ai_confidence=1.0,
                auto_confirm=False,
                entrepreneur_id=verified_entrepreneur_id,
            )
        return res["reply"]
    if not media_url and engagement.advisor_active(verified_entrepreneur_id):
        goal = compute_eight_week_goal(
            store.list_movements(entrepreneur_id=verified_entrepreneur_id), entrepreneur
        )
        summary = {
            "semanas": goal.completed_weeks_count,
            "ventas": sum(w.total_sales_pen for w in goal.weeks),
            "neto": goal.accumulated_net_pen,
        }
        return engagement.continue_advisor(verified_entrepreneur_id, incoming_body, entrepreneur, summary)

    # Opciones del menú escritas como número (1️⃣ … 9️⃣)
    option = upper_body.replace("️⃣", "").strip()
    if not media_url and option in {"7", "8", "9"}:
        upper_body = {"7": "CUADRE", "8": "PUNTOS", "9": "ASESOR"}[option]
    if not media_url and upper_body in ("CUADRE", "CAJA", "CUADRAR", "CUADRE DE CAJA", "CERRAR CAJA"):
        return engagement.start_cuadre(verified_entrepreneur_id)
    if not media_url and upper_body in ("PUNTOS", "MIS PUNTOS", "RACHA", "MI RACHA", "PREMIOS", "NIVEL"):
        return engagement.status_text(verified_entrepreneur_id)
    if not media_url and (
        upper_body == "ASESOR" or (engagement.wants_advisor(incoming_body) and not any(ch.isdigit() for ch in incoming_body))
    ):
        return engagement.start_advisor(verified_entrepreneur_id, first_name)

    if not media_url and option in {"1", "2", "3", "4", "5", "6"}:
        if option in ("1", "2"):
            return (
                "✍️ Qillqamuway imatam rantikurqanki icha gastarqanki, kayhina:\n"
                "• *Rantikurqani 80 soles papata*\n• *Gasté 12 en pasaje*\n"
                "Chaymanta *ARI* icha *MANAM* kutichimuway."
                if qu
                else "✍️ Escríbeme lo que vendiste o gastaste, como hablas:\n"
                "• *Vendí 50 soles de fruta*\n• *Gasté 12 en pasaje*\n"
                "También puedes mandarme una *nota de voz* 🎧 o una *foto* de tu boleta o cuaderno 📷.\n"
                "Luego te pregunto y respondes *SÍ* para guardar o *NO* para borrar."
            )
        if option == "3":
            incoming_body = "resumen"
        elif option == "4":
            incoming_body = "no entendí"
        elif option == "5":
            incoming_body = "idioma español" if qu else "idioma quechua"
        else:
            upper_body = "MENU"

    if upper_body in MENU_WORDS:
        greet = (
            f"¡Rimaykullayki {first_name}! 👋\n\n"
            if entrepreneur.preferred_language == "qu"
            else f"¡Hola {first_name}! 👋 Estás en la *Semana {active_week}* de tu meta.\n\n"
        )
        return greet + store.whatsapp_menu_text(entrepreneur)

    if not incoming_body:
        first_name = entrepreneur.full_name.split()[0] if entrepreneur.full_name else "casera"
        if entrepreneur.preferred_language == "qu":
            twiml = (
                f"¡Rimaykullayki {first_name}! '{entrepreneur.business_name}' qhatuykipaq rantikuykita icha gastoykita qillqamuway (Semana {active_week})."
            )
        else:
            twiml = (
                f"¡Rimaykullayki {first_name}! Envíame tu venta o gasto del día para '{entrepreneur.business_name}' (Semana {active_week})."
            )
        return twiml

    sim_response = process_whatsapp_message_for_entrepreneur(
        payload=SimulatorMessageRequest(message=incoming_body, week_number=active_week),
        entrepreneur_id=verified_entrepreneur_id,
        source_channel="TWILIO_WHATSAPP",
    )
    return media_prefix + sim_response.bot_bubble.text


def _media_reply(entrepreneur_id: str, url: str, content_type: str, extra_text: str) -> str:
    try:
        entrepreneur = store.get_entrepreneur(entrepreneur_id)
        prefix, text = _read_media(url, content_type, entrepreneur.preferred_language)
        if text is None:
            return prefix
        sim = process_whatsapp_message_for_entrepreneur(
            payload=SimulatorMessageRequest(
                message=(text + " " + extra_text).strip(),
                week_number=entrepreneur.active_week or 1,
            ),
            entrepreneur_id=entrepreneur_id,
            source_channel="TWILIO_WHATSAPP",
        )
        return prefix + sim.bot_bubble.text
    except Exception:
        _log.exception("Error procesando audio/foto")
        return FRIENDLY_ERROR


def _send_late(sender: str, reply: str) -> None:
    try:
        send_whatsapp_message(sender, reply)
        _log.info("Respuesta (audio/foto) enviada aparte: %s", reply[:90].replace("\n", " "))
    except Exception:
        _log.exception("No se pudo enviar la respuesta por la API de Twilio")


def _read_media(url: str, content_type: str, lang: str) -> tuple:
    """Devuelve (prefijo_o_mensaje, texto). Si texto es None, el prefijo es la respuesta final."""
    kind = media_kind(content_type)
    qu = lang == "qu"
    if kind == "other":
        return (
            "📎 Por ahora entiendo *notas de voz* y *fotos* (boletas o tu cuaderno de ventas). "
            "También puedes escribirme, por ejemplo: *Vendí 50 soles de fruta*.",
            None,
        )
    if not media_ai_enabled():
        return (
            "🎧📷 Recibí tu archivo, pero la lectura de audios y fotos aún no está activada en este servidor. "
            "Mientras tanto escríbemelo, por ejemplo: *Vendí 50 soles de fruta* o *Gasté 12 en pasaje*.",
            None,
        )
    try:
        kind, text = media_to_message(url, content_type)
    except Exception:
        _log.exception("No se pudo procesar el archivo de WhatsApp")
        return (
            ("🎧 No pude escuchar bien tu audio. " if kind == "audio" else "📷 No pude leer bien tu foto. ")
            + "Inténtalo otra vez o escríbemelo, por ejemplo: *Vendí 50 soles de fruta*.",
            None,
        )
    if not text:
        if kind == "audio":
            return (
                "🎧 Escuché tu audio, pero no encontré ventas ni gastos con montos. "
                "Dime por ejemplo: «Hoy vendí 80 soles de naranja y gasté 10 en pasaje».",
                None,
            )
        return (
            "📷 Vi tu foto, pero no pude leer montos claros. Toma la foto de cerca, con buena luz "
            "y que se vea el total, o escríbemelo.",
            None,
        )
    _log.info("Archivo %s convertido a texto: %s", kind, text[:120].replace("\n", " | "))
    if kind == "audio":
        head = "🎧 *Uyarirqani:*" if qu else "🎧 *Escuché:*"
        return f"{head} «{text}»\n\n", text
    lines = "\n".join(f"• {ln}" for ln in text.splitlines() if ln.strip())
    head = "📷 *Fotoykipi liyirqani:*" if qu else "📷 *En tu foto leí:*"
    return f"{head}\n{lines}\n\n", ". ".join(ln.strip().rstrip(".") for ln in text.splitlines() if ln.strip())

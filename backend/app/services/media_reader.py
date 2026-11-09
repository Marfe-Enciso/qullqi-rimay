"""Audios y fotos de WhatsApp → texto sencillo para el intérprete de Qullqi Rimay.

Flujo (mismas reglas del resto del bot):
1. Twilio envía la nota de voz o la foto (MediaUrl0 + MediaContentType0).
2. Descargamos el archivo SOLO desde dominios de Twilio, con las credenciales del servidor.
3. Gemini lo convierte en texto: transcribe el audio o lee la boleta / cuaderno de la foto.
   Gemini NO calcula saldos ni guarda nada: solo devuelve frases como «Vendí 50 soles de fruta».
4. Ese texto pasa por el intérprete normal → queda como PENDIENTE → la emprendedora responde SÍ / NO.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional, Tuple
from urllib.parse import urlsplit

import httpx

from app.config import settings

_log = logging.getLogger("qullqi.whatsapp")

MAX_MEDIA_BYTES = 12 * 1024 * 1024
ALLOWED_MEDIA_HOST_SUFFIXES = (".twilio.com", ".twiliocdn.com", ".twilio.net")

AUDIO_PROMPT = (
    "Eres el asistente de Qullqi Rimay para emprendedoras de mercado en Ayacucho (Perú). "
    "Esta es una nota de voz de WhatsApp en español peruano andino y/o quechua ayacuchano (chanka). "
    "Transcribe fielmente lo que dice, en una sola línea, sin agregar nada. "
    "Escribe los montos con números (por ejemplo «50 soles»). "
    "Si habla en quechua, conserva sus palabras en quechua. "
    "Si no se entiende nada, responde exactamente: NADA"
)

IMAGE_PROMPT = (
    "Eres el asistente de Qullqi Rimay para emprendedoras de mercado en Ayacucho (Perú). "
    "La foto puede ser una boleta, un ticket, una factura, una nota de pedido o una hoja del cuaderno "
    "donde anota sus ventas y gastos. Lee SOLO lo que está escrito, no inventes montos. "
    "Devuelve cada movimiento en una línea separada, con este formato exacto:\n"
    "Vendí <monto> soles de <producto>\n"
    "Gasté <monto> en <concepto>\n"
    "Si la foto es una boleta o factura de algo que ella COMPRÓ, es un gasto. "
    "Si es una boleta que ella emitió a un cliente, es una venta. "
    "Si solo hay un total, usa solo el total. Usa punto decimal. "
    "Si no hay montos legibles, responde exactamente: NADA"
)


def _gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or "REEMPLAZAR" in key.upper() or key.startswith("tu_"):
        return ""
    return key


def media_ai_enabled() -> bool:
    return bool(_gemini_key())


def media_kind(content_type: str) -> str:
    ct = (content_type or "").lower()
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("image/"):
        return "image"
    return "other"


def _is_twilio_media_url(url: str) -> bool:
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == s.lstrip(".") or host.endswith(s) for s in ALLOWED_MEDIA_HOST_SUFFIXES
    )


def download_twilio_media(url: str) -> Tuple[bytes, str]:
    if not _is_twilio_media_url(url):
        raise ValueError("Solo se aceptan archivos alojados por Twilio.")
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    auth = (sid, token) if sid and token else None
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        resp = client.get(url, auth=auth)
        resp.raise_for_status()
        data = resp.content
        if len(data) > MAX_MEDIA_BYTES:
            raise ValueError("Archivo demasiado grande.")
        return data, resp.headers.get("content-type", "")


def _gemini_models() -> list[str]:
    # Los modelos "lite" responden en 2-3 s; los "flash" normales a veces tardan más de 25 s.
    preferred = (os.getenv("GEMINI_MEDIA_MODEL", "") or "").strip()
    models = [preferred] if preferred else []
    for extra in (
        "gemini-flash-lite-latest",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
        "gemini-2.5-flash",
    ):
        if extra not in models:
            models.append(extra)
    return models


def gemini_media_to_text(
    data: bytes, content_type: str, kind: str, timeout_s: float = 9.0
) -> Optional[str]:
    """Prueba varios modelos de Gemini: si uno está saturado (503/429) o tarda, pasa al siguiente."""
    key = _gemini_key()
    if not key:
        return None
    mime = (content_type or "").split(";", 1)[0].strip() or (
        "audio/ogg" if kind == "audio" else "image/jpeg"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": AUDIO_PROMPT if kind == "audio" else IMAGE_PROMPT},
                    {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 400},
    }
    last_error: Optional[Exception] = None
    for model in _gemini_models():
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": key},
                    json=payload,
                )
            if resp.status_code in (400, 404) and "model" in resp.text.lower():
                continue
            resp.raise_for_status()
            parts = resp.json()["candidates"][0]["content"]["parts"]
            text = " ".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if kind == "image":
                text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
            _log.info("Gemini %s leyó el %s", model, kind)
            return text
        except Exception as exc:  # noqa: BLE001 - se registra y se prueba el siguiente modelo
            last_error = exc
            _log.warning("Gemini (%s) no pudo leer el %s: %s", model, kind, str(exc)[:160])
    if last_error:
        raise last_error
    return None


def send_whatsapp_message(to: str, body: str) -> None:
    """Envía un mensaje de WhatsApp por la API de Twilio (para respuestas que tardan más de 15 s)."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not token:
        raise RuntimeError("Faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN")
    configured = os.getenv("TWILIO_WHATSAPP_NUMBER", "").strip().replace(" ", "").replace("-", "")
    if configured and not configured.startswith("whatsapp:"):
        configured = "whatsapp:" + configured
    senders = [s for s in (configured, "whatsapp:+14155238886") if s]
    last = ""
    with httpx.Client(timeout=15.0) as client:
        for sender in dict.fromkeys(senders):
            resp = client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={"From": sender, "To": to, "Body": body[:1500]},
            )
            if resp.status_code < 300:
                return
            last = f"HTTP {resp.status_code}: {resp.text[:300]}"
            _log.warning("Twilio rechazó el envío desde %s: %s", sender, last)
    raise RuntimeError("Twilio no aceptó el mensaje: " + last)


def media_to_message(url: str, content_type: str) -> Tuple[str, Optional[str]]:
    """Devuelve (tipo, texto). texto=None si no se pudo leer; '' si no había nada útil."""
    kind = media_kind(content_type)
    if kind == "other":
        return kind, None
    data, real_type = download_twilio_media(url)
    text = gemini_media_to_text(data, content_type or real_type, kind)
    if text is None:
        return kind, None
    if text.strip().upper().strip(".") == "NADA":
        return kind, ""
    return kind, text

"""Adaptador para Twilio WhatsApp Sandbox (Validación HMAC-SHA1 y formato TwiML).

Permite conectar el Sandbox de WhatsApp de Twilio (`POST /api/twilio/webhook`) al
mismo flujo conversacional de Rosa (interpretación JSON estructurada + confirmación
en 2 pasos antes de guardar).
"""

import base64
import hashlib
import hmac
import html
import os
from typing import Dict

from app.config import settings


def build_twiml_message(body_text: str) -> str:
    """Genera respuesta XML TwiML válida y escapada contra inyección XML."""
    safe_text = html.escape(body_text)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{safe_text}</Message></Response>"
    )


def verify_twilio_signature(
    url: str,
    form_params: Dict[str, str],
    signature_header: str,
) -> bool:
    """Verifica la firma `X-Twilio-Signature` cuando `USE_EXTERNAL_TWILIO=true`."""
    if not settings.use_external_twilio:
        return False
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not auth_token or auth_token == "tu_twilio_auth_token_aqui":
        return False

    s = url
    for key in sorted(form_params.keys()):
        s += key + (form_params[key] or "")

    mac = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1)
    computed = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(computed, signature_header or "")


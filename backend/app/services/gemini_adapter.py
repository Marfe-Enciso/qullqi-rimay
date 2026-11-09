"""Adaptador para Google Gemini API con salida JSON Estructurada (`responseSchema`).

Garantiza que:
1. La clave `GEMINI_API_KEY` se lea únicamente desde variables de entorno en el servidor.
2. Gemini devuelva estrictamente un JSON conforme a `StructuredMovementExtraction`.
3. Gemini NUNCA realice cálculos de saldos, metas ni prometa aprobaciones del BCP.
4. Si `USE_EXTERNAL_GEMINI=false` o no hay clave configurada, el sistema delegue
   transparentemente al motor determinístico local sin interrumpir la demo.
"""

import json
import os
from typing import Optional
import httpx

from app.config import settings
from app.models import StructuredMovementExtraction

GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "detected_intent": {
            "type": "STRING",
            "enum": [
                "REGISTRAR_MOVIMIENTO",
                "CONFIRMAR_PENDIENTES",
                "DESCARTAR_PENDIENTES",
                "CONSULTAR_RESUMEN",
                "SALUDO_O_AYUDA",
            ],
        },
        "confidence": {"type": "NUMBER"},
        "requires_confirmation": {"type": "BOOLEAN"},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "movement_type": {"type": "STRING", "enum": ["VENTA", "GASTO"]},
                    "amount_pen": {"type": "NUMBER"},
                    "category": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "detected_terms": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                    },
                },
                "required": [
                    "movement_type",
                    "amount_pen",
                    "category",
                    "description",
                    "detected_terms",
                ],
            },
        },
        "reply_preview_es": {"type": "STRING"},
    },
    "required": [
        "detected_intent",
        "confidence",
        "requires_confirmation",
        "items",
        "reply_preview_es",
    ],
}

SYSTEM_INSTRUCTION_ROSA = (
    "Eres Qullqi Rimay, asistente financiero conversacional para Rosa Quispe, "
    "vendedora de frutas en Huamanga (Ayacucho, Perú). "
    "Tu única tarea es interpretar el mensaje de Rosa (en español peruano/andino o con "
    "términos en quechua como qullqi, rantiy, casera) y extraer ventas o gastos en el "
    "esquema JSON solicitado. "
    "REGLAS ESTRICTAS DE SEGURIDAD: "
    "1) Todo registro nuevo requiere confirmación (`requires_confirmation: true`). "
    "2) NUNCA calcules saldos acumulados ni prometas préstamos o aprobaciones del BCP. "
    "3) Responde en `reply_preview_es` con español sencillo, cálido y respetuoso."
)


def call_gemini_structured_extraction(
    message: str,
    week_number: int = 8,
) -> Optional[StructuredMovementExtraction]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if (
        not settings.use_external_gemini
        or not api_key
        or api_key == "tu_clave_gemini_aqui"
    ):
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION_ROSA}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"Semana activa: {week_number}. Mensaje de Rosa: {message}"
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": GEMINI_RESPONSE_SCHEMA,
        },
    }

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.post(
                url,
                params={"key": api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )
            parsed = json.loads(raw_text)
            parsed["engine_mode"] = f"GEMINI_STRUCTURED_JSON ({settings.gemini_model})"
            return StructuredMovementExtraction.model_validate(parsed)
    except Exception:
        # Fallback seguro al intérprete determinístico local si falla la red o cuota
        return None


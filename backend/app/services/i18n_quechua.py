"""Soporte bilingüe Español y Quechua Ayacuchano (Chanka) para Qullqi Rimay (Prioridad 5).

Nota de transparencia lingüística:
- Las interacciones en Quechua Ayacuchano (variante Chanka) cubren los flujos principales de
  bienvenida, selección de idioma, consentimiento de datos, borrador de ventas/gastos,
  confirmación explícita y resumen semanal, con textos sujetos a revisión lingüística.
- Cuando un mensaje en quechua es ambiguo o carece de monto/tipo claro, el sistema solicita
  aclaración antes de crear cualquier movimiento financiero.
"""

from typing import List
from app.models import LanguageCode, StructuredExtractedItem

LINGUISTIC_DISCLAIMER_QU = (
    "(Nota: Textos en quechua ayacuchano / Chanka sujetos a revisión lingüística)"
)


def format_pending_confirmation_prompt(
    items: List[StructuredExtractedItem],
    week_number: int,
    lang: LanguageCode = "es",
) -> str:
    bullet_lines = [
        f"• {it.movement_type}: S/ {it.amount_pen:.2f} ({it.category} — {it.description})"
        for it in items
    ]
    summary_str = "\n".join(bullet_lines)

    if lang == "qu":
        return (
            f"📝 ¡Allinmi casera! Semana {week_number} yupaykipaq kayhinatam hap'iykuni "
            f"(estado *PENDIENTE*):\n{summary_str}\n\n"
            "¿Chiqapchu kay qullqi? Kutichimuway *«Ari takyachini»* (o *«Sí confirmo»*) "
            "waqaychanaypaq, icha *«Manam»* (*«Corregir»*) pantaptinqa. "
            f"{LINGUISTIC_DISCLAIMER_QU}"
        )

    return (
        f"📝 Casera, entendí lo siguiente para tu Semana {week_number} "
        f"(en borrador *PENDIENTE*):\n{summary_str}\n\n"
        "¿Está correcto? Responde *SÍ* para guardarlo en tus cuentas "
        "o *NO* para borrarlo y escribirlo de nuevo."
    )


def format_confirmed_reply(
    count: int,
    total_pen: float,
    week_number: int,
    coaching_es: str,
    lang: LanguageCode = "es",
) -> str:
    if lang == "qu":
        return (
            f"✅ ¡Kusisqa casera! {count} movimiento(s) S/ {total_pen:.2f} qullqitam "
            f"Semana {week_number} yupaykipi waqaychaykuniña (*CONFIRMADO*). "
            f"{coaching_es} {LINGUISTIC_DISCLAIMER_QU}"
        )
    saved = (
        f"Guardé {count} movimiento(s) por S/ {total_pen:.2f}"
        if count == 1
        else f"Guardé tus {count} movimientos (ventas y gastos)"
    )
    return (
        f"✅ ¡Listo casera! {saved} en tu Semana {week_number}. {coaching_es}\n\n"
        "Escribe *RESUMEN* para ver cuánto es para tu negocio y cuánto para tu casa."
    )


def format_no_pending_to_confirm(lang: LanguageCode = "es") -> str:
    if lang == "qu":
        return (
            "Manam kunanqa takyachinapaq qullqi suyachkanchu, casera. "
            "Willaway hayk'atam rantikurqanki icha gastaranki kunan punchaw."
        )
    return (
        "No tienes movimientos pendientes por confirmar en este momento, casera. "
        "Cuéntame qué vendiste o gastaste hoy para anotarlo."
    )


def format_discarded_reply(count: int, lang: LanguageCode = "es") -> str:
    if lang == "qu":
        return (
            f"🗑️ {count} borrador movimiento(s) pichaykuniña. "
            "Allin qullqita qillqamuway musuqmanta churanaypaq."
        )
    return (
        f"🗑️ He descartado {count} movimiento(s) en borrador. "
        "Escríbeme el monto corregido cuando gustes."
    )


def format_summary_reply(
    week_explanation_es: str,
    accumulated_net_pen: float,
    goal_target_pen: float,
    progress_pct: float,
    lang: LanguageCode = "es",
) -> str:
    if lang == "qu":
        return (
            f"📊 *Willakuy (Resumen):* {week_explanation_es}\n"
            f"8 semanapi huñusqayki qullqi: S/ {accumulated_net_pen:.2f} / S/ {goal_target_pen:.2f} "
            f"({progress_pct:.1f}%). {LINGUISTIC_DISCLAIMER_QU}"
        )
    return (
        f"📊 {week_explanation_es} "
        f"En tus 8 semanas llevas S/ {accumulated_net_pen:.2f} de S/ {goal_target_pen:.2f} "
        f"({progress_pct:.1f}%)."
    )


def format_uncertain_quechua_clarification(lang: LanguageCode = "qu") -> str:
    if lang == "qu":
        return (
            "🤔 Pampachaway casera, manam allintachu hap'iykuni willawasqaykita. "
            "Mana pantaspa qillqanaypaq, ama hina kaspa sut'inchaykuway:\n"
            "1️⃣ ¿*Rantikurqankichu* (venta) icha *gastarqankichu* (gasto)?\n"
            "2️⃣ ¿Hayk'a *soles* (S/) karqan?\n"
            "Kayhinata qillqamuway: *«Rantikurqani 50 soles papata»* o *«Vendí 50 soles de papa»*. "
            f"{LINGUISTIC_DISCLAIMER_QU}"
        )
    return (
        "🤔 Disculpa casera, no comprendí con certeza tu mensaje en quechua/bilingüe. "
        "Para no guardar un dato equivocado, por favor confírmame:\n"
        "1️⃣ ¿Fue una *venta* o un *gasto*?\n"
        "2️⃣ ¿Cuál fue el monto exacto en *soles*?\n"
        "Ejemplo: *«Vendí 50 soles de fruta»* o *«Rantikurqani 50 soles»*."
    )


def format_language_switched(lang: LanguageCode) -> str:
    if lang == "qu":
        return (
            "🌿 ¡Allinmi! Kunanmantaqa *Quechua Ayacuchano (Chanka)* rimaypim "
            f"yanapasqayki. {LINGUISTIC_DISCLAIMER_QU}"
        )
    return "🌿 ¡Listo! A partir de ahora te atenderé en *Español*."


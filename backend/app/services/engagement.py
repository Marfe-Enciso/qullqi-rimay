"""Hábito y juego en el chat: racha, Qullqi puntos, cuadre de caja y conexión con un asesor.

Todo es determinista (Python), sin IA. El estado vive en memoria del servidor (demo).
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

LIMA = timezone(timedelta(hours=-5))
_lock = threading.RLock()

POINTS_PER_RECORD_DAY = 10
POINTS_PER_LESSON = 5
POINTS_PER_CUADRE = 15

LEVELS = [  # (puntos mínimos, nombre, emoji, significado)
    (0, "Muhu", "🌱", "semilla"),
    (50, "Wiñay", "🌿", "crecer"),
    (150, "Mallki", "🌳", "planta fuerte"),
]


@dataclass
class Progress:
    points: int = 0
    streak: int = 0
    last_record_day: Optional[date] = None
    lesson_days: set = field(default_factory=set)
    cuadre_step: Optional[str] = None  # "inicio" | "ahora"
    cuadre_start: float = 0.0
    advisor_step: Optional[str] = None  # "elegir"


_progress: Dict[str, Progress] = {}
advisor_requests: List[dict] = []


def _p(eid: str) -> Progress:
    with _lock:
        return _progress.setdefault(eid, Progress())


def reset_all() -> None:
    with _lock:
        _progress.clear()
        advisor_requests.clear()


def today_lima() -> date:
    return datetime.now(LIMA).date()


def level_of(points: int) -> tuple:
    current = LEVELS[0]
    for lv in LEVELS:
        if points >= lv[0]:
            current = lv
    return current


def status_line(eid: str) -> str:
    p = _p(eid)
    _, name, emoji, _ = level_of(p.points)
    return f"🔥 Racha: {p.streak} día(s) · ⭐ {p.points} Qullqi puntos · Nivel {emoji} {name}"


def status_text(eid: str) -> str:
    p = _p(eid)
    lv_min, name, emoji, meaning = level_of(p.points)
    nxt = next((lv for lv in LEVELS if lv[0] > p.points), None)
    falta = (
        f"Te faltan {nxt[0] - p.points} puntos para subir a {nxt[2]} *{nxt[1]}* ({nxt[3]})."
        if nxt
        else "¡Llegaste al nivel más alto! 🎉"
    )
    return (
        f"🏅 *Tu progreso*\n{status_line(eid)}\n"
        f"Nivel {emoji} *{name}* = {meaning}.\n{falta}\n\n"
        "Cómo ganar puntos:\n"
        f"• Registrar tus movimientos del día: +{POINTS_PER_RECORD_DAY}\n"
        f"• Leer tu resumen o lección: +{POINTS_PER_LESSON}\n"
        f"• Hacer tu *CUADRE* de caja: +{POINTS_PER_CUADRE}\n\n"
        "🎁 Con tu racha participas en premios de recarga de datos (piloto)."
    )


def on_records_confirmed(eid: str) -> str:
    """Se llama cuando ella confirma movimientos. Suma puntos una vez por día y actualiza la racha."""
    p = _p(eid)
    d = today_lima()
    with _lock:
        if p.last_record_day == d:
            return status_line(eid)
        if p.last_record_day == d - timedelta(days=1):
            p.streak += 1
        else:
            p.streak = 1
        p.last_record_day = d
        p.points += POINTS_PER_RECORD_DAY
        before = level_of(p.points - POINTS_PER_RECORD_DAY)[1]
        after = level_of(p.points)
    msg = f"+{POINTS_PER_RECORD_DAY} puntos ✨  {status_line(eid)}"
    if after[1] != before:
        msg += f"\n🎉 ¡Subiste a nivel {after[2]} *{after[1]}*!"
    return msg


def on_lesson_read(eid: str) -> str:
    p = _p(eid)
    d = today_lima()
    with _lock:
        if d in p.lesson_days:
            return ""
        p.lesson_days.add(d)
        p.points += POINTS_PER_LESSON
    return f"+{POINTS_PER_LESSON} puntos por aprender 📚"


# ---------- Cuadre de caja (detecta gastos hormiga) ----------

_NUM = re.compile(r"(\d+(?:[.,]\d{1,2})?)")


def _parse_amount(text: str) -> Optional[float]:
    m = _NUM.search(text or "")
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def cuadre_active(eid: str) -> bool:
    return _p(eid).cuadre_step is not None


def start_cuadre(eid: str) -> str:
    p = _p(eid)
    with _lock:
        p.cuadre_step = "inicio"
        p.cuadre_start = 0.0
    return (
        "🧮 *Cuadre de caja* (1 minuto)\n"
        "1/2 · ¿Con cuánta plata *empezaste* hoy tu día de venta? Escribe solo el número. Ej: *50*\n"
        "(Escribe *CANCELAR* para salir)"
    )


def continue_cuadre(eid: str, text: str, movements: list) -> dict:
    """Devuelve {"reply": str, "hormiga": float|None}."""
    p = _p(eid)
    if text.strip().upper() in ("CANCELAR", "SALIR", "NO"):
        with _lock:
            p.cuadre_step = None
        return {"reply": "Listo, cancelé el cuadre. Escribe *CUADRE* cuando quieras hacerlo.", "hormiga": None}
    amount = _parse_amount(text)
    if amount is None:
        return {"reply": "Escríbeme solo el número, por ejemplo *50* 🙂", "hormiga": None}
    if p.cuadre_step == "inicio":
        with _lock:
            p.cuadre_start = amount
            p.cuadre_step = "ahora"
        return {
            "reply": "2/2 · ¿Y cuánta plata *tienes ahora* en tu monedero o caja? Solo el número.",
            "hormiga": None,
        }
    # paso "ahora": calcular
    d = today_lima()
    ventas = gastos = 0.0
    for m in movements:
        if getattr(m, "status", "") != "CONFIRMADO":
            continue
        try:
            created = datetime.fromisoformat(str(m.created_at).replace("Z", "+00:00")).astimezone(LIMA).date()
        except ValueError:
            continue
        if created != d:
            continue
        if m.movement_type == "VENTA":
            ventas += m.amount_pen
        else:
            gastos += m.amount_pen
    esperado = round(p.cuadre_start + ventas - gastos, 2)
    real = round(amount, 2)
    diff = round(esperado - real, 2)
    with _lock:
        p.cuadre_step = None
        p.points += POINTS_PER_CUADRE
    head = (
        f"🧮 *Tu cuadre de hoy*\n"
        f"Empezaste con S/ {p.cuadre_start:.2f} + ventas anotadas S/ {ventas:.2f} − gastos anotados S/ {gastos:.2f}\n"
        f"= deberías tener *S/ {esperado:.2f}*. Tienes *S/ {real:.2f}*.\n\n"
    )
    tail = f"\n\n+{POINTS_PER_CUADRE} puntos por cuadrar tu caja ⭐"
    if diff > 0.5:
        return {
            "reply": head
            + f"🐜 *S/ {diff:.2f} se fueron sin anotar*: esos son tus *gastos hormiga* (pasajes, bolsas, comida, recargas…).\n"
            "Te lo dejo como borrador. Responde *SÍ* para guardarlo o *NO* para borrarlo."
            + tail,
            "hormiga": diff,
        }
    if diff < -0.5:
        return {
            "reply": head
            + f"💡 Tienes *S/ {-diff:.2f} más* de lo anotado: quizá olvidaste anotar una venta. "
            "Escríbemela, por ejemplo: *Vendí 20 soles de papa*."
            + tail,
            "hormiga": None,
        }
    return {"reply": head + "✅ ¡Cuadra perfecto! Anotaste todo. 👏" + tail, "hormiga": None}


# ---------- Conectar con un asesor o pedir el Agente Móvil ----------

ADVISOR_RE = re.compile(
    r"(pr[eé]stamo|cr[eé]dito|asesor|agente\s*m[oó]vil|agente\s*bcp|quiero\s+un\s+agente|manuy|prestamo)",
    re.IGNORECASE,
)


def wants_advisor(text: str) -> bool:
    return bool(ADVISOR_RE.search(text or ""))


def advisor_active(eid: str) -> bool:
    return _p(eid).advisor_step is not None


def start_advisor(eid: str, first_name: str) -> str:
    p = _p(eid)
    with _lock:
        p.advisor_step = "elegir"
    return (
        f"🤝 {first_name}, te conecto con el BCP. Con tu permiso compartiré tu *resumen de cuentas* "
        "(ventas, gastos, constancia y meta). Puedes retirar tu permiso cuando quieras.\n\n"
        "Elige una opción:\n"
        "*A* · Que me llame un asesor BCP 📞\n"
        "*B* · Pedir que el *Agente Móvil BCP* visite mi comunidad 🚚\n"
        "*C* · Ahora no\n\n"
        "Ojo: la decisión de un préstamo siempre es del banco."
    )


def continue_advisor(eid: str, text: str, profile, summary: dict) -> str:
    p = _p(eid)
    choice = text.strip().upper()[:1]
    if choice not in ("A", "B", "C"):
        return "Responde *A* (asesor), *B* (Agente Móvil) o *C* (ahora no) 🙂"
    with _lock:
        p.advisor_step = None
    if choice == "C":
        return "Perfecto, no compartí nada. Cuando quieras, escribe *ASESOR*."
    ticket = "QR-" + uuid.uuid4().hex[:5].upper()
    kind = "Llamada de asesor BCP" if choice == "A" else "Visita del Agente Móvil BCP"
    advisor_requests.append(
        {
            "ticket": ticket,
            "tipo": kind,
            "entrepreneur_id": eid,
            "nombre": profile.full_name,
            "negocio": profile.business_name,
            "ciudad": profile.city,
            "fecha": datetime.now(LIMA).isoformat(timespec="minutes"),
            **summary,
        }
    )
    resumen = (
        f"• Negocio: {profile.business_name} ({profile.city})\n"
        f"• Semanas con registro: {summary.get('semanas', 0)} de 8\n"
        f"• Ventas registradas: S/ {summary.get('ventas', 0):.2f}\n"
        f"• Ganancia acumulada: S/ {summary.get('neto', 0):.2f}\n"
        f"• Racha: {_p(eid).streak} día(s)"
    )
    when = (
        "Un asesor te llamará a este número en horario de atención."
        if choice == "A"
        else "Te avisaremos el día que el Agente Móvil pase por tu comunidad. Ese día puedes sincronizar tu cuaderno y conversar con el asesor en persona."
    )
    return (
        f"✅ Solicitud *{ticket}* registrada: {kind}.\n\n"
        f"Esto es lo que verá el asesor (con tu permiso):\n{resumen}\n\n"
        f"{when}\n_(Piloto: en la demo la solicitud queda registrada en nuestro sistema.)_"
    )

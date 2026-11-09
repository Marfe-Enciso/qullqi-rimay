"""Educación financiera en lenguaje sencillo con los números de la propia emprendedora.

Reglas del producto:
- Todo cálculo es determinístico en Python (nada lo calcula la IA).
- Se enseña con sus números, sin palabras técnicas.
- Si la usuaria escribe "no entendí", se explica de otra forma, más simple.
- Nunca se promete un crédito: solo se habla de ordenar la plata y crecer.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List

from app.models import LanguageCode, MovementRecord

# Porcentaje sugerido para separar y reinvertir en el negocio; el resto puede ir a casa.
SHARE_FOR_BUSINESS = Decimal("0.60")
# Categorías de gastos pequeños que se repiten ("gastos hormiga").
ANT_EXPENSE_CATEGORIES = {"Transporte", "Empaques"}

MINI_LESSONS: List[str] = [
    "Tu ganancia no es todo lo que vendiste: es lo que te queda después de pagar la mercadería y los gastos.",
    "Separa primero la plata del negocio y después la de la casa. Así no te quedas corta para reponer.",
    "Los gastos pequeños, como pasajes o bolsas, parecen poco, pero sumados en la semana pesan.",
    "Anotar todos los días, aunque sea poquito, te ayuda a ver si tu negocio crece de verdad.",
]

QU_NOTE = "(Castellanopi willasqayki; runasimi yachachikuykuna hamuchkanraq)"


def _d(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _week_confirmed(movements: List[MovementRecord], week_number: int) -> List[MovementRecord]:
    return [m for m in movements if m.week_number == week_number and m.status == "CONFIRMADO"]


def _totals(week_moves: List[MovementRecord]) -> tuple[Decimal, Decimal, Decimal]:
    sales = sum((_d(m.amount_pen) for m in week_moves if m.movement_type == "VENTA"), Decimal("0.00"))
    expenses = sum((_d(m.amount_pen) for m in week_moves if m.movement_type == "GASTO"), Decimal("0.00"))
    ant = sum(
        (_d(m.amount_pen) for m in week_moves
         if m.movement_type == "GASTO" and m.category in ANT_EXPENSE_CATEGORIES),
        Decimal("0.00"),
    )
    return sales, expenses, ant


def build_weekly_lesson(
    movements: List[MovementRecord],
    week_number: int,
    lang: LanguageCode = "es",
) -> str:
    """Cuánto separar, cuánto llevar a casa, gastos hormiga y una mini lección."""
    sales, expenses, ant = _totals(_week_confirmed(movements, week_number))
    net = sales - expenses
    lines: List[str] = []

    if net > 0:
        for_business = (net * SHARE_FOR_BUSINESS).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for_home = net - for_business
        lines.append(
            f"💡 Te sugiero separar S/ {for_business:.2f} para tu negocio y llevar S/ {for_home:.2f} a casa."
        )
    if ant > 0:
        lines.append(f"🐜 Gastos hormiga de esta semana (pasajes, bolsas): S/ {ant:.2f}. Son pequeños, pero suman.")

    lesson = MINI_LESSONS[(week_number - 1) % len(MINI_LESSONS)]
    lines.append(f"📚 Aprende en 1 minuto: {lesson}")
    lines.append("Si algo no se entiende, escríbeme «no entendí» y te lo explico de otra forma.")

    text = "\n".join(lines)
    return f"{text}\n{QU_NOTE}" if lang == "qu" else text


def build_simple_reexplanation(
    movements: List[MovementRecord],
    week_number: int,
    lang: LanguageCode = "es",
) -> str:
    """Explica de otra forma, con un ejemplo de S/ 10, usando sus números de la semana."""
    sales, expenses, _ = _totals(_week_confirmed(movements, week_number))
    if sales <= 0:
        text = (
            "Te lo explico fácil: tu ganancia es lo que te queda en la mano después de pagar lo que compraste "
            "para vender. Cuéntame qué vendiste hoy y te muestro tu ganancia con tus propios números."
        )
    else:
        cost_part = int(((expenses / sales) * 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        cost_part = max(0, min(10, cost_part))
        yours = 10 - cost_part
        net = sales - expenses
        if net <= 0:
            text = (
                "Te lo explico de otra forma: esta semana gastaste igual o más de lo que vendiste. "
                "Es como comprar 10 frutas y vender menos de 10: todavía no te queda ganancia. "
                "Cuando vendas lo que compraste, tu ganancia va a subir."
            )
        else:
            text = (
                f"Te lo explico de otra forma: de cada S/ 10 que vendes, S/ {cost_part} se van en mercadería "
                f"y gastos, y S/ {yours} son tuyos. Esta semana eso suma S/ {net:.2f} de ganancia."
            )
    return f"{text}\n{QU_NOTE}" if lang == "qu" else text

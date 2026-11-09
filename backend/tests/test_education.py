"""Pruebas de la capa educativa: lección semanal, gastos hormiga y «no entendí»."""

from app.models import MovementRecord
from app.services.education import build_simple_reexplanation, build_weekly_lesson
from app.services.interpreter import interpret_whatsapp_message


def _mov(i: int, mtype: str, amount: float, category: str, week: int = 8) -> MovementRecord:
    return MovementRecord(
        id=f"m{i}", entrepreneur_id="e1", week_number=week, movement_type=mtype,
        amount_pen=amount, category=category, description="x", raw_message="x",
        source_channel="TEST", ai_confidence=1.0, status="CONFIRMADO",
        created_at="2026-11-08T12:00:00+00:00",
    )


MOVES = [
    _mov(1, "VENTA", 1120.0, "Ventas"),
    _mov(2, "GASTO", 748.0, "Compra de mercadería"),
    _mov(3, "GASTO", 42.0, "Transporte"),
]


def test_weekly_lesson_splits_profit_and_flags_ant_expenses():
    text = build_weekly_lesson(MOVES, week_number=8)
    assert "S/ 198.00 para tu negocio" in text  # 60 % de S/ 330
    assert "llevar S/ 132.00 a casa" in text
    assert "Gastos hormiga" in text and "S/ 42.00" in text
    assert "no entendí" in text


def test_reexplanation_uses_her_own_numbers_out_of_ten():
    text = build_simple_reexplanation(MOVES, week_number=8)
    assert "de cada S/ 10 que vendes, S/ 7" in text
    assert "S/ 3 son tuyos" in text
    assert "S/ 330.00" in text


def test_no_entendi_is_detected_before_any_other_intent():
    for phrase in ["no entendí", "No entiendo", "explícame de otra forma", "manam yachanichu"]:
        assert interpret_whatsapp_message(phrase).detected_intent == "EXPLICAR_DE_NUEVO"
    assert interpret_whatsapp_message("no").detected_intent == "DESCARTAR_PENDIENTES"

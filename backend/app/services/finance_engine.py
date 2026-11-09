"""Motor financiero determinístico en Python.

Regla de arquitectura:
Todos los cálculos de ventas, gastos, margen neto, desglose por categoría,
cumplimiento de meta de 8 semanas, constancia e integridad del Perfil Financiero
se ejecutan exclusivamente en Python (`Decimal`) sobre movimientos con estado CONFIRMADO.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Dict, List, Tuple

from app.config import settings
from app.models import (
    CategoryBreakdownItem,
    EightWeekGoalSummary,
    EntrepreneurProfileInfo,
    FinancialProfileReport,
    MovementRecord,
    WeeklySummaryItem,
)
from app.services.explainer import (
    explain_eight_week_goal_plain,
    explain_weekly_summary_plain,
)

WEEK_PERIOD_LABELS: Dict[int, str] = {
    1: "Semana 1 (14 sep – 20 sep 2026)",
    2: "Semana 2 (21 sep – 27 sep 2026)",
    3: "Semana 3 (28 sep – 04 oct 2026)",
    4: "Semana 4 (05 oct – 11 oct 2026)",
    5: "Semana 5 (12 oct – 18 oct 2026)",
    6: "Semana 6 (19 oct – 25 oct 2026)",
    7: "Semana 7 (26 oct – 01 nov 2026)",
    8: "Semana 8 (02 nov – 08 nov 2026 • En vivo)",
}


def _d(val: float | int | str | Decimal) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_category_breakdown(
    movements: List[MovementRecord],
) -> List[CategoryBreakdownItem]:
    """Calcula el desglose determinístico de ventas y gastos por categoría sobre movimientos CONFIRMADOS."""
    confirmed = [m for m in movements if m.status == "CONFIRMADO"]
    totals_by_type: Dict[str, Decimal] = {
        "VENTA": Decimal("0.00"),
        "GASTO": Decimal("0.00"),
    }
    bucket_totals: Dict[Tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    bucket_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    for m in confirmed:
        amt = _d(m.amount_pen)
        totals_by_type[m.movement_type] += amt
        key = (m.movement_type, m.category)
        bucket_totals[key] += amt
        bucket_counts[key] += 1

    items: List[CategoryBreakdownItem] = []
    for (mtype, category), total_dec in sorted(
        bucket_totals.items(),
        key=lambda kv: (0 if kv[0][0] == "GASTO" else 1, -float(kv[1]), kv[0][1]),
    ):
        type_total = totals_by_type.get(mtype, Decimal("0.00"))
        pct = (
            float(
                ((total_dec / type_total) * Decimal("100.0")).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
            if type_total > Decimal("0.00")
            else 0.0
        )
        items.append(
            CategoryBreakdownItem(
                category=category,
                movement_type=mtype,  # type: ignore[arg-type]
                total_amount_pen=float(total_dec),
                movements_count=bucket_counts[(mtype, category)],
                percentage_of_type=pct,
            )
        )
    return items


def compute_weekly_summaries(
    movements: List[MovementRecord],
    entrepreneur: EntrepreneurProfileInfo,
) -> List[WeeklySummaryItem]:
    summaries: List[WeeklySummaryItem] = []
    weekly_target = round(float(entrepreneur.goal_weekly_target_pen), 2)

    for wk in range(1, entrepreneur.goal_weeks + 1):
        wk_movs = [m for m in movements if m.week_number == wk]
        confirmed = [m for m in wk_movs if m.status == "CONFIRMADO"]
        pending = [m for m in wk_movs if m.status == "PENDIENTE"]

        sales_dec = sum(
            (_d(m.amount_pen) for m in confirmed if m.movement_type == "VENTA"),
            Decimal("0.00"),
        )
        expenses_dec = sum(
            (_d(m.amount_pen) for m in confirmed if m.movement_type == "GASTO"),
            Decimal("0.00"),
        )
        net_dec = (sales_dec - expenses_dec).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        sales = float(sales_dec)
        expenses = float(expenses_dec)
        net = float(net_dec)
        margin_pct = (
            float(
                ((net_dec / sales_dec) * Decimal("100.0")).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            )
            if sales_dec > Decimal("0.00")
            else 0.0
        )
        target_achieved = net_dec >= _d(weekly_target) and len(confirmed) > 0

        if wk < entrepreneur.active_week and len(confirmed) > 0:
            status_badge = "COMPLETADA"
        elif wk == entrepreneur.active_week:
            status_badge = "COMPLETADA" if target_achieved else "EN_CURSO"
        else:
            status_badge = "PENDIENTE"

        explanation = explain_weekly_summary_plain(
            week_number=wk,
            sales=sales,
            expenses=expenses,
            net=net,
            weekly_target=weekly_target,
            confirmed_count=len(confirmed),
            pending_count=len(pending),
            first_name=(entrepreneur.full_name.split()[0] if entrepreneur.full_name else "casera"),
        )

        summaries.append(
            WeeklySummaryItem(
                week_number=wk,
                week_label=WEEK_PERIOD_LABELS.get(wk, f"Semana {wk}"),
                total_sales_pen=sales,
                total_expenses_pen=expenses,
                net_margin_pen=net,
                profit_margin_pct=margin_pct,
                confirmed_movements_count=len(confirmed),
                pending_movements_count=len(pending),
                weekly_target_pen=weekly_target,
                target_achieved=target_achieved,
                status_badge=status_badge,  # type: ignore[arg-type]
                plain_spanish_explanation=explanation,
            )
        )

    return summaries


def compute_eight_week_goal(
    movements: List[MovementRecord],
    entrepreneur: EntrepreneurProfileInfo,
) -> EightWeekGoalSummary:
    weekly_items = compute_weekly_summaries(movements, entrepreneur)
    accumulated_net_dec = sum(
        (_d(w.net_margin_pen) for w in weekly_items), Decimal("0.00")
    )
    accumulated_net = float(accumulated_net_dec)
    goal_target = round(float(entrepreneur.goal_target_pen), 2)
    remaining = max(0.0, round(goal_target - accumulated_net, 2))
    progress_pct = round(
        min(100.0, max(0.0, (accumulated_net / goal_target) * 100.0)), 2
    )

    active_weeks_with_records = sum(
        1 for w in weekly_items if w.confirmed_movements_count > 0
    )
    consistency_score_pct = round(
        (active_weeks_with_records / entrepreneur.goal_weeks) * 100.0, 1
    )

    coaching = explain_eight_week_goal_plain(
        accumulated_net=accumulated_net,
        goal_target=goal_target,
        completed_weeks=active_weeks_with_records,
        total_weeks=entrepreneur.goal_weeks,
        first_name=(entrepreneur.full_name.split()[0] if entrepreneur.full_name else "casera"),
        goal_title=entrepreneur.goal_title,
    )

    return EightWeekGoalSummary(
        goal_title=entrepreneur.goal_title,
        goal_target_pen=goal_target,
        weekly_target_pen=entrepreneur.goal_weekly_target_pen,
        total_weeks=entrepreneur.goal_weeks,
        completed_weeks_count=active_weeks_with_records,
        active_week_number=entrepreneur.active_week,
        accumulated_net_pen=accumulated_net,
        remaining_pen=remaining,
        progress_pct=progress_pct,
        goal_achieved=accumulated_net >= goal_target and active_weeks_with_records >= 8,
        consistency_score_pct=consistency_score_pct,
        plain_spanish_coaching=coaching,
        weeks=weekly_items,
        category_breakdown=compute_category_breakdown(movements),
    )


def compute_evidence_hash(
    entrepreneur_id: str,
    confirmed_movements: List[MovementRecord],
) -> str:
    canonical_payload = [
        {
            "id": m.id,
            "wk": m.week_number,
            "type": m.movement_type,
            "amt": f"{m.amount_pen:.2f}",
            "status": m.status,
        }
        for m in sorted(confirmed_movements, key=lambda x: x.id)
    ]
    serialized = json.dumps(
        {
            "entrepreneur_id": entrepreneur_id,
            "records": canonical_payload,
            "salt": (settings.consent_signing_secret or "qullqi-evidence")[:12],
        },
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def generate_financial_profile(
    movements: List[MovementRecord],
    entrepreneur: EntrepreneurProfileInfo,
) -> FinancialProfileReport:
    goal_summary = compute_eight_week_goal(movements, entrepreneur)
    confirmed = [m for m in movements if m.status == "CONFIRMADO"]

    total_sales_dec = sum(
        (_d(w.total_sales_pen) for w in goal_summary.weeks), Decimal("0.00")
    )
    total_expenses_dec = sum(
        (_d(w.total_expenses_pen) for w in goal_summary.weeks), Decimal("0.00")
    )
    total_net_dec = total_sales_dec - total_expenses_dec

    total_sales = float(total_sales_dec)
    total_expenses = float(total_expenses_dec)
    total_net = float(total_net_dec)

    verified_weeks = goal_summary.completed_weeks_count
    avg_weekly_net = (
        round(total_net / verified_weeks, 2) if verified_weeks > 0 else 0.0
    )
    savings_capacity = round(max(0.0, avg_weekly_net * 0.30), 2)
    expense_ratio = (
        round((total_expenses / total_sales) * 100.0, 1) if total_sales > 0 else 0.0
    )

    if verified_weeks >= 8 and goal_summary.goal_achieved:
        tier = "NIVEL A - Constancia Completa (8/8 semanas verificadas)"
    elif verified_weeks >= 7:
        tier = "NIVEL B+ - Alta Constancia Operativa (7/8 semanas verificadas)"
    elif verified_weeks >= 1:
        tier = f"NIVEL EN CONSTRUCCIÓN - {verified_weeks}/8 semanas activas"
    else:
        tier = "NIVEL INICIAL - Cuenta recién creada (0/8 semanas)"

    plain_summary = (
        f"{entrepreneur.full_name} ({entrepreneur.business_name}, {entrepreneur.city}) "
        f"registra {verified_weeks} de {entrepreneur.goal_weeks} semanas con movimientos confirmados "
        f"({len(confirmed)} operaciones en total). Sus ventas acumuladas suman S/ {total_sales:.2f} "
        f"y sus gastos comerciales S/ {total_expenses:.2f}, dejando un excedente neto total de "
        f"S/ {total_net:.2f} (promedio de S/ {avg_weekly_net:.2f} libres por semana activa). "
        f"Su capacidad estimada de ahorro/cuota semanal prudente (30% del excedente, para no ahogar el negocio) es de S/ {savings_capacity:.2f}."
    )

    disclaimer = (
        "AVISO DE TRANSPARENCIA Y CUMPLIMIENTO: Este Perfil Financiero Operativo resume "
        "registros autodeclarados y confirmados por la emprendedora en Qullqi Rimay. "
        "NO constituye una aprobación crediticia, evaluación, verificación ni oferta vinculante "
        "por parte del Banco de Crédito del Perú (BCP) ni de terceros."
    )

    evidence_hash = compute_evidence_hash(entrepreneur.id, confirmed)

    return FinancialProfileReport(
        profile_id=f"prof-{entrepreneur.id}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        entrepreneur=entrepreneur,
        verified_weeks_count=verified_weeks,
        total_confirmed_movements=len(confirmed),
        total_sales_8w_pen=total_sales,
        total_expenses_8w_pen=total_expenses,
        total_net_8w_pen=total_net,
        average_weekly_net_pen=avg_weekly_net,
        savings_capacity_weekly_pen=savings_capacity,
        expense_to_Revenue_ratio_pct=expense_ratio,
        consistency_index_pct=goal_summary.consistency_score_pct,
        goal_progress_pct=goal_summary.progress_pct,
        operational_tier=tier,
        plain_spanish_summary=plain_summary,
        evidence_integrity_hash=evidence_hash,
        regulatory_disclaimer=disclaimer,
        bcp_approval_claim=False,
        category_breakdown=goal_summary.category_breakdown,
    )

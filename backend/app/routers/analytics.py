"""Endpoints de resúmenes semanales calculados en Python, explicaciones sencillas y meta de 8 semanas."""

from typing import List
from fastapi import APIRouter, Depends
from app.models import EightWeekGoalSummary, WeeklySummaryItem
from app.security import AuthenticatedPrincipal, require_authenticated_entrepreneur
from app.services.finance_engine import compute_eight_week_goal, compute_weekly_summaries
from app.services.store import store

router = APIRouter(
    prefix="/api/analytics",
    tags=["4, 5 & 6. Cálculos Python, Explicación Sencilla y Meta 8 Semanas"],
)


@router.get("/weekly", response_model=List[WeeklySummaryItem])
def get_weekly_summaries(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> List[WeeklySummaryItem]:
    return compute_weekly_summaries(
        movements=store.list_movements(entrepreneur_id=principal.entrepreneur_id),
        entrepreneur=store.get_entrepreneur(principal.entrepreneur_id),
    )


@router.get("/goal", response_model=EightWeekGoalSummary)
def get_eight_week_goal(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> EightWeekGoalSummary:
    return compute_eight_week_goal(
        movements=store.list_movements(entrepreneur_id=principal.entrepreneur_id),
        entrepreneur=store.get_entrepreneur(principal.entrepreneur_id),
    )

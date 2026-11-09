"""Endpoints para registrar, listar, confirmar y descartar movimientos financieros."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models import MovementCreateRequest, MovementRecord
from app.security import AuthenticatedPrincipal, require_authenticated_entrepreneur
from app.services.store import store

router = APIRouter(prefix="/api/movements", tags=["1 & 3. Movimientos y Confirmación"])


@router.get("", response_model=List[MovementRecord])
def list_movements(
    week_number: Optional[int] = Query(default=None, ge=1, le=8),
    status: Optional[str] = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> List[MovementRecord]:
    return store.list_movements(
        week_number=week_number,
        status=status,
        entrepreneur_id=principal.entrepreneur_id,
    )


@router.post("", response_model=MovementRecord, status_code=201)
def create_movement(
    payload: MovementCreateRequest,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> MovementRecord:
    raw_msg = payload.raw_message or (
        f"Registro manual: {payload.movement_type} S/ {payload.amount_pen:.2f} - {payload.description}"
    )
    return store.add_movement(
        week_number=payload.week_number,
        movement_type=payload.movement_type,
        amount_pen=payload.amount_pen,
        category=payload.category,
        description=payload.description,
        raw_message=raw_msg,
        source_channel="REGISTRO_DIRECTO",
        ai_confidence=1.0,
        auto_confirm=payload.auto_confirm,
        entrepreneur_id=principal.entrepreneur_id,
    )


@router.post("/{movement_id}/confirm", response_model=MovementRecord)
def confirm_movement(
    movement_id: str,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> MovementRecord:
    updated = store.update_movement_status(
        movement_id, "CONFIRMADO", entrepreneur_id=principal.entrepreneur_id
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return updated


@router.post("/{movement_id}/discard", response_model=MovementRecord)
def discard_movement(
    movement_id: str,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> MovementRecord:
    updated = store.update_movement_status(
        movement_id, "DESCARTADO", entrepreneur_id=principal.entrepreneur_id
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return updated

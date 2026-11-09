"""Rutas del Modo Demo Aislado (`/api/demo-sandbox/*`) exclusivamente con datos ficticios de Rosa (133 movimientos).

- Permite al jurado y visitantes explorar las 8 semanas ficticias de Rosa Quispe (Huamanga)
  sin requerir claves en el frontend (`VITE_*`) y sin poder alterar la base de datos compartida
  en Supabase ni ejecutar operaciones administrativas.
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import APIRouter, Header, HTTPException, Query
from app.models import (
    ChatMessageBubble,
    ConsentGrantRequest,
    ConsentRecord,
    ConsentRevokeRequest,
    EightWeekGoalSummary,
    EntrepreneurProfileInfo,
    FinancialProfileReport,
    LanguagePreferenceUpdateRequest,
    MovementCreateRequest,
    MovementRecord,
    SharedConsentPublicView,
    SimulatorMessageRequest,
    SimulatorMessageResponse,
    WeeklySummaryItem,
)
from app.services.demo_sandbox import demo_sandbox_manager
from app.services.finance_engine import (
    compute_eight_week_goal,
    compute_weekly_summaries,
    generate_financial_profile,
)
from app.services.i18n_quechua import (
    format_confirmed_reply,
    format_discarded_reply,
    format_language_switched,
    format_no_pending_to_confirm,
    format_summary_reply,
)
from app.services.education import build_simple_reexplanation, build_weekly_lesson
from app.services.interpreter import interpret_whatsapp_message

router = APIRouter(
    prefix="/api/demo-sandbox",
    tags=["Modo Demo Aislado (Datos Ficticios Rosa — Sin Acceso a Base Compartida)"],
)


def _get_visitor_store(x_demo_visitor_id: Optional[str]):
    return demo_sandbox_manager.get_sandbox(x_demo_visitor_id or "default-public-demo-sandbox")


@router.get("/entrepreneur", response_model=EntrepreneurProfileInfo)
def sandbox_get_entrepreneur(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> EntrepreneurProfileInfo:
    sb = _get_visitor_store(x_demo_visitor_id)
    return sb.get_entrepreneur()


@router.patch("/preferences", response_model=EntrepreneurProfileInfo)
def sandbox_update_preferences(
    payload: LanguagePreferenceUpdateRequest,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> EntrepreneurProfileInfo:
    sb = _get_visitor_store(x_demo_visitor_id)
    return sb.update_entrepreneur_language(
        entrepreneur_id=sb.get_entrepreneur().id,
        preferred_language=payload.preferred_language,
    )


@router.get("/analytics/weekly", response_model=List[WeeklySummaryItem])
def sandbox_weekly_summaries(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> List[WeeklySummaryItem]:
    sb = _get_visitor_store(x_demo_visitor_id)
    return compute_weekly_summaries(sb.list_movements(), sb.get_entrepreneur())


@router.get("/analytics/goal", response_model=EightWeekGoalSummary)
def sandbox_goal_summary(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> EightWeekGoalSummary:
    sb = _get_visitor_store(x_demo_visitor_id)
    return compute_eight_week_goal(sb.list_movements(), sb.get_entrepreneur())


@router.get("/movements", response_model=List[MovementRecord])
def sandbox_list_movements(
    week_number: Optional[int] = Query(default=None, ge=1, le=8),
    status: Optional[str] = Query(default=None),
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> List[MovementRecord]:
    sb = _get_visitor_store(x_demo_visitor_id)
    return sb.list_movements(week_number=week_number, status=status)


@router.post("/movements", response_model=MovementRecord, status_code=201)
def sandbox_create_movement(
    payload: MovementCreateRequest,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> MovementRecord:
    sb = _get_visitor_store(x_demo_visitor_id)
    raw_msg = payload.raw_message or (
        f"Registro manual demo: {payload.movement_type} S/ {payload.amount_pen:.2f} - {payload.description}"
    )
    return sb.add_movement(
        week_number=payload.week_number,
        movement_type=payload.movement_type,
        amount_pen=payload.amount_pen,
        category=payload.category,
        description=payload.description,
        raw_message=raw_msg,
        source_channel="DEMO_SANDBOX_AISLADO",
        ai_confidence=1.0,
        auto_confirm=payload.auto_confirm,
    )


@router.post("/movements/{movement_id}/confirm", response_model=MovementRecord)
def sandbox_confirm_movement(
    movement_id: str,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> MovementRecord:
    sb = _get_visitor_store(x_demo_visitor_id)
    updated = sb.update_movement_status(movement_id, "CONFIRMADO")
    if not updated:
        raise HTTPException(status_code=404, detail="Movimiento ficticio no encontrado en este sandbox")
    return updated


@router.post("/movements/{movement_id}/discard", response_model=MovementRecord)
def sandbox_discard_movement(
    movement_id: str,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> MovementRecord:
    sb = _get_visitor_store(x_demo_visitor_id)
    updated = sb.update_movement_status(movement_id, "DESCARTADO")
    if not updated:
        raise HTTPException(status_code=404, detail="Movimiento ficticio no encontrado en este sandbox")
    return updated


@router.get("/simulator/history", response_model=List[ChatMessageBubble])
def sandbox_chat_history(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> List[ChatMessageBubble]:
    sb = _get_visitor_store(x_demo_visitor_id)
    return sb.list_chat_history()


@router.post("/simulator/message", response_model=SimulatorMessageResponse)
def sandbox_send_message(
    payload: SimulatorMessageRequest,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> SimulatorMessageResponse:
    sb = _get_visitor_store(x_demo_visitor_id)
    entrepreneur = sb.get_entrepreneur()
    lang = entrepreneur.preferred_language

    now_iso = datetime.now(timezone.utc).isoformat()
    user_bubble = ChatMessageBubble(
        id=f"chat-u-{uuid.uuid4().hex[:8]}",
        sender="ROSA",
        text=payload.message.strip(),
        timestamp=now_iso,
        week_number=payload.week_number,
    )
    sb.add_chat_bubble(user_bubble)

    extraction = interpret_whatsapp_message(
        message=payload.message,
        week_number=payload.week_number,
        preferred_language=lang,
    )

    created_pending: List[MovementRecord] = []
    updated_movements: List[MovementRecord] = []
    reply_text = extraction.reply_preview_es

    if extraction.detected_intent == "CAMBIAR_IDIOMA":
        target_lang = extraction.detected_language
        updated_prof = sb.update_entrepreneur_language(entrepreneur.id, target_lang)
        reply_text = format_language_switched(updated_prof.preferred_language)
    elif extraction.detected_intent == "REGISTRAR_MOVIMIENTO":
        for item in extraction.items:
            mov = sb.add_movement(
                week_number=payload.week_number,
                movement_type=item.movement_type,
                amount_pen=item.amount_pen,
                category=item.category,
                description=item.description,
                raw_message=payload.message.strip(),
                source_channel="DEMO_SANDBOX_AISLADO",
                ai_confidence=extraction.confidence,
                auto_confirm=False,
            )
            created_pending.append(mov)
    elif extraction.detected_intent == "CONFIRMAR_PENDIENTES":
        updated_movements = sb.confirm_all_pending(week_number=payload.week_number)
        if updated_movements:
            goal_state = compute_eight_week_goal(sb.list_movements(), sb.get_entrepreneur())
            total_confirmed_pen = sum(m.amount_pen for m in updated_movements)
            reply_text = format_confirmed_reply(
                count=len(updated_movements),
                total_pen=total_confirmed_pen,
                week_number=payload.week_number,
                coaching_es=goal_state.plain_spanish_coaching,
                lang=lang,
            )
        else:
            reply_text = format_no_pending_to_confirm(lang=lang)
    elif extraction.detected_intent == "DESCARTAR_PENDIENTES":
        updated_movements = sb.discard_all_pending(week_number=payload.week_number)
        if updated_movements:
            reply_text = format_discarded_reply(count=len(updated_movements), lang=lang)
        else:
            reply_text = "No había borradores pendientes por descartar, casera."
    elif extraction.detected_intent == "CONSULTAR_RESUMEN":
        goal_state = compute_eight_week_goal(sb.list_movements(), sb.get_entrepreneur())
        wk_index = max(0, min(len(goal_state.weeks) - 1, payload.week_number - 1))
        wk_item = goal_state.weeks[wk_index]
        reply_text = format_summary_reply(
            week_explanation_es=wk_item.plain_spanish_explanation,
            accumulated_net_pen=goal_state.accumulated_net_pen,
            goal_target_pen=goal_state.goal_target_pen,
            progress_pct=goal_state.progress_pct,
            lang=lang,
        )
        reply_text += "\n\n" + build_weekly_lesson(
            sb.list_movements(), week_number=payload.week_number, lang=lang
        )
    elif extraction.detected_intent == "EXPLICAR_DE_NUEVO":
        reply_text = build_simple_reexplanation(
            sb.list_movements(), week_number=payload.week_number, lang=lang
        )

    bot_bubble = ChatMessageBubble(
        id=f"chat-b-{uuid.uuid4().hex[:8]}",
        sender="QULLQI_BOT",
        text=reply_text,
        timestamp=datetime.now(timezone.utc).isoformat(),
        week_number=payload.week_number,
        structured_json=extraction,
        pending_movement_ids=[m.id for m in created_pending],
    )
    sb.add_chat_bubble(bot_bubble)

    return SimulatorMessageResponse(
        user_bubble=user_bubble,
        bot_bubble=bot_bubble,
        created_pending_movements=created_pending,
        updated_movements=updated_movements,
    )


@router.get("/profile", response_model=FinancialProfileReport)
def sandbox_get_profile(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> FinancialProfileReport:
    sb = _get_visitor_store(x_demo_visitor_id)
    return generate_financial_profile(sb.list_movements(), sb.get_entrepreneur())


@router.get("/consents", response_model=List[ConsentRecord])
def sandbox_list_consents(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> List[ConsentRecord]:
    sb = _get_visitor_store(x_demo_visitor_id)
    return sb.list_consents()


@router.post("/consents/grant", response_model=ConsentRecord, status_code=201)
def sandbox_grant_consent(
    payload: ConsentGrantRequest,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> ConsentRecord:
    if not payload.accepted_terms:
        raise HTTPException(
            status_code=400,
            detail="Se requiere aceptación explícita del consentimiento informado.",
        )
    sb = _get_visitor_store(x_demo_visitor_id)
    profile = generate_financial_profile(sb.list_movements(), sb.get_entrepreneur())
    return sb.create_consent(
        recipient_entity=payload.recipient_entity.strip(),
        purpose=payload.purpose.strip(),
        evidence_hash=profile.evidence_integrity_hash,
    )


@router.post("/consents/{consent_id}/revoke", response_model=ConsentRecord)
def sandbox_revoke_consent(
    consent_id: str,
    payload: ConsentRevokeRequest,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> ConsentRecord:
    sb = _get_visitor_store(x_demo_visitor_id)
    updated = sb.revoke_consent(consent_id=consent_id, reason=payload.reason.strip())
    if not updated:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado en este sandbox")
    return updated


@router.get("/consents/shared/{share_token}")
def sandbox_view_shared_token(
    share_token: str,
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> dict:
    sb = _get_visitor_store(x_demo_visitor_id)
    consent = sb.get_consent_by_token(share_token)
    if not consent:
        raise HTTPException(status_code=404, detail="Enlace de consentimiento inválido o inexistente.")
    if consent.status == "REVOCADO":
        raise HTTPException(
            status_code=403,
            detail=f"ACCESO REVOCADO: La titular revocó este permiso el {consent.revoked_at}. Motivo: {consent.revocation_reason}",
        )
    consent = sb.mark_consent_expired_if_needed(consent)
    if consent.status == "EXPIRADO":
        raise HTTPException(
            status_code=403,
            detail=f"ACCESO EXPIRADO: El enlace de consentimiento venció el {consent.expires_at}.",
        )
    profile = generate_financial_profile(sb.list_movements(), sb.get_entrepreneur())
    redacted_entrepreneur = profile.entrepreneur.model_copy(update={"id": "TITULAR-VERIFICADA"})
    sanitized_profile = profile.model_copy(update={"entrepreneur": redacted_entrepreneur})
    public_consent = SharedConsentPublicView(
        id=consent.id,
        recipient_entity=consent.recipient_entity,
        purpose=consent.purpose,
        consent_statement=consent.consent_statement,
        evidence_hash=consent.evidence_hash,
        status=consent.status,
        granted_at=consent.granted_at,
        expires_at=consent.expires_at,
    )
    return {"consent": public_consent, "shared_profile": sanitized_profile}


@router.post("/reset")
def sandbox_reset_visitor_state(
    x_demo_visitor_id: Optional[str] = Header(default=None, alias="X-Demo-Visitor-Id"),
) -> dict:
    """Restaura únicamente el sandbox efímero del visitante actual (sin tocar la base de datos Supabase)."""
    demo_sandbox_manager.reset_sandbox(x_demo_visitor_id or "default-public-demo-sandbox")
    return {
        "status": "sandbox_reset_ok",
        "mode": "ISOLATED_FICTIONAL_DEMO_SANDBOX",
        "message": "Tu simulación ficticia de Rosa (133 movimientos • 8 semanas) fue reiniciada en memoria aislada sin alterar la base de datos compartida.",
    }

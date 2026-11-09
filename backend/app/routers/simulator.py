"""Simulador Web de WhatsApp + Intérprete Bilingüe (Español / Quechua Ayacuchano) + Flujo de Confirmación."""

from datetime import datetime, timezone
from typing import List
import uuid

from fastapi import APIRouter, Depends
from app.models import (
    ChatMessageBubble,
    MovementRecord,
    SimulatorMessageRequest,
    SimulatorMessageResponse,
)
from app.security import AuthenticatedPrincipal, require_authenticated_entrepreneur
from app.services.finance_engine import compute_eight_week_goal
from app.services.i18n_quechua import (
    format_confirmed_reply,
    format_discarded_reply,
    format_language_switched,
    format_no_pending_to_confirm,
    format_summary_reply,
)
from app.services import engagement
from app.services.education import build_simple_reexplanation, build_weekly_lesson
from app.services.interpreter import interpret_whatsapp_message
from app.services.store import store

router = APIRouter(prefix="/api/simulator", tags=["2, 3 & 10. Simulador WhatsApp e IA"])


@router.get("/history", response_model=List[ChatMessageBubble])
def get_chat_history(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> List[ChatMessageBubble]:
    return store.list_chat_history(entrepreneur_id=principal.entrepreneur_id)


def process_whatsapp_message_for_entrepreneur(
    payload: SimulatorMessageRequest,
    entrepreneur_id: str,
    source_channel: str = "WHATSAPP_SIMULATOR",
) -> SimulatorMessageResponse:
    entrepreneur = store.get_entrepreneur(entrepreneur_id)
    lang = entrepreneur.preferred_language

    now_iso = datetime.now(timezone.utc).isoformat()
    user_bubble = ChatMessageBubble(
        id=f"chat-u-{uuid.uuid4().hex[:8]}",
        sender="ROSA",
        text=payload.message.strip(),
        timestamp=now_iso,
        week_number=payload.week_number,
    )
    store.add_chat_bubble(user_bubble, entrepreneur_id=entrepreneur_id)

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
        updated_prof = store.update_entrepreneur_language(entrepreneur_id, target_lang)
        reply_text = format_language_switched(updated_prof.preferred_language)

    elif extraction.detected_intent == "REGISTRAR_MOVIMIENTO":
        for item in extraction.items:
            mov = store.add_movement(
                week_number=payload.week_number,
                movement_type=item.movement_type,
                amount_pen=item.amount_pen,
                category=item.category,
                description=item.description,
                raw_message=payload.message.strip(),
                source_channel=source_channel,
                ai_confidence=extraction.confidence,
                auto_confirm=False,
                entrepreneur_id=entrepreneur_id,
            )
            created_pending.append(mov)

    elif extraction.detected_intent == "CONFIRMAR_PENDIENTES":
        updated_movements = store.confirm_all_pending(
            week_number=payload.week_number,
            entrepreneur_id=entrepreneur_id,
        )
        if updated_movements:
            goal_state = compute_eight_week_goal(
                store.list_movements(entrepreneur_id=entrepreneur_id),
                store.get_entrepreneur(entrepreneur_id),
            )
            total_confirmed_pen = sum(m.amount_pen for m in updated_movements)
            reply_text = format_confirmed_reply(
                count=len(updated_movements),
                total_pen=total_confirmed_pen,
                week_number=payload.week_number,
                coaching_es=goal_state.plain_spanish_coaching,
                lang=lang,
            )
            reply_text += "\n\n" + engagement.on_records_confirmed(entrepreneur_id)
        else:
            reply_text = format_no_pending_to_confirm(lang=lang)

    elif extraction.detected_intent == "DESCARTAR_PENDIENTES":
        updated_movements = store.discard_all_pending(
            week_number=payload.week_number,
            entrepreneur_id=entrepreneur_id,
        )
        if updated_movements:
            reply_text = format_discarded_reply(count=len(updated_movements), lang=lang)
        else:
            reply_text = "No había borradores pendientes por descartar, casera."

    elif extraction.detected_intent == "CONSULTAR_RESUMEN":
        goal_state = compute_eight_week_goal(
            store.list_movements(entrepreneur_id=entrepreneur_id),
            store.get_entrepreneur(entrepreneur_id),
        )
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
            store.list_movements(entrepreneur_id=entrepreneur_id),
            week_number=payload.week_number,
            lang=lang,
        )
        bonus = engagement.on_lesson_read(entrepreneur_id)
        reply_text += ("\n\n" + bonus) if bonus else ""

    elif extraction.detected_intent == "EXPLICAR_DE_NUEVO":
        reply_text = build_simple_reexplanation(
            store.list_movements(entrepreneur_id=entrepreneur_id),
            week_number=payload.week_number,
            lang=lang,
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
    store.add_chat_bubble(bot_bubble, entrepreneur_id=entrepreneur_id)

    return SimulatorMessageResponse(
        user_bubble=user_bubble,
        bot_bubble=bot_bubble,
        created_pending_movements=created_pending,
        updated_movements=updated_movements,
    )


@router.post("/message", response_model=SimulatorMessageResponse)
def send_whatsapp_message(
    payload: SimulatorMessageRequest,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> SimulatorMessageResponse:
    return process_whatsapp_message_for_entrepreneur(
        payload=payload,
        entrepreneur_id=principal.entrepreneur_id,
        source_channel="WHATSAPP_SIMULATOR",
    )

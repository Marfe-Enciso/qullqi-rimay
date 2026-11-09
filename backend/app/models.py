"""Esquemas Pydantic de dominio para Qullqi Rimay (Multiusuario, Bilingüe ES/QU y Demo Enriquecida)."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

MovementType = Literal["VENTA", "GASTO"]
MovementStatus = Literal["PENDIENTE", "CONFIRMADO", "DESCARTADO"]
ConsentStatus = Literal["ACTIVO", "REVOCADO", "EXPIRADO"]
LanguageCode = Literal["es", "qu"]


class EntrepreneurProfileInfo(BaseModel):
    id: str
    full_name: str
    business_name: str
    trade_sector: str
    market_location: str
    city: str
    region: str
    phone_masked: str
    goal_title: str
    goal_target_pen: float
    goal_weekly_target_pen: float
    goal_weeks: int = 8
    active_week: int = 8
    preferred_language: LanguageCode = "es"
    owner_user_id: Optional[str] = None
    data_consent_accepted: bool = False
    data_consent_accepted_at: Optional[str] = None
    data_consent_version: Optional[str] = None
    whatsapp_linked: bool = False
    is_fictional_demo: bool = False


class CategoryBreakdownItem(BaseModel):
    category: str
    movement_type: MovementType
    total_amount_pen: float
    movements_count: int
    percentage_of_type: float


class MovementCreateRequest(BaseModel):
    week_number: int = Field(default=8, ge=1, le=8)
    movement_type: MovementType
    amount_pen: float = Field(..., gt=0, description="Monto en soles peruanos (PEN)")
    category: str = Field(..., min_length=2, max_length=80)
    description: str = Field(..., min_length=2, max_length=240)
    raw_message: Optional[str] = None
    auto_confirm: bool = Field(
        default=False,
        description="Por seguridad del flujo, los movimientos nacen PENDIENTE salvo confirmación explícita.",
    )


class MovementRecord(BaseModel):
    id: str
    entrepreneur_id: str
    week_number: int
    movement_type: MovementType
    amount_pen: float
    category: str
    description: str
    raw_message: str
    source_channel: str
    ai_confidence: float
    status: MovementStatus
    created_at: str
    confirmed_at: Optional[str] = None


class StructuredExtractedItem(BaseModel):
    movement_type: MovementType
    amount_pen: float
    category: str
    description: str
    detected_terms: List[str] = Field(default_factory=list)


class StructuredMovementExtraction(BaseModel):
    detected_intent: Literal[
        "REGISTRAR_MOVIMIENTO",
        "CONFIRMAR_PENDIENTES",
        "DESCARTAR_PENDIENTES",
        "CONSULTAR_RESUMEN",
        "EXPLICAR_DE_NUEVO",
        "CAMBIAR_IDIOMA",
        "REQUIERE_ACLARACION",
        "SALUDO_O_AYUDA",
    ]
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_confirmation: bool
    items: List[StructuredExtractedItem] = Field(default_factory=list)
    reply_preview_es: str
    engine_mode: str = "STRUCTURED_JSON_LOCAL_DETERMINISTIC"
    detected_language: Optional[LanguageCode] = None


class SimulatorMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=600)
    week_number: int = Field(default=8, ge=1, le=8)


class ChatMessageBubble(BaseModel):
    id: str
    sender: Literal["ROSA", "QULLQI_BOT"]
    text: str
    timestamp: str
    week_number: int
    structured_json: Optional[StructuredMovementExtraction] = None
    pending_movement_ids: List[str] = Field(default_factory=list)


class SimulatorMessageResponse(BaseModel):
    user_bubble: ChatMessageBubble
    bot_bubble: ChatMessageBubble
    created_pending_movements: List[MovementRecord] = Field(default_factory=list)
    updated_movements: List[MovementRecord] = Field(default_factory=list)


class WeeklySummaryItem(BaseModel):
    week_number: int
    week_label: str
    total_sales_pen: float
    total_expenses_pen: float
    net_margin_pen: float
    profit_margin_pct: float
    confirmed_movements_count: int
    pending_movements_count: int
    weekly_target_pen: float
    target_achieved: bool
    status_badge: Literal["COMPLETADA", "EN_CURSO", "PENDIENTE"]
    plain_spanish_explanation: str


class EightWeekGoalSummary(BaseModel):
    goal_title: str
    goal_target_pen: float
    weekly_target_pen: float
    total_weeks: int
    completed_weeks_count: int
    active_week_number: int
    accumulated_net_pen: float
    remaining_pen: float
    progress_pct: float
    goal_achieved: bool
    consistency_score_pct: float
    plain_spanish_coaching: str
    weeks: List[WeeklySummaryItem]
    category_breakdown: List[CategoryBreakdownItem] = Field(default_factory=list)


class FinancialProfileReport(BaseModel):
    profile_id: str
    generated_at: str
    entrepreneur: EntrepreneurProfileInfo
    verified_weeks_count: int
    total_confirmed_movements: int
    total_sales_8w_pen: float
    total_expenses_8w_pen: float
    total_net_8w_pen: float
    average_weekly_net_pen: float
    savings_capacity_weekly_pen: float
    expense_to_Revenue_ratio_pct: float
    consistency_index_pct: float
    goal_progress_pct: float
    operational_tier: str
    plain_spanish_summary: str
    evidence_integrity_hash: str
    regulatory_disclaimer: str
    bcp_approval_claim: bool = False
    category_breakdown: List[CategoryBreakdownItem] = Field(default_factory=list)


class ConsentGrantRequest(BaseModel):
    recipient_entity: str = Field(
        default="Asesor de Inclusión Financiera BCP (Evaluación Informativa)",
        min_length=3,
        max_length=150,
    )
    purpose: str = Field(
        default="Compartir historial operativo de 8 semanas para orientación financiera",
        min_length=5,
        max_length=240,
    )
    accepted_terms: bool = Field(
        ...,
        description="Debe ser True para evidenciar el consentimiento informado de la titular.",
    )


class ConsentRevokeRequest(BaseModel):
    reason: str = Field(
        default="Revocado por decisión de la titular",
        min_length=3,
        max_length=200,
    )


class ConsentRecord(BaseModel):
    id: str
    entrepreneur_id: str
    recipient_entity: str
    purpose: str
    consent_statement: str
    share_token: str
    token_sha256: str = ""
    evidence_hash: str
    status: ConsentStatus
    granted_at: str
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    revocation_reason: Optional[str] = None


class SharedConsentPublicView(BaseModel):
    """Vista pública minimizada para enlaces compartidos (sin share_token, token_sha256 ni entrepreneur_id)."""

    id: str
    recipient_entity: str
    purpose: str
    consent_statement: str
    evidence_hash: str
    status: ConsentStatus
    granted_at: str
    expires_at: Optional[str] = None


# --- Modelos de Autenticación Web, Onboarding y Vinculación WhatsApp (Prioridades 1, 2, 3 y 5) ---


class AuthRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    business_name: str = Field(..., min_length=2, max_length=140)
    trade_sector: str = Field(default="Comercio minorista y abarrotes", min_length=2, max_length=140)
    market_location: str = Field(default="Mercado Local", min_length=2, max_length=140)
    city: str = Field(default="Huamanga", min_length=2, max_length=80)
    region: str = Field(default="Ayacucho", min_length=2, max_length=80)
    goal_title: str = Field(
        default="Capital de trabajo e inventario para mi negocio",
        min_length=4,
        max_length=180,
    )
    goal_target_pen: float = Field(default=1600.0, gt=0)
    preferred_language: LanguageCode = "es"
    accepted_data_consent: bool = Field(
        ...,
        description="Consentimiento obligatorio para tratamiento de datos personales y financieros.",
    )
    consent_version: str = Field(
        default="v1.0-2026-11",
        min_length=2,
        max_length=40,
        description="Versión de las condiciones de tratamiento de datos aceptadas expresamente.",
    )
    whatsapp_claim_code: Optional[str] = Field(
        default=None,
        description="Código temporal de un solo uso si el registro inició por WhatsApp.",
    )


class AuthRegisterResponse(BaseModel):
    status: Literal[
        "PENDING_EMAIL_VERIFICATION",
        "VERIFICATION_REQUIRED",
        "VERIFIED_AND_ACTIVE",
    ]
    user_id: str
    entrepreneur_id: str = ""
    email: str
    verification_required: bool = True
    email_verification_required: bool = True
    verification_delivery_mode: str
    message: str


class AuthVerifyEmailRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    verification_code: str = Field(..., min_length=4, max_length=32)


class AuthLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    entrepreneur: EntrepreneurProfileInfo


class LanguagePreferenceUpdateRequest(BaseModel):
    preferred_language: LanguageCode


class WhatsappLinkGenerateResponse(BaseModel):
    link_code: str
    expires_at: str
    sandbox_join_instruction: str = ""
    sandbox_instructions: str = ""
    whatsapp_command: str
    wa_me_url: str = ""


class WhatsappClaimCodeRequest(BaseModel):
    claim_code: str = Field(..., min_length=4, max_length=40)

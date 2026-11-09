"""Endpoints para Perfil Financiero, otorgamiento de consentimiento y revocación inmediata."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.models import (
    ConsentGrantRequest,
    ConsentRecord,
    ConsentRevokeRequest,
    FinancialProfileReport,
    SharedConsentPublicView,
)
from app.security import AuthenticatedPrincipal, require_authenticated_entrepreneur
from app.services.finance_engine import generate_financial_profile
from app.services.store import store

router = APIRouter(
    prefix="/api",
    tags=["7, 8 & 9. Perfil Financiero y Consentimiento Revocable"],
)


@router.get("/profile", response_model=FinancialProfileReport)
def get_financial_profile(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> FinancialProfileReport:
    return generate_financial_profile(
        movements=store.list_movements(entrepreneur_id=principal.entrepreneur_id),
        entrepreneur=store.get_entrepreneur(principal.entrepreneur_id),
    )


@router.get("/consents", response_model=List[ConsentRecord])
def list_consents(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> List[ConsentRecord]:
    return store.list_consents(entrepreneur_id=principal.entrepreneur_id)


@router.post("/consents/grant", response_model=ConsentRecord, status_code=201)
def grant_consent(
    payload: ConsentGrantRequest,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> ConsentRecord:
    if not payload.accepted_terms:
        raise HTTPException(
            status_code=400,
            detail="Se requiere aceptación explícita del consentimiento informado por parte de la titular.",
        )
    profile = generate_financial_profile(
        movements=store.list_movements(entrepreneur_id=principal.entrepreneur_id),
        entrepreneur=store.get_entrepreneur(principal.entrepreneur_id),
    )
    return store.create_consent(
        recipient_entity=payload.recipient_entity.strip(),
        purpose=payload.purpose.strip(),
        evidence_hash=profile.evidence_integrity_hash,
        entrepreneur_id=principal.entrepreneur_id,
    )


@router.post("/consents/{consent_id}/revoke", response_model=ConsentRecord)
def revoke_consent(
    consent_id: str,
    payload: ConsentRevokeRequest,
    principal: AuthenticatedPrincipal = Depends(require_authenticated_entrepreneur),
) -> ConsentRecord:
    updated = store.revoke_consent(
        consent_id=consent_id,
        reason=payload.reason.strip(),
        entrepreneur_id=principal.entrepreneur_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Registro de consentimiento no encontrado")
    return updated


@router.get("/consents/shared/{share_token}")
def view_shared_profile_by_token(share_token: str) -> dict:
    consent = store.get_consent_by_token(share_token)
    if not consent:
        raise HTTPException(
            status_code=404, detail="Enlace de consentimiento inválido o inexistente."
        )
    if consent.status == "REVOCADO":
        raise HTTPException(
            status_code=403,
            detail=(
                f"ACCESO REVOCADO: La titular revocó este permiso el {consent.revoked_at}. "
                f"Motivo: {consent.revocation_reason}"
            ),
        )
    consent = store.mark_consent_expired_if_needed(consent)
    if consent.status == "EXPIRADO":
        raise HTTPException(
            status_code=403,
            detail=(
                f"ACCESO EXPIRADO: El enlace de consentimiento venció el {consent.expires_at}."
            ),
        )

    profile = generate_financial_profile(
        movements=store.list_movements(entrepreneur_id=consent.entrepreneur_id),
        entrepreneur=store.get_entrepreneur(consent.entrepreneur_id),
    )
    # Minimización de datos para vista compartida externa:
    # No se expone share_token, token_sha256 ni el ID interno de base de datos de la titular.
    redacted_entrepreneur = profile.entrepreneur.model_copy(
        update={"id": "TITULAR-VERIFICADA"}
    )
    sanitized_profile = profile.model_copy(
        update={"entrepreneur": redacted_entrepreneur}
    )
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
    return {
        "consent": public_consent,
        "shared_profile": sanitized_profile,
    }

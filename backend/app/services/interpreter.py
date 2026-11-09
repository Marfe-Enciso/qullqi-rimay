"""Intérprete de mensajes con salida JSON estructurada (`StructuredMovementExtraction`).

Soporta Español y Quechua Ayacuchano (Chanka) con confirmación obligatoria antes de guardar
y solicitud de aclaración cuando una expresión en quechua es incierta (Prioridad 5).
"""

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import List
from app.models import (
    LanguageCode,
    StructuredExtractedItem,
    StructuredMovementExtraction,
)
from app.services.gemini_adapter import call_gemini_structured_extraction
from app.services.i18n_quechua import (
    format_language_switched,
    format_pending_confirmation_prompt,
    format_uncertain_quechua_clarification,
)

SALE_KEYWORDS = [
    "vendí",
    "vendi",
    "venta",
    "ventas",
    "entró",
    "entro",
    "entraron",
    "salió",
    "salio",
    "salieron",
    "cobré",
    "cobre",
    "hice",
    "compraron",
    "pedido",
    "canasta",
    "canastas",
    # Quechua Ayacuchano (Chanka)
    "rantikurqani",
    "rantikuni",
    "hatumurqani",
    "rantikusqay",
]

EXPENSE_KEYWORDS = [
    "gasté",
    "gaste",
    "gasto",
    "pagué",
    "pague",
    "compré",
    "compre",
    "compra",
    "invertí",
    "inverti",
    "flete",
    "jabas",
    "bolsas",
    "transporte",
    "pasaje",
    "pasajes",
    "mototaxi",
    "mayorista",
    "carga",
    "puesto",
    "vigilancia",
    "hielo",
    "estiba",
    "merma",
    "malogró",
    "malogro",
    # Quechua Ayacuchano (Chanka)
    "gastarqani",
    "gastani",
    "pagarqani",
    "rantirqani",
]

QUECHUA_LEXICON = [
    "rantikurqani",
    "rantikuni",
    "rantirqani",
    "gastarqani",
    "pagarqani",
    "qullqi",
    "qullqita",
    "takyachini",
    "willakuy",
    "haykataq",
    "hayk'ataq",
    "imaynataq",
    "punchaw",
    "kunan",
    "allinmi",
    "manam",
    "pichay",
    "casera",
    "ruru",
]

FRUIT_TERMS = [
    "tuna",
    "chirimoya",
    "lúcuma",
    "lucuma",
    "palta",
    "granadilla",
    "papaya",
    "plátano",
    "platano",
    "naranja",
    "mandarina",
    "piña",
    "pina",
    "mango",
    "fresa",
    "fresas",
    "maracuyá",
    "maracuya",
    "pacay",
    "manzana",
    "uva",
    "fruta",
    "frutas",
]

LOGISTICS_TERMS = [
    "jabas",
    "bolsas",
    "flete",
    "mototaxi",
    "transporte",
    "pasaje",
    "pasajes",
    "carretilla",
    "estiba",
    "puesto",
    "arbitrio",
    "vigilancia",
    "hielo",
    "mallas",
    "canastillas",
    "merma",
]


def _detect_terms(clause: str) -> List[str]:
    lowered = clause.lower()
    found: List[str] = []
    for term in FRUIT_TERMS + LOGISTICS_TERMS + QUECHUA_LEXICON:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            found.append(term)
    return found


def _classify_clause(clause: str) -> str:
    lowered = clause.lower()
    exp_score = sum(1 for kw in EXPENSE_KEYWORDS if kw in lowered)
    sale_score = sum(1 for kw in SALE_KEYWORDS if kw in lowered)
    if exp_score > sale_score:
        return "GASTO"
    if sale_score > 0:
        return "VENTA"
    if any(t in lowered for t in LOGISTICS_TERMS):
        return "GASTO"
    return "VENTA"


def _infer_category(mtype: str, clause: str) -> str:
    lowered = clause.lower()
    if mtype == "VENTA":
        return "Ventas de frutas"
    if any(t in lowered for t in ["merma", "malogr", "madur", "descarte", "perdid"]):
        return "Mermas"
    if any(
        t in lowered
        for t in ["transporte", "pasaje", "pasajes", "mototaxi", "flete", "estiba", "carretilla"]
    ):
        return "Transporte"
    if any(
        t in lowered
        for t in ["bolsa", "empaque", "malla", "canastilla", "papel", "caja", "jaba"]
    ):
        return "Empaques"
    if any(
        t in lowered
        for t in ["puesto", "arbitrio", "vigilancia", "limpieza", "hielo", "balanza", "luz", "agua"]
    ):
        return "Gastos del puesto"
    return "Compra de mercadería"


def interpret_whatsapp_message(
    message: str,
    week_number: int = 8,
    preferred_language: LanguageCode = "es",
) -> StructuredMovementExtraction:
    cleaned = message.strip()
    lowered = cleaned.lower()
    cmd = re.sub(r"[.,!¡?¿]", " ", lowered)
    cmd = re.sub(r"\s+", " ", cmd).strip()

    # 0. Cambio explícito de idioma (Español / Quechua Ayacuchano)
    if re.search(
        r"\b(idioma\s+quechua|cambiar\s+a\s+quechua|runasimi|quechua\s+ayacuchano)\b",
        lowered,
    ):
        return StructuredMovementExtraction(
            detected_intent="CAMBIAR_IDIOMA",
            confidence=1.0,
            requires_confirmation=False,
            items=[],
            reply_preview_es=format_language_switched("qu"),
            detected_language="qu",
        )

    if re.search(
        r"\b(idioma\s+espa[ñn]ol|cambiar\s+a\s+espa[ñn]ol|castellano)\b",
        lowered,
    ):
        return StructuredMovementExtraction(
            detected_intent="CAMBIAR_IDIOMA",
            confidence=1.0,
            requires_confirmation=False,
            items=[],
            reply_preview_es=format_language_switched("es"),
            detected_language="es",
        )

    # 0b. "No entendí": volver a explicar de forma más simple (antes de cualquier IA externa)
    if re.search(
        r"(no\s+entend[ií]|no\s+entiendo|expl[ií]came|explicame|otra\s+forma|m[aá]s\s+f[aá]cil|"
        r"manam\s+yachanichu|manam\s+intindinichu|mana\s+intindinichu)",
        lowered,
    ):
        return StructuredMovementExtraction(
            detected_intent="EXPLICAR_DE_NUEVO",
            confidence=0.98,
            requires_confirmation=False,
            items=[],
            reply_preview_es="Claro, te lo explico de otra forma.",
            detected_language=preferred_language,
        )

    # Gemini (si está activado) solo se usa al final, cuando las reglas locales no entendieron nada:
    # así las respuestas normales son instantáneas y no dependen de la red.

    # 1. Intención de confirmar pendientes (Español y Quechua Ayacuchano)
    if re.fullmatch(
        r"(s[ií]|s[ií]\s+confirm[oa]|confirmar|confirmo|guardar|s[ií]\s+guardar|dale|ok|ari|ari\s+takyachini|takyachini|allinmi|chiqaqmi|listo|correcto|s[ií]\s+est[aá]\s+bien|est[aá]\s+bien)[.!]?",
        cmd,
    ):
        return StructuredMovementExtraction(
            detected_intent="CONFIRMAR_PENDIENTES",
            confidence=0.99,
            requires_confirmation=False,
            items=[],
            reply_preview_es="¡Perfecto casera! Confirmando tus movimientos pendientes.",
            detected_language=preferred_language,
        )

    # 2. Intención de descartar o corregir pendientes (Español y Quechua Ayacuchano)
    if re.fullmatch(
        r"(no|cancelar|corregir|borrar|descartar|no\s+guardar|mana|manam|pichay|pantay|est[aá]\s+mal|no\s+es\s+as[ií])[.!]?",
        cmd,
    ):
        return StructuredMovementExtraction(
            detected_intent="DESCARTAR_PENDIENTES",
            confidence=0.99,
            requires_confirmation=False,
            items=[],
            reply_preview_es="Entendido casera, he descartado el borrador pendiente.",
            detected_language=preferred_language,
        )

    # 3. Intención de consultar resumen o meta (Español y Quechua Ayacuchano)
    if any(
        kw in lowered
        for kw in [
            "resumen",
            "cómo voy",
            "como voy",
            "cuánto llevo",
            "cuanto llevo",
            "meta",
            "saldo",
            "willakuy",
            "haykataq",
            "hayk'ataq",
            "yupay",
        ]
    ) and not re.search(r"\d+", lowered):
        return StructuredMovementExtraction(
            detected_intent="CONSULTAR_RESUMEN",
            confidence=0.95,
            requires_confirmation=False,
            items=[],
            reply_preview_es="Aquí tienes el estado actualizado de tu Semana y tu meta de 8 semanas.",
            detected_language=preferred_language,
        )

    # 4. Detección de incertidumbre en Quechua (Prioridad 5: si hay términos en quechua o montos sin verbo claro)
    has_quechua_marker = any(
        qw in lowered
        for qw in ["qullqi", "rantikurqani", "rantirqani", "gastarqani", "kunan", "punchaw", "ruru", "solesmi"]
    )
    has_explicit_verb = any(k in lowered for k in SALE_KEYWORDS + EXPENSE_KEYWORDS)
    has_numbers = bool(re.search(r"\d+", lowered))

    if (has_quechua_marker and not (has_explicit_verb and has_numbers)) or (
        preferred_language == "qu" and has_numbers and not has_explicit_verb
    ):
        return StructuredMovementExtraction(
            detected_intent="REQUIERE_ACLARACION",
            confidence=0.45,
            requires_confirmation=False,
            items=[],
            reply_preview_es=format_uncertain_quechua_clarification(
                "qu" if has_quechua_marker or preferred_language == "qu" else "es"
            ),
            detected_language="qu" if has_quechua_marker else preferred_language,
        )

    # 5. Extracción de cláusulas con montos numéricos
    clauses = re.split(
        r"(?:\n|\.(?=\s|$)|,(?!\d)|;|\by\b|\bpero\b|\btambién\b|\btambien\b|\bluego\b|\bhinaspa\b|\bchaymanta\b)",
        cleaned,
        flags=re.IGNORECASE,
    )
    extracted_items: List[StructuredExtractedItem] = []

    current_type_context = "VENTA"
    for raw_clause in clauses:
        clause = raw_clause.strip()
        if not clause:
            continue

        lowered_clause = clause.lower()
        if any(k in lowered_clause for k in EXPENSE_KEYWORDS) or any(
            k in lowered_clause for k in SALE_KEYWORDS
        ):
            current_type_context = _classify_clause(clause)

        # 5a. Multiplicación cantidad x precio unitario (ej. "Vendí 20 kg de naranja a 4")
        qty_price_match = re.search(
            r"(\d+(?:[.,]\d{1,2})?)\s*(?:kg|kilos?|kilo|g|gramos?|jabas?|bolsas?|manos?|unidades?|unid|cajas?|sacos?|atados?|litros?|docenas?)?(?:\s+de\s+[a-záéíóúñ\s]+?)?\s+(?:a|x|por)\s+(?:s/?\.?\s*)?(\d+(?:[.,]\d{1,2})?)\b",
            clause,
            flags=re.IGNORECASE,
        )
        if qty_price_match:
            try:
                qty_dec = Decimal(qty_price_match.group(1).replace(",", "."))
                unit_dec = Decimal(qty_price_match.group(2).replace(",", "."))
                total_dec = (qty_dec * unit_dec).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                amount = float(total_dec)
                if amount > 0:
                    mtype = current_type_context
                    cat = _infer_category(mtype, clause)
                    terms = _detect_terms(clause)
                    desc_prefix = (
                        "Venta registrada" if mtype == "VENTA" else "Gasto registrado"
                    )
                    desc = (
                        f"{desc_prefix}: {clause[:90]} "
                        f"({qty_dec} x S/ {unit_dec:.2f} = S/ {total_dec:.2f})"
                    )
                    extracted_items.append(
                        StructuredExtractedItem(
                            movement_type=mtype,  # type: ignore[arg-type]
                            amount_pen=amount,
                            category=cat,
                            description=desc,
                            detected_terms=terms,
                        )
                    )
                    continue
            except Exception:
                pass

        # 5b. Montos directos en soles
        matches = list(
            re.finditer(
                r"(?:s/?\.?\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:soles|sol|s/\.?|lucas|qullqi)?",
                clause,
                flags=re.IGNORECASE,
            )
        )
        for m in matches:
            raw_num = m.group(1).replace(",", ".")
            try:
                amount = round(float(raw_num), 2)
            except ValueError:
                continue
            if amount <= 8 and re.search(rf"semana\s*{int(amount)}", lowered_clause):
                continue
            if amount <= 0:
                continue

            mtype = current_type_context
            cat = _infer_category(mtype, clause)
            terms = _detect_terms(clause)
            desc_prefix = "Venta registrada" if mtype == "VENTA" else "Gasto registrado"
            desc = f"{desc_prefix}: {clause[:110]}"

            extracted_items.append(
                StructuredExtractedItem(
                    movement_type=mtype,  # type: ignore[arg-type]
                    amount_pen=amount,
                    category=cat,
                    description=desc,
                    detected_terms=terms,
                )
            )

    if extracted_items:
        effective_lang: LanguageCode = (
            "qu" if has_quechua_marker or preferred_language == "qu" else "es"
        )
        reply = format_pending_confirmation_prompt(
            items=extracted_items,
            week_number=week_number,
            lang=effective_lang,
        )
        return StructuredMovementExtraction(
            detected_intent="REGISTRAR_MOVIMIENTO",
            confidence=0.96,
            requires_confirmation=True,
            items=extracted_items,
            reply_preview_es=reply,
            detected_language=effective_lang,
        )

    gemini_result = call_gemini_structured_extraction(cleaned, week_number=week_number)
    if gemini_result is not None and gemini_result.items:
        return gemini_result

    return StructuredMovementExtraction(
        detected_intent="SALUDO_O_AYUDA",
        confidence=0.90,
        requires_confirmation=False,
        items=[],
        reply_preview_es=(
            "¡Rimaykullayki casera! Puedo ayudarte en Español o Quechua Ayacuchano a anotar tus ventas y gastos. "
            "Por ejemplo: 'Vendí 20 kg de naranja a 4 y gasté 6 en pasaje' o 'Rantikurqani 80 soles papata'."
        ),
        detected_language=preferred_language,
    )

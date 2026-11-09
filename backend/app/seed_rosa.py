"""Datos semilla para la Demo Ficticia de Rosa Quispe (Vendedora de frutas en Huamanga).

1. `get_initial_movements()`: conserva intactos los 28 movimientos originales (`mov-seed-001`..`028`)
   ya sincronizados en Supabase (`oqbfuyxoclufkikaddoj`), sin modificarlos ni duplicarlos.
2. `get_enriched_demo_movements()`: genera un conjunto separado e idempotente de 133 movimientos
   coherentes distribuidos en las Semanas 1 a 7 (19 movimientos por semana) y deja la Semana 8
   interactiva para la presentación ante el jurado, cubriendo las 6 categorías:
   - Ventas de frutas
   - Compra de mercadería
   - Transporte
   - Empaques
   - Gastos del puesto
   - Mermas
"""

from typing import List, Tuple
from app.models import ChatMessageBubble, EntrepreneurProfileInfo, MovementRecord


def get_rosa_profile() -> EntrepreneurProfileInfo:
    return EntrepreneurProfileInfo(
        id="rosa-huamanga-001",
        full_name="Rosa Quispe Huamán (Demostración Ficticia)",
        business_name="Frutería La Huamanguina - Puesto 14",
        trade_sector="Comercio minorista de frutas de estación y regionales",
        market_location="Mercado Nery García Zárate",
        city="Huamanga",
        region="Ayacucho",
        phone_masked="+51 966 *** 418",
        goal_title="Comprar vitrina exhibidora refrigerada para fruta picada y jugos",
        goal_target_pen=2000.00,
        goal_weekly_target_pen=250.00,
        goal_weeks=8,
        active_week=8,
        preferred_language="es",
        data_consent_accepted=False,
        data_consent_accepted_at=None,
        data_consent_version=None,
        whatsapp_linked=True,
        is_fictional_demo=True,
    )


def get_initial_movements() -> List[MovementRecord]:
    """Conserva exactamente los 28 movimientos originales almacenados en Supabase."""
    e_id = "rosa-huamanga-001"
    raw_weeks = [
        (1, "VENTA", 410.0, "Ventas de frutas", "Venta de tuna morada, verde y chirimoya", "Casera vendí 410 soles de tuna y chirimoya en la mañana", "2026-09-14T13:10:00Z"),
        (1, "VENTA", 270.0, "Ventas de frutas", "Venta de palta fuerte y granadilla", "Por la tarde salieron 270 soles en palta fuerte y granadilla", "2026-09-16T18:20:00Z"),
        (1, "GASTO", 340.0, "Compra de mercadería", "Compra de jabas de fruta al mayorista del valle", "Pagué 340 soles al camión mayorista por las jabas de fruta", "2026-09-14T06:30:00Z"),
        (1, "GASTO", 80.0, "Gastos del puesto", "Estiba, bolsas biodegradables y limpieza de puesto", "Gasté 80 soles en bolsas, carretilla y pago del puesto", "2026-09-17T19:00:00Z"),
        (2, "VENTA", 430.0, "Ventas de frutas", "Venta de lúcuma de Luricocha y palta", "Esta semana vendí 430 soles de lúcuma y palta", "2026-09-21T14:00:00Z"),
        (2, "VENTA", 280.0, "Ventas de frutas", "Venta de naranja, plátano de isla y papaya", "Vendí 280 soles más en papaya y plátano para desayuno", "2026-09-24T17:45:00Z"),
        (2, "GASTO", 385.0, "Compra de mercadería", "Abastecimiento de lúcuma, papaya y plátano", "Gasté 385 soles comprando carga fresca de Luricocha", "2026-09-21T06:15:00Z"),
        (2, "GASTO", 70.0, "Transporte", "Transporte en mototaxi y papel periódico de embalaje", "Pagué 70 soles de mototaxi y papel para envolver fruta", "2026-09-25T18:10:00Z"),
        (3, "VENTA", 390.0, "Ventas de frutas", "Venta de chirimoya, granadilla y mandarina", "Entró 390 soles de chirimoya y mandarina dulce", "2026-09-28T15:00:00Z"),
        (3, "VENTA", 260.0, "Ventas de frutas", "Venta de piña golden y fresas", "Vendí 260 soles de piña golden y fresas", "2026-10-01T18:00:00Z"),
        (3, "GASTO", 350.0, "Compra de mercadería", "Reposición de piña del VRAEM y cítricos", "Gasté 350 soles en jabas de piña y mandarina", "2026-09-28T06:40:00Z"),
        (3, "GASTO", 65.0, "Gastos del puesto", "Hielo, mallas para fruta y arbitrio municipal", "Se fue 65 soles en mallas y arbitrio del mercado", "2026-10-02T17:30:00Z"),
        (4, "VENTA", 460.0, "Ventas de frutas", "Venta fuerte de fin de mes: palta, mango y lúcuma", "Por quincena y fin de mes vendí 460 soles en palta y mango", "2026-10-05T16:10:00Z"),
        (4, "VENTA", 280.0, "Ventas de frutas", "Canastas de fruta para profesoras de colegio", "Hice 280 soles armando canastas de fruta para un colegio", "2026-10-08T18:30:00Z"),
        (4, "GASTO", 395.0, "Compra de mercadería", "Compra de mango, palta seleccionada y uva", "Invertí 395 soles en fruta de primera para las canastas", "2026-10-05T06:00:00Z"),
        (4, "GASTO", 75.0, "Empaques", "Canastillas de carrizo, celofán y cintas", "Gasté 75 soles en canastillas de carrizo y transporte", "2026-10-07T12:20:00Z"),
        (5, "VENTA", 425.0, "Ventas de frutas", "Venta de tuna, pacay y granadilla", "Vendí 425 soles de tuna, pacay y granadilla a mis caseras", "2026-10-12T15:30:00Z"),
        (5, "VENTA", 270.0, "Ventas de frutas", "Venta de papaya, melón y plátano", "Salió 270 soles en papaya y melón para juguerías", "2026-10-15T17:50:00Z"),
        (5, "GASTO", 375.0, "Compra de mercadería", "Compra mayorista de fruta fresca", "Pagué 375 soles al proveedor de fruta de valle", "2026-10-12T06:20:00Z"),
        (5, "GASTO", 70.0, "Transporte", "Flete, ayudante de descarga y bolsas", "Pagué 70 soles de flete y ayudante", "2026-10-16T18:00:00Z"),
        (6, "VENTA", 440.0, "Ventas de frutas", "Venta de palta fuerte, chirimoya cumbe y fresa", "Vendí 440 soles en palta fuerte y chirimoya grande", "2026-10-19T14:50:00Z"),
        (6, "VENTA", 280.0, "Ventas de frutas", "Venta de maracuyá, naranja para jugo y piña", "Entraron 280 soles por venta de naranja y maracuyá", "2026-10-22T18:10:00Z"),
        (6, "GASTO", 390.0, "Compra de mercadería", "Compra de chirimoya, palta y sacos de naranja", "Gasté 390 soles en los sacos de naranja y cajas de palta", "2026-10-19T06:10:00Z"),
        (6, "GASTO", 70.0, "Empaques", "Bolsas, balanza mantenimiento y transporte", "Gasté 70 soles en bolsas y movilidad", "2026-10-23T18:40:00Z"),
        (7, "VENTA", 455.0, "Ventas de frutas", "Venta en feria de Todos los Santos (fruta para ofrendas y mesa)", "Por víspera de feria vendí 455 soles en piña, plátano y granadilla", "2026-10-27T16:00:00Z"),
        (7, "VENTA", 280.0, "Ventas de frutas", "Venta de lúcuma, mango y manzana Israel", "Vendí 280 soles en manzana, mango y lúcuma", "2026-10-30T18:30:00Z"),
        (7, "GASTO", 395.0, "Compra de mercadería", "Compra de fruta surtida para campaña de feria", "Compré 395 soles en mercadería surtida para la semana 7", "2026-10-27T05:50:00Z"),
        (7, "GASTO", 75.0, "Gastos del puesto", "Jabas plásticas, flete y pago semanal de vigilancia", "Gasté 75 soles en flete, jabas y vigilancia del mercado", "2026-10-31T19:00:00Z"),
    ]

    records: List[MovementRecord] = []
    for idx, (wk, mtype, amt, cat, desc, raw, ts) in enumerate(raw_weeks, start=1):
        records.append(
            MovementRecord(
                id=f"mov-seed-{idx:03d}",
                entrepreneur_id=e_id,
                week_number=wk,
                movement_type=mtype,  # type: ignore[arg-type]
                amount_pen=amt,
                category=cat,
                description=desc,
                raw_message=raw,
                source_channel="WHATSAPP_HISTORICO",
                ai_confidence=0.98,
                status="CONFIRMADO",
                created_at=ts,
                confirmed_at=ts,
            )
        )
    return records


def get_enriched_demo_movements() -> List[MovementRecord]:
    """Genera 133 movimientos ficticios coherentes en las Semanas 1-7 (19 por semana) para la Demo Ampliada.

    - Ventas totales Semanas 1-7: S/ 4,930.00
    - Gastos totales Semanas 1-7: S/ 3,135.00
    - Excedente Neto Acumulado Semanas 1-7: S/ 1,795.00 (faltan S/ 205.00 en la Semana 8 interactiva).
    """
    e_id = "rosa-huamanga-001"
    week_dates = {
        1: ("2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18", "2026-09-19", "2026-09-20"),
        2: ("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"),
        3: ("2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"),
        4: ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"),
        5: ("2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"),
        6: ("2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"),
        7: ("2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"),
    }

    # 8 ventas por semana + 11 gastos por semana = 19 movimientos por semana * 7 semanas = 133 movimientos
    weekly_sales_splits: dict[int, List[Tuple[float, str, str]]] = {
        1: [
            (110.0, "Venta de tuna morada y verde de Huanta (22 kg x S/ 5)", "Vendí 110 soles de tuna morada y verde temprano"),
            (95.0, "Venta de palta fuerte de Luricocha a caseras", "Salieron 95 soles de palta fuerte seleccionada"),
            (85.0, "Venta de chirimoya cumbe dulce por docena", "Vendí 85 soles en chirimoya cumbe"),
            (90.0, "Venta de granadilla y maracuyá para jugos", "Entraron 90 soles de granadilla y maracuyá"),
            (75.0, "Venta de naranja huando y mandarina sin pepa", "Vendí 75 soles de naranja huando y mandarina"),
            (80.0, "Venta de papaya y plátano de seda para desayunos", "Cobré 80 soles de papaya y plátano de seda"),
            (70.0, "Venta de piña golden del VRAEM picada y entera", "Vendí 70 soles de piña golden del VRAEM"),
            (75.0, "Venta de domingo: surtido de fruta familiar", "En la feria dominical vendí 75 soles de fruta surtida"),
        ],
        2: [
            (115.0, "Venta de lúcuma de Luricocha para heladerías", "Vendí 115 soles de lúcuma madura a heladería local"),
            (100.0, "Venta de palta fuerte primera calidad (20 kg x S/ 5)", "Vendí 20 kg de palta a 5 soles"),
            (90.0, "Venta de papaya selva y plátano de isla", "Salieron 90 soles en papaya y plátano de isla"),
            (95.0, "Venta de naranja para jugo por malla", "Entró 95 soles por mallas de naranja para jugo"),
            (80.0, "Venta de tuna blanca y chirimoya", "Vendí 80 soles de tuna blanca y chirimoya"),
            (80.0, "Venta de fresas frescas y granadilla", "Vendí 80 soles de fresas y granadilla para niños"),
            (75.0, "Venta de manzana Israel y pera de agua", "Cobré 75 soles en manzana Israel y pera"),
            (75.0, "Venta dominical de canastas económicas de fruta", "Hice 75 soles en canastas surtidas de domingo"),
        ],
        3: [
            (105.0, "Venta de chirimoya y mandarina dulce", "Entró 105 soles de chirimoya y mandarina"),
            (90.0, "Venta de piña golden y maracuyá del VRAEM", "Vendí 90 soles de piña golden y maracuyá"),
            (85.0, "Venta de palta fuerte y limón sutil", "Salieron 85 soles de palta fuerte y limón"),
            (85.0, "Venta de granadilla y tumbo serrano", "Vendí 85 soles en granadilla y tumbo"),
            (75.0, "Venta de plátano palillo y de isla", "Cobré 75 soles de plátano palillo e isla"),
            (75.0, "Venta de papaya madura a juguerías del mercado", "Vendí 75 soles de papaya a las juguerías"),
            (70.0, "Venta de fresas y mora andina", "Entraron 70 soles de fresa y mora"),
            (65.0, "Venta de cierre de semana: naranja y manzana", "Vendí 65 soles de naranja y manzana el domingo"),
        ],
        4: [
            (120.0, "Venta de quincena: palta fuerte y mango kent", "Por fin de mes vendí 120 soles en palta y mango"),
            (105.0, "Canastas de fruta para profesoras de colegio en Huamanga", "Hice 105 soles en canastas de fruta para colegio"),
            (95.0, "Venta de lúcuma y chirimoya seleccionada", "Vendí 95 soles de lúcuma y chirimoya grande"),
            (95.0, "Venta de uva borgoña e Italia por kilo", "Salieron 95 soles de uva borgoña y verde"),
            (85.0, "Venta de granadilla y naranja huando", "Vendí 85 soles de granadilla y naranja huando"),
            (85.0, "Venta de piña golden y papaya para restaurantes", "Cobré 85 soles de piña y papaya para restaurante"),
            (80.0, "Venta de tuna morada y pacay", "Entraron 80 soles de tuna y pacay"),
            (75.0, "Venta dominical de fruta picada en envases", "Vendí 75 soles de vasos de fruta fresca"),
        ],
        5: [
            (110.0, "Venta de tuna, pacay y granadilla a caseras", "Rantikurqani 110 soles tuna, pacay y granadilla"),
            (95.0, "Venta de papaya, melón y plátano para juguerías", "Salió 95 soles en papaya y melón"),
            (90.0, "Venta de palta fuerte de Luricocha", "Vendí 90 soles de palta fuerte cremosa"),
            (90.0, "Venta de naranja de jugo y mandarina", "Entraron 90 soles de cítricos dulces"),
            (80.0, "Venta de chirimoya y lúcuma", "Vendí 80 soles de chirimoya y lúcuma"),
            (80.0, "Venta de piña golden y sandía por tajadas", "Cobré 80 soles en piña y sandía"),
            (75.0, "Venta de manzana delicia y plátano de seda", "Vendí 75 soles de manzana y plátano para loncheras"),
            (75.0, "Venta de domingo en el puesto 14", "Cerré la semana con 75 soles de fruta variada"),
        ],
        6: [
            (115.0, "Venta de palta fuerte y chirimoya cumbe grande", "Vendí 115 soles en palta fuerte y chirimoya"),
            (100.0, "Venta de fresa, arándano y granadilla", "Salieron 100 soles de fresa y granadilla"),
            (95.0, "Venta de maracuyá y naranja para jugos", "Entraron 95 soles por venta de naranja y maracuyá"),
            (90.0, "Venta de mango edward y piña golden", "Vendí 90 soles de mango y piña golden"),
            (85.0, "Venta de lúcuma y plátano de isla", "Cobré 85 soles de lúcuma y plátano"),
            (80.0, "Venta de papaya y melón coquito", "Vendí 80 soles de papaya y melón"),
            (80.0, "Venta de tuna y pacay del valle", "Entraron 80 soles de tuna fresca y pacay"),
            (75.0, "Venta dominical de fruta seleccionada", "Vendí 75 soles el domingo por la mañana"),
        ],
        7: [
            (120.0, "Venta de campaña Todos los Santos: piña, plátano y granadilla para ofrendas", "Por víspera de Todos los Santos vendí 120 soles de fruta para mesa"),
            (105.0, "Venta de canastas familiares de Todos los Santos", "Hice 105 soles en canastas de fruta para familias"),
            (95.0, "Venta de lúcuma, mango y manzana Israel", "Vendí 95 soles en manzana, mango y lúcuma"),
            (95.0, "Venta de palta fuerte y chirimoya especial", "Salieron 95 soles de palta y chirimoya"),
            (85.0, "Venta de naranja huando y mandarina", "Entraron 85 soles de naranja huando y mandarina"),
            (80.0, "Venta de uva, pera y durazno", "Vendí 80 soles de uva, pera y durazno para altares"),
            (80.0, "Venta de papaya, piña y maracuyá", "Cobré 80 soles de fruta para refrescos y ponches"),
            (75.0, "Venta del 1 de noviembre en el mercado", "Vendí 75 soles el domingo de feria"),
        ],
    }

    weekly_expense_splits: dict[int, List[Tuple[float, str, str, str]]] = {
        1: [
            (120.0, "Compra de mercadería", "Compra mayorista de jabas de tuna y chirimoya", "Pagué 120 soles al mayorista de Huanta por jabas de tuna"),
            (95.0, "Compra de mercadería", "Compra de cajas de palta fuerte de Luricocha", "Compré 95 soles de palta fuerte al productor"),
            (70.0, "Compra de mercadería", "Compra de sacos de naranja y granadilla", "Invertí 70 soles en sacos de naranja y granadilla"),
            (55.0, "Compra de mercadería", "Compra de piña del VRAEM y plátano", "Pagué 55 soles por carga de piña y plátano"),
            (18.0, "Transporte", "Flete compartido de camión mayorista al mercado", "Pagué 18 soles de flete del camión"),
            (12.0, "Transporte", "Mototaxi y carretilla de estiba hasta el puesto 14", "Gasté 12 soles en mototaxi y estiba"),
            (12.0, "Empaques", "Compra de millar de bolsas biodegradables y papel", "Compré 12 soles de bolsas biodegradables"),
            (8.0, "Empaques", "Mallas plásticas para fruta y cintas", "Gasté 8 soles en mallas para naranja"),
            (12.0, "Gastos del puesto", "Pago semanal de arbitrio y limpieza del Mercado Nery García", "Pagué 12 soles de arbitrio municipal del puesto"),
            (8.0, "Gastos del puesto", "Agua, desinfección y vigilancia nocturna", "Gasté 8 soles en limpieza y vigilancia"),
            (10.0, "Mermas", "Merma de papaya y plátano muy maduro descontado", "Tuve 10 soles de merma en fruta madura"),
        ],
        2: [
            (135.0, "Compra de mercadería", "Abastecimiento de lúcuma y palta de Luricocha", "Gasté 135 soles en carga de lúcuma y palta"),
            (105.0, "Compra de mercadería", "Compra de papaya, plátano de isla y manzana", "Pagué 105 soles al proveedor de papaya y plátano"),
            (80.0, "Compra de mercadería", "Compra de cítricos y granadilla", "Compré 80 soles en naranja y granadilla"),
            (65.0, "Compra de mercadería", "Compra de fresa fresca y tuna blanca", "Invertí 65 soles en cajas de fresa y tuna"),
            (15.0, "Transporte", "Flete de fruta desde Luricocha", "Pagué 15 soles de flete de Luricocha"),
            (10.0, "Transporte", "Pasajes y mototaxi de madrugada", "Gasté 10 soles en pasaje y mototaxi"),
            (10.0, "Empaques", "Papel periódico de embalaje y bolsas", "Pagué 10 soles en papel y bolsas"),
            (8.0, "Empaques", "Envases biodegradables para fresas", "Gasté 8 soles en envases para fresa"),
            (10.0, "Gastos del puesto", "Arbitrio semanal del puesto 14", "Pagué 10 soles de arbitrio del mercado"),
            (7.0, "Gastos del puesto", "Vigilancia y alumbrado del pasaje de frutas", "Gasté 7 soles en vigilancia"),
            (10.0, "Mermas", "Merma por magulladura de fresas en el traslado", "Se perdieron 10 soles en merma de fresa"),
        ],
        3: [
            (125.0, "Compra de mercadería", "Reposición de piña golden y maracuyá del VRAEM", "Gasté 125 soles en jabas de piña y maracuyá"),
            (95.0, "Compra de mercadería", "Compra de chirimoya y mandarina dulce", "Pagué 95 soles por chirimoya y mandarina"),
            (75.0, "Compra de mercadería", "Compra de palta fuerte y granadilla", "Compré 75 soles de palta y granadilla"),
            (55.0, "Compra de mercadería", "Compra de plátano y papaya", "Invertí 55 soles en plátano y papaya"),
            (14.0, "Transporte", "Flete de carga de fruta", "Pagué 14 soles de flete"),
            (10.0, "Transporte", "Estiba y movilidad local", "Gasté 10 soles en carretilla y pasaje"),
            (10.0, "Empaques", "Mallas y bolsas de despacho", "Compré 10 soles de mallas y bolsas"),
            (6.0, "Empaques", "Servilletas y papel protector", "Gasté 6 soles en papel para chirimoya"),
            (10.0, "Gastos del puesto", "Arbitrio municipal y recojo de residuos", "Pagué 10 soles de arbitrio"),
            (6.0, "Gastos del puesto", "Hielo para conservar fruta picada", "Gasté 6 soles en hielo"),
            (9.0, "Mermas", "Merma de mandarina y plátano maduro", "Desconté 9 soles por merma de fruta"),
        ],
        4: [
            (140.0, "Compra de mercadería", "Compra de mango kent y palta de primera", "Invertí 140 soles en mango y palta seleccionada"),
            (110.0, "Compra de mercadería", "Compra de uva, lúcuma y chirimoya para canastas", "Pagué 110 soles en uva y chirimoya"),
            (80.0, "Compra de mercadería", "Compra de granadilla, naranja y piña", "Compré 80 soles de cítricos y piña"),
            (65.0, "Compra de mercadería", "Compra de tuna y pacay", "Gasté 65 soles en tuna y pacay"),
            (16.0, "Transporte", "Flete de camión y descarga", "Pagué 16 soles de flete"),
            (11.0, "Transporte", "Mototaxi para entrega de canastas a colegio", "Gasté 11 soles en mototaxi para entregar pedido"),
            (12.0, "Empaques", "Canastillas de carrizo y papel celofán", "Compré 12 soles en canastillas de carrizo"),
            (8.0, "Empaques", "Cintas decorativas y bolsas", "Gasté 8 soles en cintas y bolsas"),
            (10.0, "Gastos del puesto", "Arbitrio semanal y limpieza", "Pagué 10 soles de puesto"),
            (8.0, "Gastos del puesto", "Calibración de balanza y vigilancia", "Gasté 8 soles en balanza y vigilancia"),
            (10.0, "Mermas", "Merma de mango muy maduro por calor", "Hubo 10 soles de merma por calor"),
        ],
        5: [
            (130.0, "Compra de mercadería", "Compra mayorista de tuna, pacay y granadilla", "Pagué 130 soles al proveedor del valle"),
            (105.0, "Compra de mercadería", "Compra de papaya, melón y plátano", "Compré 105 soles de papaya y melón"),
            (75.0, "Compra de mercadería", "Compra de palta fuerte y cítricos", "Invertí 75 soles en palta y naranja"),
            (65.0, "Compra de mercadería", "Compra de piña, sandía y manzana", "Gasté 65 soles en piña y manzana"),
            (15.0, "Transporte", "Flete y ayudante de descarga", "Pagué 15 soles de flete"),
            (10.0, "Transporte", "Pasajes de toda la semana en combi/mototaxi", "Gasté 10 soles en pasajes"),
            (10.0, "Empaques", "Bolsas biodegradables medianas y grandes", "Compré 10 soles de bolsas"),
            (8.0, "Empaques", "Envases para fruta picada", "Gasté 8 soles en envases"),
            (10.0, "Gastos del puesto", "Pago semanal de puesto y agua", "Pagué 10 soles del puesto"),
            (8.0, "Gastos del puesto", "Vigilancia y escobas de limpieza", "Gasté 8 soles en vigilancia"),
            (9.0, "Mermas", "Merma de sandía y papaya por falta de refrigeración", "Perdí 9 soles de fruta por no tener aún la vitrina refrigerada"),
        ],
        6: [
            (135.0, "Compra de mercadería", "Compra de cajas de palta fuerte y chirimoya cumbe", "Gasté 135 soles en cajas de palta y chirimoya"),
            (110.0, "Compra de mercadería", "Compra de fresa, granadilla y maracuyá", "Pagué 110 soles por fresa y granadilla"),
            (80.0, "Compra de mercadería", "Compra de sacos de naranja para jugo y piña", "Compré 80 soles en sacos de naranja y piña"),
            (65.0, "Compra de mercadería", "Compra de lúcuma, papaya y plátano", "Invertí 65 soles en lúcuma y papaya"),
            (15.0, "Transporte", "Flete de proveedor mayorista", "Pagué 15 soles de flete"),
            (10.0, "Transporte", "Movilidad y estiba en el mercado", "Gasté 10 soles en estiba"),
            (10.0, "Empaques", "Bolsas y mallas fruteras", "Compré 10 soles de bolsas y mallas"),
            (8.0, "Empaques", "Cajas de cartón para pedidos", "Gasté 8 soles en cajas"),
            (10.0, "Gastos del puesto", "Arbitrio municipal semanal", "Pagué 10 soles de arbitrio"),
            (8.0, "Gastos del puesto", "Hielo y vigilancia del puesto", "Gasté 8 soles en hielo y vigilancia"),
            (9.0, "Mermas", "Merma de chirimoya madura", "Tuve 9 soles de merma en chirimoya"),
        ],
        7: [
            (140.0, "Compra de mercadería", "Compra de piña, plátano y granadilla para Todos los Santos", "Compré 140 soles en fruta para feria de Todos los Santos"),
            (110.0, "Compra de mercadería", "Compra de manzana Israel, mango y lúcuma", "Pagué 110 soles en manzana, mango y lúcuma"),
            (80.0, "Compra de mercadería", "Compra de palta fuerte y chirimoya", "Invertí 80 soles en palta y chirimoya"),
            (65.0, "Compra de mercadería", "Compra de uva, pera, durazno y naranja", "Gasté 65 soles en fruta fina para ofrendas"),
            (16.0, "Transporte", "Flete especial de feria y descarga", "Pagué 16 soles de flete de feria"),
            (11.0, "Transporte", "Mototaxi y transporte de canastas", "Gasté 11 soles en mototaxi"),
            (12.0, "Empaques", "Jabas plásticas y canastillas de feria", "Compré 12 soles en jabas y canastillas"),
            (8.0, "Empaques", "Bolsas y papel seda para canastas", "Gasté 8 soles en bolsas y papel"),
            (10.0, "Gastos del puesto", "Arbitrio y derecho de feria", "Pagué 10 soles de puesto"),
            (8.0, "Gastos del puesto", "Pago semanal de vigilancia y limpieza", "Gasté 8 soles en vigilancia"),
            (10.0, "Mermas", "Merma de fruta madura al cierre de feria", "Desconté 10 soles de merma al cerrar la feria"),
        ],
    }

    records: List[MovementRecord] = []
    seq = 1
    for wk in range(1, 8):
        days = week_dates[wk]
        # 8 ventas distribuidas en los 7 días de la semana
        for s_idx, (amt, desc, raw) in enumerate(weekly_sales_splits[wk]):
            day_str = days[s_idx % len(days)]
            hour = 10 + (s_idx % 8)
            ts = f"{day_str}T{hour:02d}:15:00Z"
            records.append(
                MovementRecord(
                    id=f"demo-ext-w{wk}-s{s_idx + 1:02d}-{seq:03d}",
                    entrepreneur_id=e_id,
                    week_number=wk,
                    movement_type="VENTA",
                    amount_pen=amt,
                    category="Ventas de frutas",
                    description=desc,
                    raw_message=raw,
                    source_channel="WHATSAPP_HISTORICO_DEMO",
                    ai_confidence=0.98,
                    status="CONFIRMADO",
                    created_at=ts,
                    confirmed_at=ts,
                )
            )
            seq += 1

        # 11 gastos distribuidos en los 7 días de la semana
        for g_idx, (amt, cat, desc, raw) in enumerate(weekly_expense_splits[wk]):
            day_str = days[g_idx % len(days)]
            hour = 6 + (g_idx % 11)
            ts = f"{day_str}T{hour:02d}:30:00Z"
            records.append(
                MovementRecord(
                    id=f"demo-ext-w{wk}-g{g_idx + 1:02d}-{seq:03d}",
                    entrepreneur_id=e_id,
                    week_number=wk,
                    movement_type="GASTO",
                    amount_pen=amt,
                    category=cat,
                    description=desc,
                    raw_message=raw,
                    source_channel="WHATSAPP_HISTORICO_DEMO",
                    ai_confidence=0.98,
                    status="CONFIRMADO",
                    created_at=ts,
                    confirmed_at=ts,
                )
            )
            seq += 1

    return records


def get_initial_chat_history() -> List[ChatMessageBubble]:
    return [
        ChatMessageBubble(
            id="chat-init-1",
            sender="QULLQI_BOT",
            text=(
                "¡Rimaykullayki casera Rosa! 🍐🥑 (Escenario Ficticio de Demostración — 8 Semanas). "
                "Ya tienes registradas tus Semanas 1 a 7 completas en el Mercado Nery García Zárate de Huamanga "
                "con S/ 1,795.00 de ganancia neta acumulada hacia tu meta de S/ 2,000.00 (vitrina refrigerada). "
                "¡Solo te faltan S/ 205.00 en esta Semana 8! Puedes escribirme en Español o en Quechua Ayacuchano."
            ),
            timestamp="2026-11-08T08:00:00Z",
            week_number=8,
        ),
        ChatMessageBubble(
            id="chat-init-2",
            sender="ROSA",
            text="Allillanchu Qullqi Bot, kunan punchaw Semana 8 qallarisunchik.",
            timestamp="2026-11-08T08:05:00Z",
            week_number=8,
        ),
        ChatMessageBubble(
            id="chat-init-3",
            sender="QULLQI_BOT",
            text=(
                "¡Allillanmi casera Rosa! 🌱 Escríbeme tus ventas o gastos del día "
                "(por ejemplo: «Vendí 20 kg de naranja a 4 y gasté 6 en pasaje» o «Rantikurqani 90 soles palta») "
                "y te pediré tu confirmación antes de guardarlos."
            ),
            timestamp="2026-11-08T08:05:10Z",
            week_number=8,
        ),
    ]

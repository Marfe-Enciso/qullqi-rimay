"""Servicio de explicaciones financieras en español sencillo y empático.

Traduce números calculados por Python en mensajes claros sin tecnicismos bancarios.
Los textos usan el nombre y la meta de cada emprendedora (no solo los de la demo).
"""


def explain_weekly_summary_plain(
    week_number: int,
    sales: float,
    expenses: float,
    net: float,
    weekly_target: float,
    confirmed_count: int,
    pending_count: int,
    first_name: str = "casera",
) -> str:
    if confirmed_count == 0 and pending_count == 0:
        return (
            f"En la Semana {week_number} aún no tienes ventas ni gastos confirmados. "
            f"Escríbeme por WhatsApp qué vendiste hoy en tu negocio para empezar a sumar."
        )

    pending_note = (
        f" (Tienes {pending_count} movimiento(s) esperando tu confirmación en el chat)."
        if pending_count > 0
        else ""
    )

    if net >= weekly_target:
        extra = round(net - weekly_target, 2)
        return (
            f"¡Excelente trabajo en la Semana {week_number}, {first_name}! Vendiste S/ {sales:.2f} "
            f"y pagaste S/ {expenses:.2f} en gastos del negocio. Te quedaron S/ {net:.2f} limpios en el bolsillo, "
            f"superando tu meta semanal de S/ {weekly_target:.2f} por S/ {extra:.2f}.{pending_note}"
        )
    elif net > 0:
        missing = round(weekly_target - net, 2)
        return (
            f"En la Semana {week_number} vendiste S/ {sales:.2f} y gastaste S/ {expenses:.2f}. "
            f"Te van quedando S/ {net:.2f} libres. Solo te faltan S/ {missing:.2f} para alcanzar "
            f"tu meta de S/ {weekly_target:.2f} de esta semana.{pending_note}"
        )
    else:
        return (
            f"En la Semana {week_number} tus compras de mercadería y gastos (S/ {expenses:.2f}) "
            f"todavía superan a las ventas registradas (S/ {sales:.2f}). Conforme vendas lo que compraste, "
            f"tu saldo libre subirá.{pending_note}"
        )


def explain_eight_week_goal_plain(
    accumulated_net: float,
    goal_target: float,
    completed_weeks: int,
    total_weeks: int,
    first_name: str = "casera",
    goal_title: str = "tu meta",
) -> str:
    remaining = max(0.0, round(goal_target - accumulated_net, 2))
    goal_label = (goal_title or "tu meta").strip()
    goal_label = goal_label[0].lower() + goal_label[1:] if goal_label else "tu meta"
    if accumulated_net >= goal_target:
        surplus = round(accumulated_net - goal_target, 2)
        return (
            f"¡Felicitaciones, {first_name}! Cumpliste tus {total_weeks} semanas de constancia y juntaste "
            f"S/ {accumulated_net:.2f} libres (S/ {surplus:.2f} por encima de tu meta de S/ {goal_target:.2f}: "
            f"{goal_label}). Ya puedes generar tu Perfil Financiero y, si tú quieres, compartirlo."
        )
    return (
        f"Vas muy bien: llevas {completed_weeks} de {total_weeks} semanas registradas con constancia y "
        f"has juntado S/ {accumulated_net:.2f} libres de gastos. Te faltan S/ {remaining:.2f} "
        f"para llegar a los S/ {goal_target:.2f} de tu meta: {goal_label}."
    )

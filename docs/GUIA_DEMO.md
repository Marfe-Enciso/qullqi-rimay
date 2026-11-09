# Guía de Demostración en Vivo — Qullqi Rimay (Caso Rosa, Huamanga)

**Entrega Hackatón Women in Tech – Reto 2 BCP:** Lunes 9 de noviembre de 2026, 9:00 a. m. (Hora de Perú)

---

## 1. Contexto de la Protagonista (Datos Ficticios)
- **Nombre:** Rosa Quispe Huamán
- **Negocio:** Frutería La Huamanguina – Puesto 14, Mercado Nery García Zárate (Huamanga, Ayacucho)
- **Meta de 8 Semanas:** Juntar **S/ 2,000.00** libres de gastos (promedio S/ 250/semana) para comprar una **vitrina exhibidora refrigerada** para fruta picada y jugos.
- **Estado Inicial (Semanas 1 a 7 precargadas):**
  - Del 14 de septiembre al 01 de noviembre de 2026.
  - 28 movimientos confirmados.
  - Acumulado neto confirmado: **S/ 1,795.00** (89.75% de la meta).
  - Faltan **S/ 205.00** en la **Semana 8 (02 nov – 08 nov 2026 • En vivo)**.

---

## 2. Guion Paso a Paso para el Jurado

1. **Abrir el panel web (`http://127.0.0.1:5173/` o URL de Vercel):**
   - Mostrar la barra de **Meta de 8 Semanas** en `S/ 1,795.00 / S/ 2,000.00` con `7/8 sem (87.5%)`.
2. **Prueba de Interpretación con Multiplicación y Confirmación (Fase 1):**
   - En el **Simulador de WhatsApp**, hacer clic en el chip sugerido o escribir:
     > `"Vendí 20 kg de naranja a 4 y gasté 6 en pasaje"`
   - Mostrar cómo Qullqi Rimay desglosa en JSON estructurado:
     - `VENTA`: **S/ 80.00** (`20 x S/ 4.00 = S/ 80.00`)
     - `GASTO`: **S/ 6.00** (`gasté 6 en pasaje`)
   - Destacar que el acumulado **no cambia todavía** porque ambos movimientos nacen en estado `PENDIENTE` (confirmación en 2 pasos).
3. **Confirmar y Completar la Meta de 8 Semanas:**
   - Hacer clic en **Confirmar** o enviar `"Sí confirmo"`.
   - Enviar el segundo movimiento del día:
     > `"Casera hoy vendí 190 soles de palta fuerte y lúcuma, y gasté 45 soles en jabas y transporte"`
   - Confirmarlo con `"Sí confirmo"`.
   - Observar cómo la Semana 8 alcanza **S/ 219.00** libres (`74 + 145`), el acumulado sube a **S/ 2,014.00 / S/ 2,000.00 (100%)** y la explicación en español sencillo felicita a Rosa por completar sus 8 semanas de constancia.
4. **Generar Perfil Financiero, Compartir con Consentimiento y Revocar Acceso:**
   - Cambiar a la pestaña **Perfil Financiero y Consentimiento**.
   - Mostrar el aviso ético y regulatorio (`bcp_approval_claim = false`): Qullqi Rimay **no inventa aprobaciones crediticias del BCP**, sino que certifica constancia operativa con hash SHA-256.
   - Marcar la casilla de consentimiento informado de Rosa y hacer clic en **Generar Token de Acceso con Consentimiento**.
   - Hacer clic en **Probar enlace compartido** para verificar que el token activo permite consultar el perfil.
   - Hacer clic en **Revocar Acceso Ahora** y volver a probar el enlace para demostrar que devuelve inmediatamente **Acceso Bloqueado (`HTTP 403 Forbidden`)**.


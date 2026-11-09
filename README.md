# Qullqi Rimay (Dinero que Habla)

**Hackatón Women in Tech – Reto 2 BCP**  
*Asistente financiero conversacional por WhatsApp y perfilador de historial operativo verificable para mujeres microemprendedoras.*

---

## 1. Propósito y Arquitectura

**Qullqi Rimay** ("El dinero habla" en quechua chanka) transforma mensajes cotidianos de WhatsApp (texto o notas de voz transcritas en español andino/coloquial con términos en quechua como *qullqi*, *rantiy*, *hatun*, *wasi*) en registros financieros confirmados, métricas semanales calculadas determinísticamente en Python, y un **Perfil Financiero Operativo de 8 Semanas** compartible bajo consentimiento explícito y revocable en cualquier momento.

### Principios de Seguridad y Cumplimiento (Guardrails)
1. **Cero exposición de credenciales**: Todas las claves (`GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `TWILIO_AUTH_TOKEN`) residen exclusivamente en variables de entorno del servidor (`.env` ignorado por Git).
2. **Cero promesas o aprobaciones crediticias falsas**: El sistema **nunca** afirma ni simula que el BCP u otra entidad ha preaprobado o aprobado un crédito. El perfil financiero se presenta estrictamente como *Reporte de Historial Operativo Autodeclarado y Verificado por Flujo de Confirmación*.
3. **Confirmación explícita (Two-Step Commit)**: Ningún movimiento interpretado por IA impacta el libro mayor ni la meta de 8 semanas hasta que la usuaria lo confirma explícitamente (`PENDIENTE` -> `CONFIRMADO` / `DESCARTADO`).
4. **Cálculo determinístico en Python**: La IA interpreta la intención y explica resultados en español sencillo, pero **jamás** calcula saldos, márgenes ni cumplimientos de meta. Todo cálculo numérico se ejecuta en el motor financiero en Python (`app/services/finance_engine.py`).
5. **Consentimiento granular y revocable**: Compartir el perfil financiero genera un token único con registro de auditoría (fecha, destinatario, propósito, hash de evidencia) que la emprendedora puede revocar instantáneamente (`REVOCADO`), bloqueando de inmediato cualquier consulta externa.

---

## 2. Estructura del Proyecto

```text
Qullqi-Rimay/
├── README.md
├── .gitignore
├── docs/
│   ├── ARQUITECTURA.md
│   └── SUPABASE_SCHEMA.sql
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── render.yaml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # Aplicación FastAPI y configuración CORS
│   │   ├── config.py               # Configuración tipada y variables de entorno
│   │   ├── models.py               # Esquemas Pydantic (Movimientos, IA JSON, Perfil, Consentimiento)
│   │   ├── seed_rosa.py            # Precarga de Rosa (Huamanga): 7 semanas completas + meta de 8 semanas
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py           # Healthcheck del sistema
│   │   │   ├── movements.py        # Registro, confirmación y listado de ventas/gastos
│   │   │   ├── simulator.py        # Simulador web de WhatsApp + intérprete IA JSON estructurado
│   │   │   ├── analytics.py        # Resúmenes semanales en Python, meta 8 semanas y explicación sencilla
│   │   │   └── profile_consent.py  # Perfil financiero, otorgamiento y revocación de consentimiento
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── store.py            # Almacén en memoria / persistencia desacoplada lista para Supabase
│   │       ├── finance_engine.py   # Motor determinístico en Python (resúmenes, constancia, meta 8 sem)
│   │       ├── interpreter.py      # Intérprete con JSON estructurado (modo local determinístico + interfaz Gemini)
│   │       └── explainer.py        # Generador de explicaciones en español sencillo sin tecnicismos
│   └── tests/
│       ├── __init__.py
│       └── test_api.py             # Suite de pruebas automatizadas (pytest) de las 10 funciones
└── frontend/
    ├── .env.example
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── vercel.json
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── types.ts
        ├── api.ts
        └── components/
            ├── WhatsAppSimulator.tsx
            ├── WeeklyDashboard.tsx
            ├── EightWeekGoal.tsx
            └── FinancialProfileModal.tsx
```

---

## 3. Las 10 Funciones Principales

| # | Función | Implementación Backend | Implementación Frontend |
|---|---------|------------------------|-------------------------|
| 1 | Registrar ventas y gastos | `POST /api/movements` | Formulario rápido y vía chat |
| 2 | Interpretar mensajes con IA (JSON estructurado) | `POST /api/simulator/message` (`interpreter.py`) | Burbujas con desglose JSON estructurado |
| 3 | Confirmar movimientos antes de guardarlos | `POST /api/movements/{id}/confirm` o `reject` | Botones "Sí, guardar" / "Corregir" en WhatsApp |
| 4 | Calcular resúmenes semanales con Python | `GET /api/analytics/weekly` (`finance_engine.py`) | Tarjetas de ingresos, gastos, neto y margen |
| 5 | Explicar resultados en español sencillo | `explainer.py` incluido en `/api/analytics/weekly` | Panel "Qullqi Rimay te explica en sencillo" |
| 6 | Llevar una meta de ocho semanas | `GET /api/analytics/goal` | Barra de progreso de 8 semanas (Semanas 1-7 listas, Semana 8 en vivo) |
| 7 | Generar un perfil financiero | `GET /api/profile` | Vista de Perfil Operativo con aviso legal de no-aprobación |
| 8 | Compartirlo con consentimiento | `POST /api/consents/grant` y `GET /api/consents/shared/{token}` | Modal de consentimiento informado + enlace verificable |
| 9 | Revocar el acceso | `POST /api/consents/{id}/revoke` | Botón de revocación inmediata con estado auditado |
| 10 | Simulador web de WhatsApp | `/api/simulator/*` | Interfaz interactiva estilo WhatsApp con sugerencias para Semana 8 |

---

## 4. Escenario Demo: Rosa (Vendedora de Frutas en Huamanga)

- **Emprendedora**: Rosa Quispe, puesto de frutas de estación (tuna, chirimoya, lúcuma, granadilla, palta fuerte) en el Mercado Nery García Zárate, Huamanga (Ayacucho).
- **Meta de 8 semanas**: Ahorrar **S/ 2,000.00** de excedente neto acumulado (S/ 250.00 por semana promedio) durante 8 semanas consecutivas para comprar una vitrina refrigerada para jugos y fruta picada.
- **Estado precargado (Semanas 1 a 7)**: 7 semanas registradas y confirmadas con un acumulado neto de **S/ 1,795.00** (89.75% de la meta total).
- **Semana 8 (En vivo durante la demo)**: Inicia con S/ 0.00 o lista para registrar en vivo mediante el simulador de WhatsApp (ej. *"Casera hoy vendí 180 soles de palta fuerte y lúcuma, y gasté 45 soles en jabas y transporte"*). Al confirmar los movimientos de la Semana 8, Rosa supera los S/ 2,000.00 y completa sus 8 semanas de constancia verificada.


# Resultados de Pruebas Automatizadas y Persistencia Real en Supabase — Qullqi Rimay

**Fecha de ejecución:** 8 de noviembre de 2026  
**Proyecto Supabase:** `qullqi-rimay-demo` (`oqbfuyxoclufkikaddoj`)  
**Entorno:** Windows 11 • Python 3.12.13 (`pytest 9.2.0`) • Node.js + TypeScript + Vite (`5.4.21`)

---

## 1. Suite Automatizada Backend (`pytest -v` — 9/9 Aprobadas)

| # | Prueba (`backend/tests/test_api.py`) | Qué verifica | Resultado |
| :--- | :--- | :--- | :--- |
| 1 | `test_health_and_rosa_seed_state` | Salud del servicio y precarga de 28 movimientos históricos (Semanas 1–7) de Rosa Quispe (Huamanga). | ✅ `PASSED` |
| 2 | `test_rosa_orange_kg_multiplication_and_confirmation_flow` | Caso `"Vendí 20 kg de naranja a 4 y gasté 6 en pasaje"` → `VENTA: S/ 80.00`, `GASTO: S/ 6.00`, ambos en estado `PENDIENTE` y etiqueta de Semana 8 (`02 nov – 08 nov 2026 • En vivo`). | ✅ `PASSED` |
| 3 | `test_seven_preloaded_weeks_and_eight_week_goal_math` | Cálculo determinístico en Python (`Decimal`): Semanas 1–7 acumulan `S/ 1,795.00`, restan `S/ 205.00` para la meta de `S/ 2,000.00`. | ✅ `PASSED` |
| 4 | `test_simulator_ai_structured_json_and_confirmation_flow` | Flujo en 2 pasos (Borrador `PENDIENTE` → `"Sí confirmo"` → `CONFIRMADO`, alcanzando `S/ 2,040.00` y `goal_achieved = True`). | ✅ `PASSED` |
| 5 | `test_profile_generation_consent_grant_and_revocation_guardrails` | `bcp_approval_claim == False`, hash SHA-256 de evidencias, minimización de datos en vista compartida (`TITULAR-VERIFICADA`, sin exponer `share_token` ni `token_sha256`), y bloqueo `403` tras revocación. | ✅ `PASSED` |
| 6 | `test_shared_consent_expiration_enforcement` | Caducidad automática de enlaces compartidos (`expires_at <= now` → HTTP `403 Forbidden` y transición a estado `EXPIRADO`). | ✅ `PASSED` |
| 7 | `test_anonymous_access_rejected_on_all_private_and_admin_endpoints` | Bloqueo `401 Unauthorized` ante peticiones anónimas o con credenciales inválidas en todos los endpoints privados y administrativos (`/api/movements*`, `/api/analytics*`, `/api/simulator*`, `/api/profile`, `/api/consents*`, `/api/demo/reset`). | ✅ `PASSED` |
| 8 | `test_twilio_whatsapp_webhook_and_message_sid_idempotency` | Webhook `POST /api/twilio/webhook` con respuesta TwiML XML e idempotencia por `MessageSid`. | ✅ `PASSED` |
| 9 | `test_multi_entrepreneur_isolation_for_movements_and_consents` | Bloqueo `403 Forbidden` ante intento de usar un `X-Entrepreneur-Id` ajeno y bloqueo `404` ante confirmación/revocación cruzada entre emprendedoras. | ✅ `PASSED` |

---

## 2. Pruebas Controladas de Persistencia Real en Supabase (`USE_EXTERNAL_SUPABASE=true`)

Ejecutadas contra `https://oqbfuyxoclufkikaddoj.supabase.co` sin eliminar datos ni ejecutar resets destructivos:

1. **Confirmación de los 28 movimientos históricos de Rosa (Semanas 1–7)**:
   - Verificados `28` movimientos en `public.movements` (`week_number <= 7`, `status = 'CONFIRMADO'`, `accumulated_net_pen = S/ 1,795.00`) y `8` filas sincronizadas en `public.weekly_goals` (`wg-rosa-huamanga-001-w1` a `w8` con `weekly_target_pen = 250.00`).
2. **Registro y confirmación de movimiento ficticio en Semana 8**:
   - Creado movimiento `mov-cbf9bd21` (`VENTA`, `S/ 80.00`, `"20 kg de naranja a S/ 4.00 en puesto de Huamanga"`, `created_at = 2026-11-08T23:10:28.560344+00:00`) en estado `PENDIENTE` y confirmado (`confirmed_at = 2026-11-08T23:10:29.576597+00:00`).
3. **Verificación directa en Supabase (`public.movements` y `public.audit_logs`)**:
   - Registro `mov-cbf9bd21` almacenado en `public.movements` con `status = 'CONFIRMADO'` y 2 eventos en `public.audit_logs` (`CREATE_MOVEMENT`, `MOVEMENT_CONFIRMADO`).
4. **Reinicio #1 de FastAPI (`uvicorn` nuevo PID `2068`) y verificación de persistencia (Pasos 4 y 5)**:
   - Tras reiniciar FastAPI, `GET /api/movements?week_number=8` devolvió `mov-cbf9bd21` intacto (`CONFIRMADO`, `S/ 80.00`), `total_movements = 29` y `accumulated_net_pen = S/ 1,875.00`.
5. **Creación y revocación de consentimiento ficticio (Paso 6)**:
   - Creado consentimiento `cons-3fd075b6c73e` (`token_sha256 = 74941ff9c92fedd16ed5df2494935375d6d5ed086664cf9fce1b6155d5708b14`).
   - Enlace compartido verificado activo (`HTTP 200`, sin exponer `share_token` ni `token_sha256`).
   - Revocado mediante `POST /api/consents/cons-3fd075b6c73e/revoke` (`revoked_at = 2026-11-08T23:11:53.81321+00:00`) → consulta posterior al enlace compartido devolvió `HTTP 403 Forbidden`.
6. **Reinicio #2 de FastAPI (`uvicorn` nuevo PID `18928`) y persistencia de revocación y caducidad (Paso 7 y Prioridad 4)**:
   - Tras el segundo reinicio de FastAPI, `cons-3fd075b6c73e` continuó en estado `REVOCADO` y su enlace compartido siguió bloqueado con `HTTP 403 Forbidden`.
   - Creado consentimiento ficticio vencido `cons-exp-6a0167fe` → al consultarse por enlace compartido devolvió `HTTP 403 Forbidden ("ACCESO EXPIRADO")` y actualizó su estado a `EXPIRADO` en `public.profile_consents`.

### Conteo Final Verificado en Supabase (`list_tables` en `read_only=true`)
- `public.entrepreneurs`: `1` fila (`rls_enabled=True`)
- `public.movements`: `29` filas (`rls_enabled=True`)
- `public.weekly_goals`: `8` filas (`rls_enabled=True`)
- `public.profile_consents`: `2` filas (`rls_enabled=True`)
- `public.chat_messages`: `1` fila (`rls_enabled=True`)
- `public.processed_messages`: `0` filas (`rls_enabled=True`)
- `public.audit_logs`: `4` filas (`rls_enabled=True`)

---

## 3. Compilación Frontend (`npm.cmd run build`)

- `tsc -b && vite build` completado en `2.87s` con `0 errores`.
- Proxy de Vite (`http://127.0.0.1:5173/api/health`) conectado en tiempo real a FastAPI y Supabase (`total_movements = 29`).

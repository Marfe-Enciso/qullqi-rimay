# Auditoría de Seguridad DevSecOps — Qullqi Rimay

**Fecha de ejecución:** 2026-11-08 (Hora de Perú, UTC-5)  
**Directorio auditado:** `D:\demo funcional\Qullqi-Rimay`  
**Herramienta de detección de secretos:** `gitleaks v8.30.1`

---

## 1. Revisión de `.gitignore` y Aislamiento de Secretos

Se verificó que [`.gitignore`](file:///D:/demo%20funcional/Qullqi-Rimay/.gitignore) excluye explícitamente:
- Archivos de variables de entorno: `.env`, `.env.local`, `.env.*.local`, `backend/.env`, `frontend/.env`.
- Entornos virtuales y cachés de Python: `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`.
- Módulos y artefactos de compilación de Node/Vite: `node_modules/`, `dist/`.

 únicamente se incluyen en el control de versiones las plantillas sin credenciales reales:
- [`backend/.env.example`](file:///D:/demo%20funcional/Qullqi-Rimay/backend/.env.example)
- [`frontend/.env.example`](file:///D:/demo%20funcional/Qullqi-Rimay/frontend/.env.example)

---

## 2. Escaneo con Gitleaks (`v8.30.1`)

### 2.1 Escaneo de archivos del directorio (`gitleaks dir`)
Comando ejecutado:
```powershell
gitleaks dir "D:\demo funcional\Qullqi-Rimay" -v
```
Resultado real:
```text
4:22PM INF scanned ~22429567 bytes (22.43 MB) in 1.97s
4:22PM INF no leaks found
```

### 2.2 Escaneo del historial Git (`gitleaks git`)
Ejecutado tras el primer commit en la rama `main`:
- **Secretos expuestos detectados:** `0` (`no leaks found`).

---

## 3. Verificación de Privacidad y Datos Ficticios (PII Check)

- **Usuaria de demostración:** Rosa Quispe Huamán (`rosa-huamanga-001`), personaje 100% ficticio ubicado en el Mercado Nery García Zárate (Huamanga, Ayacucho).
- **Teléfono enmascarado:** `+51 966 *** 418` (sin números telefónicos personales reales).
- **Guardrail ético BCP (`bcp_approval_claim = False`):** El Perfil Financiero incluye obligatoriamente el descargo regulatorio que aclara que el reporte es un historial operativo autodeclarado y confirmado, y **no** constituye una preaprobación ni oferta de crédito del BCP.

---

## 4. Controles de Seguridad del MVP (Fase 4 Implementada en Código)

1. **Tokens de acceso con alta entropía y hash SHA-256:**
   - Generados con `secrets.token_urlsafe(18)` (`qr-tok-...`).
   - Se calcula y almacena `token_sha256` (`hashlib.sha256`) junto con fecha de caducidad (`expires_at` a 7 días).
2. **Revocación inmediata (`POST /api/consents/{id}/revoke`):**
   - Cambia el estado a `REVOCADO` y bloquea cualquier consulta posterior a `GET /api/consents/shared/{token}` con código `HTTP 403 Forbidden`.
3. **Idempotencia y validación criptográfica en Webhook de Twilio (`POST /api/twilio/webhook`):**
   - Validación HMAC-SHA1 de `X-Twilio-Signature` mediante [`verify_twilio_signature`](file:///D:/demo%20funcional/Qullqi-Rimay/backend/app/services/twilio_adapter.py#L26-L44).
   - Deduplicación de `MessageSid` mediante `store.is_message_sid_processed(message_sid)` y tabla `processed_messages` en [`docs/SUPABASE_SCHEMA.sql`](file:///D:/demo%20funcional/Qullqi-Rimay/docs/SUPABASE_SCHEMA.sql).
   - Escape XML seguro con `html.escape` en [`build_twiml_message`](file:///D:/demo%20funcional/Qullqi-Rimay/backend/app/services/twilio_adapter.py#L17-L23).
4. **Cálculo financiero determinístico con `Decimal`:**
   - Tanto el intérprete de multiplicación (`20 kg de naranja a 4` -> `S/ 80.00`) como el motor financiero (`finance_engine.py`) utilizan `decimal.Decimal` con `ROUND_HALF_UP`.
5. **Row Level Security (RLS) en Supabase:**
   - Habilitado en todas las tablas de [`docs/SUPABASE_SCHEMA.sql`](file:///D:/demo%20funcional/Qullqi-Rimay/docs/SUPABASE_SCHEMA.sql#L92-L120).

---

## 5. Identidad Git y Estado del Repositorio

- **Usuario Git configurado localmente:** `angel` (`cuberorock@gmail.com`)
- **Rama principal:** `main`
- **Repositorio remoto conectado:** `https://github.com/Angel1l/Qullqi-Rimay.git`
- **Estado del push:** Publicado y sincronizado (`main -> origin/main`).
- **Visibilidad comprobada:** `PRIVATE` (verificado mediante consulta HTTP sin credenciales a `https://api.github.com/repos/Angel1l/Qullqi-Rimay` -> `HTTP 404 Not Found`, lo que certifica que no es público).


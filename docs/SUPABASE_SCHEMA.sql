-- ============================================================================
-- QULLQI RIMAY - ESQUEMA SUPABASE POSTGRESQL COMPLETO (Fases 3, 4 y 7)
-- Proyecto destino: qullqi-rimay-demo (ref: oqbfuyxoclufkikaddoj)
-- Incluye:
--   - 7 tablas en esquema `public` con integridad referencial.
--   - Row Level Security (RLS) estricto en todas las tablas (cero acceso `anon`).
--   - Aislamiento multi-emprendedora (SELECT, INSERT, UPDATE con USING + WITH CHECK, DELETE)
--     usando `(select auth.uid())::text` (InitPlan optimizado).
--   - Bitácora `audit_logs` inmutable (solo SELECT e INSERT, sin UPDATE ni DELETE).
--   - Índices B-Tree en todas las claves foráneas y hashes de búsqueda.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Emprendedoras y Negocios
CREATE TABLE IF NOT EXISTS public.entrepreneurs (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    business_name TEXT NOT NULL,
    trade_sector TEXT NOT NULL,
    market_location TEXT NOT NULL DEFAULT 'Mercado Nery García Zárate',
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    phone_masked TEXT NOT NULL,
    goal_title TEXT NOT NULL,
    goal_target_pen NUMERIC(12, 2) NOT NULL CHECK (goal_target_pen > 0),
    goal_weekly_target_pen NUMERIC(12, 2) NOT NULL DEFAULT 250.00 CHECK (goal_weekly_target_pen > 0),
    goal_weeks INT NOT NULL DEFAULT 8 CHECK (goal_weeks = 8),
    active_week INT NOT NULL DEFAULT 8 CHECK (active_week BETWEEN 1 AND 8),
    owner_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entrepreneurs_owner_user_id
    ON public.entrepreneurs(owner_user_id);

-- 2. Movimientos Financieros y Confirmaciones Pendientes
CREATE TABLE IF NOT EXISTS public.movements (
    id TEXT PRIMARY KEY,
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE,
    week_number INT NOT NULL CHECK (week_number BETWEEN 1 AND 8),
    movement_type TEXT NOT NULL CHECK (movement_type IN ('VENTA', 'GASTO')),
    amount_pen NUMERIC(12, 2) NOT NULL CHECK (amount_pen > 0),
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    raw_message TEXT NOT NULL,
    source_channel TEXT NOT NULL DEFAULT 'WHATSAPP_SIMULATOR',
    ai_confidence NUMERIC(4, 3) NOT NULL DEFAULT 1.000,
    status TEXT NOT NULL CHECK (status IN ('PENDIENTE', 'CONFIRMADO', 'DESCARTADO')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_movements_entrepreneur_week
    ON public.movements(entrepreneur_id, week_number, status);

-- 3. Metas y Semanas Registradas (Instantáneas Semanales)
CREATE TABLE IF NOT EXISTS public.weekly_goals (
    id TEXT PRIMARY KEY,
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE,
    week_number INT NOT NULL CHECK (week_number BETWEEN 1 AND 8),
    week_label TEXT NOT NULL,
    weekly_target_pen NUMERIC(12, 2) NOT NULL,
    total_sales_pen NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_expenses_pen NUMERIC(12, 2) NOT NULL DEFAULT 0,
    net_margin_pen NUMERIC(12, 2) NOT NULL DEFAULT 0,
    status_badge TEXT NOT NULL CHECK (status_badge IN ('COMPLETADA', 'EN_CURSO', 'PENDIENTE')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entrepreneur_id, week_number)
);

CREATE INDEX IF NOT EXISTS idx_weekly_goals_entrepreneur
    ON public.weekly_goals(entrepreneur_id);

-- 4. Consentimientos y Enlaces Compartidos (Con Hash SHA-256 de Token y Caducidad)
CREATE TABLE IF NOT EXISTS public.profile_consents (
    id TEXT PRIMARY KEY,
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE,
    recipient_entity TEXT NOT NULL,
    purpose TEXT NOT NULL,
    consent_statement TEXT NOT NULL,
    share_token TEXT NOT NULL UNIQUE,
    token_sha256 TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVO', 'REVOCADO', 'EXPIRADO')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    revoked_at TIMESTAMPTZ,
    revocation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_consents_entrepreneur
    ON public.profile_consents(entrepreneur_id);
CREATE INDEX IF NOT EXISTS idx_consents_token_sha256
    ON public.profile_consents(token_sha256);

-- 5. Historial de Mensajes del Simulador / WhatsApp
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id TEXT PRIMARY KEY,
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK (sender IN ('ROSA', 'QULLQI_BOT')),
    text TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    week_number INT NOT NULL DEFAULT 8 CHECK (week_number BETWEEN 1 AND 8),
    structured_json JSONB,
    pending_movement_ids JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_entrepreneur_ts
    ON public.chat_messages(entrepreneur_id, timestamp);

-- 6. Identificadores de Mensajes Procesados (Idempotencia Twilio MessageSid - Fase 7)
CREATE TABLE IF NOT EXISTS public.processed_messages (
    message_sid TEXT PRIMARY KEY,
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE,
    sender_phone_hash TEXT NOT NULL,
    raw_body TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_messages_entrepreneur
    ON public.processed_messages(entrepreneur_id);

-- 7. Historial de Modificaciones y Auditoría Inmutable (Fases 3 y 4)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entrepreneur
    ON public.audit_logs(entrepreneur_id, created_at DESC);

-- ============================================================================
-- SEGURIDAD ROW LEVEL SECURITY (RLS) Y AISLAMIENTO ENTRE EMPRENDEDORAS
-- Ninguna tabla expone acceso al rol `anon`.
-- Cada política verifica `(select auth.uid())::text` tanto en USING como en WITH CHECK
-- para impedir lectura o reasignación cruzada (BOLA / IDOR) entre emprendedoras.
-- ============================================================================
ALTER TABLE public.entrepreneurs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weekly_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profile_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processed_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Función auxiliar SECURITY INVOKER para verificar titularidad real por owner_user_id
CREATE OR REPLACE FUNCTION public.is_entrepreneur_owner(target_entrepreneur_id TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.entrepreneurs e
        WHERE e.id = target_entrepreneur_id
          AND e.owner_user_id IS NOT NULL
          AND e.owner_user_id = (SELECT auth.uid())
    );
$$;

-- 1. Políticas para public.entrepreneurs
DROP POLICY IF EXISTS "entrepreneurs_select_own" ON public.entrepreneurs;
CREATE POLICY "entrepreneurs_select_own"
    ON public.entrepreneurs FOR SELECT TO authenticated
    USING (owner_user_id IS NOT NULL AND owner_user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "entrepreneurs_insert_own" ON public.entrepreneurs;
CREATE POLICY "entrepreneurs_insert_own"
    ON public.entrepreneurs FOR INSERT TO authenticated
    WITH CHECK (owner_user_id IS NOT NULL AND owner_user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "entrepreneurs_update_own" ON public.entrepreneurs;
CREATE POLICY "entrepreneurs_update_own"
    ON public.entrepreneurs FOR UPDATE TO authenticated
    USING (owner_user_id IS NOT NULL AND owner_user_id = (SELECT auth.uid()))
    WITH CHECK (owner_user_id IS NOT NULL AND owner_user_id = (SELECT auth.uid()));

-- 2. Políticas para public.movements
DROP POLICY IF EXISTS "movements_select_own" ON public.movements;
CREATE POLICY "movements_select_own"
    ON public.movements FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "movements_insert_own" ON public.movements;
CREATE POLICY "movements_insert_own"
    ON public.movements FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "movements_update_own" ON public.movements;
CREATE POLICY "movements_update_own"
    ON public.movements FOR UPDATE TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id))
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "movements_delete_own" ON public.movements;
CREATE POLICY "movements_delete_own"
    ON public.movements FOR DELETE TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

-- 3. Políticas para public.weekly_goals
DROP POLICY IF EXISTS "weekly_goals_select_own" ON public.weekly_goals;
CREATE POLICY "weekly_goals_select_own"
    ON public.weekly_goals FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "weekly_goals_insert_own" ON public.weekly_goals;
CREATE POLICY "weekly_goals_insert_own"
    ON public.weekly_goals FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "weekly_goals_update_own" ON public.weekly_goals;
CREATE POLICY "weekly_goals_update_own"
    ON public.weekly_goals FOR UPDATE TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id))
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- 4. Políticas para public.profile_consents
DROP POLICY IF EXISTS "profile_consents_select_own" ON public.profile_consents;
CREATE POLICY "profile_consents_select_own"
    ON public.profile_consents FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "profile_consents_insert_own" ON public.profile_consents;
CREATE POLICY "profile_consents_insert_own"
    ON public.profile_consents FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "profile_consents_update_own" ON public.profile_consents;
CREATE POLICY "profile_consents_update_own"
    ON public.profile_consents FOR UPDATE TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id))
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- 5. Políticas para public.chat_messages
DROP POLICY IF EXISTS "chat_messages_select_own" ON public.chat_messages;
CREATE POLICY "chat_messages_select_own"
    ON public.chat_messages FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "chat_messages_insert_own" ON public.chat_messages;
CREATE POLICY "chat_messages_insert_own"
    ON public.chat_messages FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- 6. Políticas para public.processed_messages
DROP POLICY IF EXISTS "processed_messages_select_own" ON public.processed_messages;
CREATE POLICY "processed_messages_select_own"
    ON public.processed_messages FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "processed_messages_insert_own" ON public.processed_messages;
CREATE POLICY "processed_messages_insert_own"
    ON public.processed_messages FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- 7. Políticas para public.audit_logs (Inmutable: solo lectura e inserción de la propia titular)
DROP POLICY IF EXISTS "audit_logs_select_own" ON public.audit_logs;
CREATE POLICY "audit_logs_select_own"
    ON public.audit_logs FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "audit_logs_insert_own" ON public.audit_logs;
CREATE POLICY "audit_logs_insert_own"
    ON public.audit_logs FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

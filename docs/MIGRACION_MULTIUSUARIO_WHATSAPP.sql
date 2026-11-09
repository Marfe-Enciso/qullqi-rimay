-- =============================================================================
-- QULLQI RIMAY — MIGRACIÓN INCREMENTAL NO DESTRUCTIVA: MULTIUSUARIO + WHATSAPP
-- Archivo: docs/MIGRACION_MULTIUSUARIO_WHATSAPP.sql
-- Proyecto Supabase: qullqi-rimay-demo (oqbfuyxoclufkikaddoj)
-- Estado: PREPARADA PARA REVISIÓN Y AUTORIZACIÓN DEL USUARIO (NO EJECUTADA)
-- =============================================================================
-- GARANTÍAS DE NO DESTRUCCIÓN Y SEGURIDAD:
-- 1. CERO sentencias DROP TABLE, TRUNCATE o DELETE sobre datos existentes.
-- 2. Conserva intactos el perfil ficticio 'rosa-huamanga-001', sus 29 movimientos,
--    8 metas semanales, 2 consentimientos, mensajes de chat y logs de auditoría.
-- 3. No presupone ni altera el consentimiento de Rosa ('rosa-huamanga-001'),
--    y exige consentimiento expreso (fecha + versión) para toda cuenta real
--    con owner_user_id IS NOT NULL.
-- 4. Elimina todas las políticas RLS previas antes de recrear el conjunto
--    canónico único para impedir permisos acumulativos involuntarios (OR).
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. COLUMNAS Y RESTRICCIONES EN public.entrepreneurs (TITULARIDAD Y CONSENTIMIENTO)
-- =============================================================================
ALTER TABLE public.entrepreneurs
    ADD COLUMN IF NOT EXISTS owner_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS preferred_language TEXT NOT NULL DEFAULT 'es'
        CHECK (preferred_language IN ('es', 'qu')),
    ADD COLUMN IF NOT EXISTS data_consent_accepted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS data_consent_accepted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS data_consent_version TEXT,
    ADD COLUMN IF NOT EXISTS whatsapp_linked BOOLEAN NOT NULL DEFAULT FALSE;

-- Asegurar que el valor por defecto sea FALSE para no presuponer consentimiento automático
ALTER TABLE public.entrepreneurs
    ALTER COLUMN data_consent_accepted SET DEFAULT FALSE;

-- 1.2 Comprobación estricta de salvaguarda: interrumpe la transacción si Rosa presenta titularidad inesperada
DO $$
DECLARE
    v_rosa_owner UUID;
BEGIN
    SELECT owner_user_id INTO v_rosa_owner
    FROM public.entrepreneurs
    WHERE id = 'rosa-huamanga-001';

    IF v_rosa_owner IS NOT NULL THEN
        RAISE EXCEPTION 'Abortando migración: el perfil ficticio rosa-huamanga-001 presenta titularidad inesperada (%)', v_rosa_owner;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'entrepreneurs_fictional_rosa_never_owned_chk'
    ) THEN
        ALTER TABLE public.entrepreneurs
            ADD CONSTRAINT entrepreneurs_fictional_rosa_never_owned_chk
            CHECK (id <> 'rosa-huamanga-001' OR owner_user_id IS NULL);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'entrepreneurs_real_owner_requires_consent_chk'
    ) THEN
        ALTER TABLE public.entrepreneurs
            ADD CONSTRAINT entrepreneurs_real_owner_requires_consent_chk
            CHECK (
                owner_user_id IS NULL
                OR (
                    data_consent_accepted IS TRUE
                    AND data_consent_accepted_at IS NOT NULL
                    AND data_consent_version IS NOT NULL
                )
            );
    END IF;
END $$;

-- Protección contra duplicados: 1 usuario de Supabase Auth -> máximo 1 perfil de emprendedora
CREATE UNIQUE INDEX IF NOT EXISTS idx_entrepreneurs_owner_user_id_unique
    ON public.entrepreneurs(owner_user_id)
    WHERE owner_user_id IS NOT NULL;


-- =============================================================================
-- 2. IDEMPOTENCIA DE TWILIO EN TELÉFONOS NO VINCULADOS (public.processed_messages)
-- =============================================================================
-- Permite registrar MessageSid durante el onboarding provisional con entrepreneur_id = NULL,
-- eliminando cualquier referencia alternativa a 'rosa-huamanga-001'.
ALTER TABLE public.processed_messages
    ALTER COLUMN entrepreneur_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_processed_messages_phone_hash
    ON public.processed_messages(sender_phone_hash);


-- =============================================================================
-- 3. TABLA DE VINCULACIÓN DE WHATSAPP (public.whatsapp_links)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.whatsapp_links (
    phone_sha256 TEXT PRIMARY KEY CHECK (char_length(phone_sha256) = 64),
    entrepreneur_id TEXT NOT NULL REFERENCES public.entrepreneurs(id) ON DELETE CASCADE
        CHECK (entrepreneur_id <> 'rosa-huamanga-001'),
    phone_masked TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Protección atómica contra duplicados: cada emprendedora tiene un único vínculo activo
CREATE UNIQUE INDEX IF NOT EXISTS idx_whatsapp_links_entrepreneur_unique
    ON public.whatsapp_links(entrepreneur_id);


-- =============================================================================
-- 4. TABLA DE REGISTRO CONVERSACIONAL EN WHATSAPP (public.whatsapp_onboarding_sessions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.whatsapp_onboarding_sessions (
    phone_sha256 TEXT PRIMARY KEY CHECK (char_length(phone_sha256) = 64),
    phone_masked TEXT NOT NULL,
    step TEXT NOT NULL DEFAULT 'AWAITING_LANGUAGE'
        CHECK (step IN (
            'AWAITING_LANGUAGE',
            'AWAITING_NAME_BUSINESS',
            'AWAITING_CONSENT',
            'READY_TO_LINK',
            'LINKED'
        )),
    preferred_language TEXT NOT NULL DEFAULT 'es'
        CHECK (preferred_language IN ('es', 'qu')),
    full_name TEXT,
    business_name TEXT,
    city TEXT NOT NULL DEFAULT 'Huamanga',
    consent_accepted BOOLEAN NOT NULL DEFAULT FALSE,
    consent_accepted_at TIMESTAMPTZ,
    consent_version TEXT,
    provisional_entrepreneur_id TEXT,
    claim_code_sha256 TEXT CHECK (claim_code_sha256 IS NULL OR char_length(claim_code_sha256) = 64),
    claim_expires_at TIMESTAMPTZ,
    last_message_sid TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT whatsapp_onboarding_consent_metadata_chk CHECK (
        consent_accepted IS FALSE
        OR (consent_accepted_at IS NOT NULL AND consent_version IS NOT NULL)
    )
);


-- =============================================================================
-- 5. TABLA DE CÓDIGOS DE UN SOLO USO Y EXPIRACIÓN (public.whatsapp_link_challenges)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.whatsapp_link_challenges (
    code_sha256 TEXT PRIMARY KEY CHECK (char_length(code_sha256) = 64),
    entrepreneur_id TEXT NOT NULL CHECK (entrepreneur_id <> 'rosa-huamanga-001'),
    phone_sha256 TEXT CHECK (phone_sha256 IS NULL OR char_length(phone_sha256) = 64),
    phone_masked TEXT,
    challenge_type TEXT NOT NULL CHECK (challenge_type IN ('WEB_TO_WA', 'WA_PROVISIONAL')),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    used_at TIMESTAMPTZ,
    attempts SMALLINT NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_link_challenges_expires_at
    ON public.whatsapp_link_challenges(expires_at)
    WHERE used = FALSE;


-- =============================================================================
-- 6. REVISIÓN Y CONSOLIDACIÓN DE POLÍTICAS RLS (CERO PERMISOS ACUMULATIVOS)
-- =============================================================================
ALTER TABLE public.entrepreneurs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weekly_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profile_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processed_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_onboarding_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.whatsapp_link_challenges ENABLE ROW LEVEL SECURITY;

-- Función auxiliar SECURITY INVOKER para verificar titularidad real por owner_user_id
-- Impide explícitamente que 'rosa-huamanga-001' sea reclamada por ningún usuario autenticado.
CREATE OR REPLACE FUNCTION public.is_entrepreneur_owner(target_entrepreneur_id TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.entrepreneurs e
        WHERE e.id = target_entrepreneur_id
          AND e.id <> 'rosa-huamanga-001'
          AND e.owner_user_id IS NOT NULL
          AND e.owner_user_id = (SELECT auth.uid())
    );
$$;

REVOKE ALL ON FUNCTION public.is_entrepreneur_owner(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_entrepreneur_owner(TEXT) TO authenticated, service_role;

-- 6.1 Limpieza exhaustiva de políticas previas (esquema inicial + borradores previos)
-- public.entrepreneurs
DROP POLICY IF EXISTS "entrepreneurs_select_own" ON public.entrepreneurs;
DROP POLICY IF EXISTS "entrepreneurs_insert_own" ON public.entrepreneurs;
DROP POLICY IF EXISTS "entrepreneurs_update_own" ON public.entrepreneurs;
DROP POLICY IF EXISTS "entrepreneurs_delete_own" ON public.entrepreneurs;
DROP POLICY IF EXISTS entrepreneurs_owner_select ON public.entrepreneurs;
DROP POLICY IF EXISTS entrepreneurs_owner_insert ON public.entrepreneurs;
DROP POLICY IF EXISTS entrepreneurs_owner_update ON public.entrepreneurs;

-- public.movements
DROP POLICY IF EXISTS "movements_select_own" ON public.movements;
DROP POLICY IF EXISTS "movements_insert_own" ON public.movements;
DROP POLICY IF EXISTS "movements_update_own" ON public.movements;
DROP POLICY IF EXISTS "movements_delete_own" ON public.movements;
DROP POLICY IF EXISTS movements_owner_select ON public.movements;
DROP POLICY IF EXISTS movements_owner_insert ON public.movements;
DROP POLICY IF EXISTS movements_owner_update ON public.movements;

-- public.weekly_goals
DROP POLICY IF EXISTS "weekly_goals_select_own" ON public.weekly_goals;
DROP POLICY IF EXISTS "weekly_goals_insert_own" ON public.weekly_goals;
DROP POLICY IF EXISTS "weekly_goals_update_own" ON public.weekly_goals;
DROP POLICY IF EXISTS "weekly_goals_delete_own" ON public.weekly_goals;
DROP POLICY IF EXISTS weekly_goals_owner_select ON public.weekly_goals;

-- public.profile_consents
DROP POLICY IF EXISTS "profile_consents_select_own" ON public.profile_consents;
DROP POLICY IF EXISTS "profile_consents_insert_own" ON public.profile_consents;
DROP POLICY IF EXISTS "profile_consents_update_own" ON public.profile_consents;
DROP POLICY IF EXISTS "profile_consents_delete_own" ON public.profile_consents;
DROP POLICY IF EXISTS profile_consents_owner_select ON public.profile_consents;

-- public.chat_messages
DROP POLICY IF EXISTS "chat_messages_select_own" ON public.chat_messages;
DROP POLICY IF EXISTS "chat_messages_insert_own" ON public.chat_messages;
DROP POLICY IF EXISTS "chat_messages_update_own" ON public.chat_messages;
DROP POLICY IF EXISTS "chat_messages_delete_own" ON public.chat_messages;
DROP POLICY IF EXISTS chat_messages_owner_select ON public.chat_messages;

-- public.processed_messages (solo service_role del backend; sin acceso para authenticated/anon)
DROP POLICY IF EXISTS "processed_messages_select_own" ON public.processed_messages;
DROP POLICY IF EXISTS "processed_messages_insert_own" ON public.processed_messages;
DROP POLICY IF EXISTS "processed_messages_update_own" ON public.processed_messages;
DROP POLICY IF EXISTS "processed_messages_delete_own" ON public.processed_messages;

-- public.audit_logs
DROP POLICY IF EXISTS "audit_logs_select_own" ON public.audit_logs;
DROP POLICY IF EXISTS "audit_logs_insert_own" ON public.audit_logs;
DROP POLICY IF EXISTS "audit_logs_update_own" ON public.audit_logs;
DROP POLICY IF EXISTS "audit_logs_delete_own" ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_owner_select ON public.audit_logs;

-- public.whatsapp_links, whatsapp_onboarding_sessions, whatsapp_link_challenges
DROP POLICY IF EXISTS "whatsapp_links_select_own" ON public.whatsapp_links;
DROP POLICY IF EXISTS whatsapp_links_owner_select ON public.whatsapp_links;


-- 6.2 Creación del conjunto único y no acumulativo de políticas RLS por tabla

-- A) public.entrepreneurs: lectura y actualización solo de la propia titular verificada (y nunca Rosa)
CREATE POLICY "entrepreneurs_select_own"
    ON public.entrepreneurs FOR SELECT TO authenticated
    USING (
        id <> 'rosa-huamanga-001'
        AND owner_user_id IS NOT NULL
        AND owner_user_id = (SELECT auth.uid())
    );

CREATE POLICY "entrepreneurs_update_own"
    ON public.entrepreneurs FOR UPDATE TO authenticated
    USING (
        id <> 'rosa-huamanga-001'
        AND owner_user_id IS NOT NULL
        AND owner_user_id = (SELECT auth.uid())
    )
    WITH CHECK (
        id <> 'rosa-huamanga-001'
        AND owner_user_id IS NOT NULL
        AND owner_user_id = (SELECT auth.uid())
        AND data_consent_accepted IS TRUE
        AND data_consent_accepted_at IS NOT NULL
        AND data_consent_version IS NOT NULL
    );

-- B) public.movements
CREATE POLICY "movements_select_own"
    ON public.movements FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

CREATE POLICY "movements_insert_own"
    ON public.movements FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

CREATE POLICY "movements_update_own"
    ON public.movements FOR UPDATE TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id))
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- C) public.weekly_goals
CREATE POLICY "weekly_goals_select_own"
    ON public.weekly_goals FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

-- D) public.profile_consents
CREATE POLICY "profile_consents_select_own"
    ON public.profile_consents FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

CREATE POLICY "profile_consents_insert_own"
    ON public.profile_consents FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

CREATE POLICY "profile_consents_update_own"
    ON public.profile_consents FOR UPDATE TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id))
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- E) public.chat_messages
CREATE POLICY "chat_messages_select_own"
    ON public.chat_messages FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

CREATE POLICY "chat_messages_insert_own"
    ON public.chat_messages FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- F) public.audit_logs (inmutable: solo lectura de su propia bitácora)
CREATE POLICY "audit_logs_select_own"
    ON public.audit_logs FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

-- G) public.whatsapp_links (solo lectura del vínculo propio)
CREATE POLICY "whatsapp_links_select_own"
    ON public.whatsapp_links FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

-- Nota: public.processed_messages, public.whatsapp_onboarding_sessions y
-- public.whatsapp_link_challenges quedan con RLS activo y CERO políticas para
-- anon/authenticated; solo el backend (service_role) opera sobre ellas.

COMMIT;

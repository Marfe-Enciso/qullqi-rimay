-- ============================================================================
-- MIGRACIÓN INCREMENTAL NO DESTRUCTIVA (PREPARADA PARA REVISIÓN — NO EJECUTAR SIN AUTORIZACIÓN)
-- Archivo: docs/migrations/20261108_02_incremental_ownership_and_rls.sql
-- Objetivos de Seguridad (Prioridad 2):
--   1. Vincular explícitamente `auth.users.id` (UUID) con `public.entrepreneurs.owner_user_id`
--      (`UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL`).
--   2. Evitar recursión RLS:
--      - `public.entrepreneurs` evalúa `owner_user_id IS NOT NULL AND owner_user_id = (SELECT auth.uid())`
--        directamente sobre la fila sin invocar subconsultas circulares.
--      - Las tablas hijas (`movements`, `weekly_goals`, `profile_consents`, `chat_messages`,
--        `processed_messages`, `audit_logs`) verifican la titularidad mediante
--        `public.is_entrepreneur_owner(entrepreneur_id)`.
--   3. Mínimo privilegio en funciones SQL:
--      - `SECURITY INVOKER`, `STABLE`, `SET search_path = ''`.
--      - `REVOKE ALL ON FUNCTION ... FROM PUBLIC, anon` y `GRANT EXECUTE ... TO authenticated, service_role`.
--   4. Impedir asignaciones o transferencias de titularidad no verificadas:
--      - Trigger `trg_prevent_ownership_reassign` bloquea cualquier intento de cambiar `id` o
--        `owner_user_id` desde sesiones no administrativas.
-- ============================================================================

-- 1. Columna de titularidad real vinculada a Supabase Auth (`auth.users`)
ALTER TABLE public.entrepreneurs
    ADD COLUMN IF NOT EXISTS owner_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_entrepreneurs_owner_user_id
    ON public.entrepreneurs(owner_user_id);

-- 2. Trigger para impedir reasignación de titularidad (owner_user_id) o cambio de ID
CREATE OR REPLACE FUNCTION public.enforce_entrepreneur_ownership_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
    jwt_role TEXT := COALESCE(
        current_setting('request.jwt.claims', true)::jsonb ->> 'role',
        current_user
    );
BEGIN
    IF OLD.id IS DISTINCT FROM NEW.id THEN
        RAISE EXCEPTION 'No se permite modificar el identificador primario de la emprendedora.';
    END IF;

    IF OLD.owner_user_id IS NOT NULL
       AND OLD.owner_user_id IS DISTINCT FROM NEW.owner_user_id
       AND jwt_role NOT IN ('service_role', 'postgres', 'supabase_admin') THEN
        RAISE EXCEPTION 'No se permite transferir ni sobrescribir owner_user_id sin autorización administrativa.';
    END IF;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.enforce_entrepreneur_ownership_immutability() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.enforce_entrepreneur_ownership_immutability() TO authenticated, service_role;

DROP TRIGGER IF EXISTS trg_prevent_ownership_reassign ON public.entrepreneurs;
CREATE TRIGGER trg_prevent_ownership_reassign
    BEFORE UPDATE ON public.entrepreneurs
    FOR EACH ROW
    EXECUTE FUNCTION public.enforce_entrepreneur_ownership_immutability();

-- 3. Función auxiliar SECURITY INVOKER sin recursión y con permisos mínimos
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
          AND e.owner_user_id IS NOT NULL
          AND e.owner_user_id = (SELECT auth.uid())
    );
$$;

REVOKE ALL ON FUNCTION public.is_entrepreneur_owner(TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_entrepreneur_owner(TEXT) TO authenticated, service_role;

-- 4. Políticas RLS en `public.entrepreneurs` (evaluación directa sin recursión)
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

-- 5. Políticas RLS en `public.movements`
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

-- 6. Políticas RLS en `public.weekly_goals`
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

-- 7. Políticas RLS en `public.profile_consents`
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

-- 8. Políticas RLS en `public.chat_messages`
DROP POLICY IF EXISTS "chat_messages_select_own" ON public.chat_messages;
CREATE POLICY "chat_messages_select_own"
    ON public.chat_messages FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "chat_messages_insert_own" ON public.chat_messages;
CREATE POLICY "chat_messages_insert_own"
    ON public.chat_messages FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- 9. Políticas RLS en `public.processed_messages`
DROP POLICY IF EXISTS "processed_messages_select_own" ON public.processed_messages;
CREATE POLICY "processed_messages_select_own"
    ON public.processed_messages FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "processed_messages_insert_own" ON public.processed_messages;
CREATE POLICY "processed_messages_insert_own"
    ON public.processed_messages FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

-- 10. Políticas RLS en `public.audit_logs` (Inmutable: solo SELECT e INSERT de la propia titular)
DROP POLICY IF EXISTS "audit_logs_select_own" ON public.audit_logs;
CREATE POLICY "audit_logs_select_own"
    ON public.audit_logs FOR SELECT TO authenticated
    USING (public.is_entrepreneur_owner(entrepreneur_id));

DROP POLICY IF EXISTS "audit_logs_insert_own" ON public.audit_logs;
CREATE POLICY "audit_logs_insert_own"
    ON public.audit_logs FOR INSERT TO authenticated
    WITH CHECK (public.is_entrepreneur_owner(entrepreneur_id));

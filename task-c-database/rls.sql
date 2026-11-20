-- ============================================================================
-- Row Level Security (RLS) Policies for Multi-Tenant Isolation
-- (Designed for Supabase / PostgreSQL)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Enable RLS on all Tenant-Scoped Tables
-- ----------------------------------------------------------------------------
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners / service roles (prevent accidental bypass)
ALTER TABLE companies FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2. Helper Security Functions (SECURITY DEFINER with safe search_path)
-- ----------------------------------------------------------------------------

-- 2.1 Get application profile UUID (public.users.id) from Supabase Auth UID
CREATE OR REPLACE FUNCTION public.get_current_user_profile_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT id
    FROM public.users
    WHERE auth_user_id = auth.uid()
    LIMIT 1;
$$;

-- 2.2 Get tenant company UUID from Supabase Auth UID
CREATE OR REPLACE FUNCTION public.get_current_user_company_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT company_id
    FROM public.users
    WHERE auth_user_id = auth.uid()
    LIMIT 1;
$$;

-- 2.3 Get user role ('manager' | 'employee') from Supabase Auth UID
CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS public.user_role
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT role
    FROM public.users
    WHERE auth_user_id = auth.uid()
    LIMIT 1;
$$;

-- 2.4 Boolean check: is current user a Manager in their company?
CREATE OR REPLACE FUNCTION public.is_company_manager()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.users
        WHERE auth_user_id = auth.uid()
          AND role = 'manager'::public.user_role
    );
$$;

-- Function Execution Privileges
REVOKE EXECUTE ON FUNCTION public.get_current_user_profile_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_current_user_profile_id() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.get_current_user_company_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_current_user_company_id() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.get_current_user_role() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_current_user_role() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.is_company_manager() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_company_manager() TO authenticated;

-- ----------------------------------------------------------------------------
-- 3. RLS Policies: Companies Table
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS companies_select_policy ON public.companies;
DROP POLICY IF EXISTS companies_update_policy ON public.companies;

CREATE POLICY companies_select_policy ON public.companies
    FOR SELECT
    TO authenticated
    USING (
        id = public.get_current_user_company_id()
    );

-- ----------------------------------------------------------------------------
-- 4. RLS Policies: Users Table
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS users_select_policy ON public.users;
DROP POLICY IF EXISTS users_insert_policy ON public.users;
DROP POLICY IF EXISTS users_update_policy ON public.users;

CREATE POLICY users_select_policy ON public.users
    FOR SELECT
    TO authenticated
    USING (
        company_id = public.get_current_user_company_id()
    );

-- ----------------------------------------------------------------------------
-- 5. RLS Policies: Tasks Table
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS tasks_select_policy ON public.tasks;
DROP POLICY IF EXISTS tasks_insert_policy ON public.tasks;
DROP POLICY IF EXISTS tasks_update_policy ON public.tasks;
DROP POLICY IF EXISTS tasks_delete_policy ON public.tasks;

-- SELECT Policy:
-- - Managers see ALL tasks belonging to their company.
-- - Employees see ONLY tasks assigned to their application profile ID.
CREATE POLICY tasks_select_policy ON public.tasks
    FOR SELECT
    TO authenticated
    USING (
        company_id = public.get_current_user_company_id()
        AND (
            public.is_company_manager()
            OR assigned_to = public.get_current_user_profile_id()
        )
    );

-- INSERT Policy:
-- - Only Managers can create tasks.
-- - Must be created within manager's verified company.
-- - created_by must match manager's application profile ID.
CREATE POLICY tasks_insert_policy ON public.tasks
    FOR INSERT
    TO authenticated
    WITH CHECK (
        company_id = public.get_current_user_company_id()
        AND public.is_company_manager()
        AND created_by = public.get_current_user_profile_id()
    );

-- UPDATE Policy:
-- - Managers can update any task within their company.
-- - Employees can update ONLY their own assigned tasks.
-- - USING and WITH CHECK both enforce company and assignee/manager constraints.
CREATE POLICY tasks_update_policy ON public.tasks
    FOR UPDATE
    TO authenticated
    USING (
        company_id = public.get_current_user_company_id()
        AND (
            public.is_company_manager()
            OR assigned_to = public.get_current_user_profile_id()
        )
    )
    WITH CHECK (
        company_id = public.get_current_user_company_id()
        AND (
            public.is_company_manager()
            OR assigned_to = public.get_current_user_profile_id()
        )
    );

-- ----------------------------------------------------------------------------
-- 6. Privileges & Grants (Explicit Column-Level Protection)
-- ----------------------------------------------------------------------------
REVOKE ALL PRIVILEGES ON TABLE public.companies FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.users FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.tasks FROM anon, authenticated;

GRANT SELECT ON TABLE public.companies TO authenticated;
GRANT SELECT ON TABLE public.users TO authenticated;
GRANT SELECT, INSERT ON TABLE public.tasks TO authenticated;
GRANT UPDATE (status, updated_at) ON TABLE public.tasks TO authenticated;

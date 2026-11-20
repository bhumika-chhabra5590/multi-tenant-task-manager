-- ============================================================================
-- Migration: 002_supabase_auth_integration.sql
-- Purpose: Add Supabase Auth mapping, configure strict column-level privileges,
--          and enforce Row Level Security (RLS) policies.
-- Safe & Additive: DOES NOT DROP companies, users, or tasks. Preserves all seed rows.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Add auth_user_id mapping column to public.users
-- ----------------------------------------------------------------------------
-- The application uses public.users.id (UUID) as the internal profile ID (referenced
-- by tasks.created_by and tasks.assigned_to).
-- The auth_user_id maps each public profile to a real Supabase Auth user (auth.users.id / auth.uid()).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'auth_user_id'
    ) THEN
        ALTER TABLE public.users
            ADD COLUMN auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL;
        
        COMMENT ON COLUMN public.users.auth_user_id IS
            'Links application profile to Supabase Auth UUID (auth.users.id / auth.uid()).';
    END IF;
END $$;

-- Index to optimize RLS security helper lookups
CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON public.users(auth_user_id);

-- ----------------------------------------------------------------------------
-- 2. Secure Identity Helper Functions (SECURITY DEFINER with safe search_path)
-- ----------------------------------------------------------------------------
-- Why SECURITY DEFINER is needed:
-- During RLS evaluation on public.tasks or public.companies, the database must
-- inspect public.users to find the caller's company_id and role.
-- Using SECURITY DEFINER allows the helper function to query public.users with
-- internal privileges without triggering recursive RLS evaluation loops.
-- A fixed search_path = '' prevents search-path hijacking attacks. All table references
-- are schema-qualified (public.users).

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

-- Helper Function Execution Privileges
REVOKE EXECUTE ON FUNCTION public.get_current_user_profile_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_current_user_profile_id() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.get_current_user_company_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_current_user_company_id() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.get_current_user_role() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_current_user_role() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.is_company_manager() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_company_manager() TO authenticated;

-- ----------------------------------------------------------------------------
-- 3. Review & Fix Foreign Key Constraints
-- ----------------------------------------------------------------------------
-- In Postgres, composite foreign key (company_id, assigned_to) with ON DELETE SET NULL
-- would attempt to set all referenced columns to NULL, failing because company_id is NOT NULL.
-- We ensure the constraint uses ON DELETE RESTRICT on the composite key.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema = 'public'
          AND table_name = 'tasks'
          AND constraint_name = 'fk_tasks_assigned_to_company_user'
    ) THEN
        ALTER TABLE public.tasks DROP CONSTRAINT fk_tasks_assigned_to_company_user;
    END IF;

    ALTER TABLE public.tasks
        ADD CONSTRAINT fk_tasks_assigned_to_company_user
        FOREIGN KEY (company_id, assigned_to)
        REFERENCES public.users(company_id, id)
        ON DELETE RESTRICT;
END $$;

-- ----------------------------------------------------------------------------
-- 4. Clean Up Obsolete RLS Policies
-- ----------------------------------------------------------------------------
-- Drop unnecessary update/insert policies on companies and users since the
-- application API does not expose company or user modification endpoints.
DROP POLICY IF EXISTS companies_update_policy ON public.companies;
DROP POLICY IF EXISTS users_insert_policy ON public.users;
DROP POLICY IF EXISTS users_update_policy ON public.users;
DROP POLICY IF EXISTS tasks_delete_policy ON public.tasks;

-- ----------------------------------------------------------------------------
-- 5. Upgrade Row Level Security (RLS) Policies
-- ----------------------------------------------------------------------------
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.companies FORCE ROW LEVEL SECURITY;
ALTER TABLE public.users FORCE ROW LEVEL SECURITY;
ALTER TABLE public.tasks FORCE ROW LEVEL SECURITY;

-- 5.1 Companies Table Policies
DROP POLICY IF EXISTS companies_select_policy ON public.companies;
CREATE POLICY companies_select_policy ON public.companies
    FOR SELECT
    TO authenticated
    USING (
        id = public.get_current_user_company_id()
    );

-- 5.2 Users Table Policies
DROP POLICY IF EXISTS users_select_policy ON public.users;
CREATE POLICY users_select_policy ON public.users
    FOR SELECT
    TO authenticated
    USING (
        company_id = public.get_current_user_company_id()
    );

-- 5.3 Tasks Table Policies
DROP POLICY IF EXISTS tasks_select_policy ON public.tasks;
DROP POLICY IF EXISTS tasks_insert_policy ON public.tasks;
DROP POLICY IF EXISTS tasks_update_policy ON public.tasks;

-- SELECT POLICY:
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

-- INSERT POLICY:
-- - Only Managers can create tasks.
-- - company_id must match manager's database-derived company.
-- - created_by must match manager's application profile ID.
CREATE POLICY tasks_insert_policy ON public.tasks
    FOR INSERT
    TO authenticated
    WITH CHECK (
        company_id = public.get_current_user_company_id()
        AND public.is_company_manager()
        AND created_by = public.get_current_user_profile_id()
    );

-- UPDATE POLICY:
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
-- 6. Privileges and Column-Level Permissions (CRITICAL SECURITY FIX)
-- ----------------------------------------------------------------------------
-- Explicitly revoke ALL table-level permissions from anon and authenticated first.
-- A table-level UPDATE grant overrides column-level restrictions in PostgreSQL.
REVOKE ALL PRIVILEGES ON TABLE public.companies FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.users FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.tasks FROM anon, authenticated;

-- Companies: SELECT only for authenticated
GRANT SELECT ON TABLE public.companies TO authenticated;

-- Users: SELECT only for authenticated (No INSERT, UPDATE, or DELETE for users)
-- Prevents employees from modifying their role, company_id, or auth_user_id
GRANT SELECT ON TABLE public.users TO authenticated;

-- Tasks: SELECT and INSERT for authenticated
GRANT SELECT, INSERT ON TABLE public.tasks TO authenticated;

-- Tasks: UPDATE granted ONLY on explicitly permitted columns
-- Prevents reassigning tasks (assigned_to), tampering with created_by, or altering company_id
GRANT UPDATE (status, updated_at) ON TABLE public.tasks TO authenticated;

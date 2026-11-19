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
-- 2. Helper Security Functions (SECURITY DEFINER with fixed search_path)
-- ----------------------------------------------------------------------------

-- Returns the company_id associated with the authenticated user
CREATE OR REPLACE FUNCTION get_current_user_company_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    -- Check if company_id is provided directly in JWT app_metadata / claims
    SELECT COALESCE(
        NULLIF(current_setting('request.jwt.claims', true)::jsonb->'app_metadata'->>'company_id', '')::UUID,
        (SELECT company_id FROM public.users WHERE id = auth.uid() LIMIT 1)
    );
$$;

-- Returns the role ('manager' or 'employee') of the authenticated user
CREATE OR REPLACE FUNCTION get_current_user_role()
RETURNS user_role
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT role FROM public.users WHERE id = auth.uid() LIMIT 1;
$$;

-- Checks if the authenticated user is a Manager in their company
CREATE OR REPLACE FUNCTION is_company_manager()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.users
        WHERE id = auth.uid()
          AND role = 'manager'::user_role
    );
$$;

-- ----------------------------------------------------------------------------
-- 3. RLS Policies: Companies Table
-- ----------------------------------------------------------------------------

-- Users can only view their own company record
DROP POLICY IF EXISTS companies_select_policy ON companies;
CREATE POLICY companies_select_policy ON companies
    FOR SELECT
    TO authenticated
    USING (
        id = get_current_user_company_id()
    );

-- Only Managers can update their company details
DROP POLICY IF EXISTS companies_update_policy ON companies;
CREATE POLICY companies_update_policy ON companies
    FOR UPDATE
    TO authenticated
    USING (
        id = get_current_user_company_id()
        AND is_company_manager()
    )
    WITH CHECK (
        id = get_current_user_company_id()
        AND is_company_manager()
    );

-- ----------------------------------------------------------------------------
-- 4. RLS Policies: Users Table
-- ----------------------------------------------------------------------------

-- Users can only view colleague profiles within their own company
DROP POLICY IF EXISTS users_select_policy ON users;
CREATE POLICY users_select_policy ON users
    FOR SELECT
    TO authenticated
    USING (
        company_id = get_current_user_company_id()
    );

-- Only Managers can register/invite new users to their company
DROP POLICY IF EXISTS users_insert_policy ON users;
CREATE POLICY users_insert_policy ON users
    FOR INSERT
    TO authenticated
    WITH CHECK (
        company_id = get_current_user_company_id()
        AND is_company_manager()
    );

-- Users can update their own profile; managers can update company member profiles
DROP POLICY IF EXISTS users_update_policy ON users;
CREATE POLICY users_update_policy ON users
    FOR UPDATE
    TO authenticated
    USING (
        company_id = get_current_user_company_id()
        AND (id = auth.uid() OR is_company_manager())
    )
    WITH CHECK (
        -- Enforce that company_id cannot be changed across tenants
        company_id = get_current_user_company_id()
    );

-- ----------------------------------------------------------------------------
-- 5. RLS Policies: Tasks Table
-- ----------------------------------------------------------------------------

-- SELECT Policy:
-- - Managers can view ALL tasks belonging to their company.
-- - Employees can view tasks assigned to them (or all company tasks if team visibility is enabled).
DROP POLICY IF EXISTS tasks_select_policy ON tasks;
CREATE POLICY tasks_select_policy ON tasks
    FOR SELECT
    TO authenticated
    USING (
        company_id = get_current_user_company_id()
        AND (
            is_company_manager()
            OR assigned_to = auth.uid()
            OR created_by = auth.uid()
        )
    );

-- INSERT Policy:
-- - Only Managers can create tasks.
-- - Must be created within the manager's verified company.
-- - created_by must match the authenticated manager's UID.
DROP POLICY IF EXISTS tasks_insert_policy ON tasks;
CREATE POLICY tasks_insert_policy ON tasks
    FOR INSERT
    TO authenticated
    WITH CHECK (
        company_id = get_current_user_company_id()
        AND is_company_manager()
        AND created_by = auth.uid()
    );

-- UPDATE Policy:
-- - Managers can update any task within their company.
-- - Employees can update tasks assigned to them (e.g. updating status).
-- - Neither role can reassign the task to a different company (company_id is immutable).
DROP POLICY IF EXISTS tasks_update_policy ON tasks;
CREATE POLICY tasks_update_policy ON tasks
    FOR UPDATE
    TO authenticated
    USING (
        company_id = get_current_user_company_id()
        AND (
            is_company_manager()
            OR assigned_to = auth.uid()
        )
    )
    WITH CHECK (
        company_id = get_current_user_company_id()
    );

-- DELETE Policy:
-- - Only Managers can delete tasks belonging to their company.
DROP POLICY IF EXISTS tasks_delete_policy ON tasks;
CREATE POLICY tasks_delete_policy ON tasks
    FOR DELETE
    TO authenticated
    USING (
        company_id = get_current_user_company_id()
        AND is_company_manager()
    );

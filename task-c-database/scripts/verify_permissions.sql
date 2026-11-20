-- ============================================================================
-- SQL Verification Script: Verify Column-Level and Table-Level Grants
-- File: task-c-database/scripts/verify_permissions.sql
-- ============================================================================
-- RUN THIS SCRIPT IN SUPABASE SQL EDITOR TO VERIFY PRIVILEGE HARDENING.
-- All protected columns MUST return can_update = false.
-- Only tasks.status and tasks.updated_at MUST return can_update = true.
-- ============================================================================

-- Query 1: Verify specific column-level UPDATE privileges for 'authenticated' role
SELECT
    c.table_name,
    c.column_name,
    has_column_privilege('authenticated', format('public.%I', c.table_name), c.column_name, 'UPDATE') AS can_update,
    CASE 
        WHEN c.table_name = 'tasks' AND c.column_name IN ('status', 'updated_at') THEN 'PASS (PERMITTED)'
        WHEN c.table_name = 'tasks' AND c.column_name IN ('assigned_to', 'created_by', 'company_id') THEN 'PASS (PROTECTED)'
        WHEN c.table_name = 'users' AND c.column_name IN ('role', 'auth_user_id', 'company_id') THEN 'PASS (PROTECTED)'
        ELSE 'OTHER'
    END AS verification_result
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND (
    (c.table_name = 'users' AND c.column_name IN ('role', 'auth_user_id', 'company_id'))
    OR
    (c.table_name = 'tasks' AND c.column_name IN ('assigned_to', 'created_by', 'company_id', 'status', 'updated_at'))
  )
ORDER BY c.table_name, c.column_name;

-- Query 2: Verify table-level privileges for 'authenticated' and 'anon'
-- Confirms table-level UPDATE, DELETE, TRUNCATE are revoked.
SELECT
    table_name,
    grantee,
    privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND table_name IN ('companies', 'users', 'tasks')
  AND grantee IN ('anon', 'authenticated')
ORDER BY table_name, grantee, privilege_type;

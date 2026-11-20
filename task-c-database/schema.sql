-- ============================================================================
-- Multi-Tenant Task Management Database Schema (Supabase / PostgreSQL)
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Custom Enum Types
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('manager', 'employee');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE task_status AS ENUM ('pending', 'in_progress', 'completed', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE task_priority AS ENUM ('low', 'medium', 'high', 'urgent');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ----------------------------------------------------------------------------
-- 1. Companies Table (Tenant Entity)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL CHECK (char_length(trim(name)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- ----------------------------------------------------------------------------
-- 2. Users Table (Multi-Tenant Employees & Managers)
-- ----------------------------------------------------------------------------
-- In Supabase, id references auth.users(id). For standard Postgres setups,
-- it serves as the user identifier.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    full_name VARCHAR(255) NOT NULL CHECK (char_length(trim(full_name)) > 0),
    role user_role NOT NULL DEFAULT 'employee',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),

    -- Multi-tenant integrity: composite unique constraint required for composite FK references
    CONSTRAINT uq_users_company_user UNIQUE (company_id, id)
);

-- ----------------------------------------------------------------------------
-- 3. Tasks Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL CHECK (char_length(trim(title)) > 0),
    description TEXT,
    status task_status NOT NULL DEFAULT 'pending',
    priority task_priority NOT NULL DEFAULT 'medium',
    assigned_to UUID,
    created_by UUID NOT NULL,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),

    -- Database-level Multi-Tenant Integrity Guarantees:
    -- Composite Foreign Keys ensure tasks can ONLY be assigned to or created by
    -- users belonging to the exact same company!
    CONSTRAINT fk_tasks_assigned_to_company_user
        FOREIGN KEY (company_id, assigned_to)
        REFERENCES users(company_id, id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_tasks_created_by_company_user
        FOREIGN KEY (company_id, created_by)
        REFERENCES users(company_id, id)
        ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- Automatic updated_at Trigger
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc', now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_companies_updated_at ON companies;
CREATE TRIGGER set_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS set_users_updated_at ON users;
CREATE TRIGGER set_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS set_tasks_updated_at ON tasks;
CREATE TRIGGER set_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

-- ----------------------------------------------------------------------------
-- Performance Indexes Scoped for Tenant Queries
-- ----------------------------------------------------------------------------
-- Multi-tenant queries always filter by company_id first
CREATE INDEX IF NOT EXISTS idx_users_company_id ON users(company_id);
CREATE INDEX IF NOT EXISTS idx_users_company_role ON users(company_id, role);

CREATE INDEX IF NOT EXISTS idx_tasks_company_id ON tasks(company_id);
CREATE INDEX IF NOT EXISTS idx_tasks_company_status ON tasks(company_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_company_assigned_to ON tasks(company_id, assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_company_created_at ON tasks(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_company_due_date ON tasks(company_id, due_date) WHERE due_date IS NOT NULL;

-- ============================================================================
-- Seed Data for Multi-Tenant Task Management Database
-- ============================================================================

-- 1. Insert Companies (Tenants)
INSERT INTO companies (id, name) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'Acme Innovations Inc'),
    ('b0000000-0000-0000-0000-000000000002', 'Beta Robotics Corp')
ON CONFLICT (id) DO NOTHING;

-- 2. Insert Users for Company Alpha (Acme) and Company Beta
INSERT INTO users (id, company_id, email, full_name, role) VALUES
    -- Acme Innovations Users
    ('a1111111-1111-1111-1111-111111111111', 'a0000000-0000-0000-0000-000000000001', 'alice.manager@acme.com', 'Alice Manager', 'manager'),
    ('a2222222-2222-2222-2222-222222222222', 'a0000000-0000-0000-0000-000000000001', 'bob.developer@acme.com', 'Bob Developer', 'employee'),
    ('a3333333-3333-3333-3333-333333333333', 'a0000000-0000-0000-0000-000000000001', 'carol.designer@acme.com', 'Carol Designer', 'employee'),

    -- Beta Robotics Users
    ('b1111111-1111-1111-1111-111111111111', 'b0000000-0000-0000-0000-000000000002', 'david.manager@betarobotics.com', 'David Manager', 'manager'),
    ('b2222222-2222-2222-2222-222222222222', 'b0000000-0000-0000-0000-000000000002', 'eve.engineer@betarobotics.com', 'Eve Engineer', 'employee')
ON CONFLICT (id) DO NOTHING;

-- 3. Insert Tasks for Acme Innovations (Company Alpha)
INSERT INTO tasks (id, company_id, title, description, status, priority, assigned_to, created_by, due_date) VALUES
    (
        'a1000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        'Setup Supabase Row Level Security',
        'Configure isolation policies across companies and users tables',
        'completed',
        'high',
        'a2222222-2222-2222-2222-222222222222', -- Bob
        'a1111111-1111-1111-1111-111111111111', -- Alice
        NOW() + INTERVAL '3 days'
    ),
    (
        'a1000000-0000-0000-0000-000000000002',
        'a0000000-0000-0000-0000-000000000001',
        'Implement FastAPI CRUD & Pydantic Schemas',
        'Build POST, GET, PATCH endpoints with error validation',
        'in_progress',
        'urgent',
        'a2222222-2222-2222-2222-222222222222', -- Bob
        'a1111111-1111-1111-1111-111111111111', -- Alice
        NOW() + INTERVAL '5 days'
    ),
    (
        'a1000000-0000-0000-0000-000000000003',
        'a0000000-0000-0000-0000-000000000001',
        'Design Mobile Task UI Components',
        'Create high fidelity Figma designs for task cards and status pills',
        'pending',
        'medium',
        'a3333333-3333-3333-3333-333333333333', -- Carol
        'a1111111-1111-1111-1111-111111111111', -- Alice
        NOW() + INTERVAL '7 days'
    ),
    (
        'a1000000-0000-0000-0000-000000000004',
        'a0000000-0000-0000-0000-000000000001',
        'Deprecate Legacy v0 Monolith',
        'Decommission unused internal endpoints',
        'cancelled',
        'low',
        NULL,
        'a1111111-1111-1111-1111-111111111111', -- Alice
        NULL
    )
ON CONFLICT (id) DO NOTHING;

-- 4. Insert Tasks for Beta Robotics (Company Beta)
INSERT INTO tasks (id, company_id, title, description, status, priority, assigned_to, created_by, due_date) VALUES
    (
        'b1000000-0000-0000-0000-000000000001',
        'b0000000-0000-0000-0000-000000000002',
        'Firmware v3.2 Telemetry Integration',
        'Proprietary motor sensor pipeline for Beta Robotics units',
        'in_progress',
        'urgent',
        'b2222222-2222-2222-2222-222222222222', -- Eve
        'b1111111-1111-1111-1111-111111111111', -- David
        NOW() + INTERVAL '2 days'
    ),
    (
        'b1000000-0000-0000-0000-000000000002',
        'b0000000-0000-0000-0000-000000000002',
        'Calibrate Optical LiDAR Sensors',
        'Safety validation tests for manufacturing line',
        'pending',
        'high',
        'b2222222-2222-2222-2222-222222222222', -- Eve
        'b1111111-1111-1111-1111-111111111111', -- David
        NOW() + INTERVAL '4 days'
    )
ON CONFLICT (id) DO NOTHING;

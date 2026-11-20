-- ============================================================================
-- SQL Mapping Template: Map Supabase Auth Users to Application Profiles
-- File: task-c-database/scripts/map_auth_users.sql
-- ============================================================================
-- INSTRUCTIONS:
-- 1. In Supabase Dashboard -> Authentication -> Users, create the 5 users
--    using the exact email addresses below.
-- 2. Copy the generated User UID (UUID) for each user.
-- 3. Replace the placeholder '<AUTH_UUID_FOR_...>' below with the actual UUID.
-- 4. Run this script in the Supabase SQL Editor.
-- ============================================================================

-- ============================================================================
-- Company Alpha (Acme Innovations Inc)
-- ============================================================================

-- 1. Alice Manager (Company Alpha Manager)
-- Application Profile ID: a1111111-1111-1111-1111-111111111111
UPDATE public.users
SET auth_user_id = '<AUTH_UUID_FOR_ALICE>'::UUID
WHERE email = 'alice.manager@acme.com';

-- 2. Bob Developer (Company Alpha Employee)
-- Application Profile ID: a2222222-2222-2222-2222-222222222222
UPDATE public.users
SET auth_user_id = '<AUTH_UUID_FOR_BOB>'::UUID
WHERE email = 'bob.developer@acme.com';

-- 3. Carol Designer (Company Alpha Employee)
-- Application Profile ID: a3333333-3333-3333-3333-333333333333
UPDATE public.users
SET auth_user_id = '<AUTH_UUID_FOR_CAROL>'::UUID
WHERE email = 'carol.designer@acme.com';

-- ============================================================================
-- Company Beta (Beta Robotics Corp)
-- ============================================================================

-- 4. David Manager (Company Beta Manager)
-- Application Profile ID: b1111111-1111-1111-1111-111111111111
UPDATE public.users
SET auth_user_id = '<AUTH_UUID_FOR_DAVID>'::UUID
WHERE email = 'david.manager@betarobotics.com';

-- 5. Eve Engineer (Company Beta Employee)
-- Application Profile ID: b2222222-2222-2222-2222-222222222222
UPDATE public.users
SET auth_user_id = '<AUTH_UUID_FOR_EVE>'::UUID
WHERE email = 'eve.engineer@betarobotics.com';

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this query after mapping to verify all 5 profiles are correctly linked:
SELECT
    u.id AS profile_id,
    u.auth_user_id,
    u.email,
    u.role,
    c.name AS company_name
FROM public.users u
JOIN public.companies c ON u.company_id = c.id
ORDER BY c.name, u.role DESC, u.email;

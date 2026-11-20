"""
Opt-In Real Supabase Integration Test Suite
Executes real end-to-end tests against hosted Supabase Auth and PostgreSQL RLS.

GATING MECHANISM:
This module is SKIPPED by default during ordinary pytest execution.
To execute this suite against a live hosted Supabase instance:
1. Ensure .env has valid SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.
2. Execute migration task-c-database/migrations/002_supabase_auth_integration.sql.
3. Link the 5 demo auth users using task-c-database/scripts/map_auth_users.sql.
4. Set environment variable: RUN_SUPABASE_INTEGRATION_TESTS=1
5. Supply test access tokens or test passwords in environment:
   - SUPABASE_MGR_ALPHA_TOKEN
   - SUPABASE_EMP_ALPHA_TOKEN
   - SUPABASE_MGR_BETA_TOKEN
"""

import os
import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

# Explicit gating: will NOT run unless explicitly opted-in
RUN_INTEGRATION = os.getenv("RUN_SUPABASE_INTEGRATION_TESTS", "").lower() in ("1", "true")

if not RUN_INTEGRATION:
    pytest.skip(
        "Live Supabase integration tests are opt-in. Set RUN_SUPABASE_INTEGRATION_TESTS=1 to run.",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def live_client():
    if not settings.is_supabase_configured:
        pytest.fail("Cannot run live integration tests: SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY missing.")
    return TestClient(app)


@pytest.fixture(scope="module")
def mgr_alpha_jwt():
    token = os.getenv("SUPABASE_MGR_ALPHA_TOKEN")
    if not token:
        pytest.fail("SUPABASE_MGR_ALPHA_TOKEN environment variable required for live integration tests.")
    return token


@pytest.fixture(scope="module")
def emp_alpha_jwt():
    token = os.getenv("SUPABASE_EMP_ALPHA_TOKEN")
    if not token:
        pytest.fail("SUPABASE_EMP_ALPHA_TOKEN environment variable required for live integration tests.")
    return token


@pytest.fixture(scope="module")
def mgr_beta_jwt():
    token = os.getenv("SUPABASE_MGR_BETA_TOKEN")
    if not token:
        pytest.fail("SUPABASE_MGR_BETA_TOKEN environment variable required for live integration tests.")
    return token


def test_live_alpha_manager_sees_only_alpha_tasks(live_client, mgr_alpha_jwt):
    """Real test: Alpha manager retrieves only Company Alpha tasks via PostgREST + RLS."""
    response = live_client.get("/tasks", headers={"Authorization": f"Bearer {mgr_alpha_jwt}"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    for task in data["items"]:
        # Company Alpha ID from seed.sql: a0000000-0000-0000-0000-000000000001
        assert task["company_id"] == "a0000000-0000-0000-0000-000000000001"


def test_live_beta_manager_sees_only_beta_tasks(live_client, mgr_beta_jwt):
    """Real test: Beta manager retrieves only Company Beta tasks via PostgREST + RLS."""
    response = live_client.get("/tasks", headers={"Authorization": f"Bearer {mgr_beta_jwt}"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    for task in data["items"]:
        # Company Beta ID from seed.sql: b0000000-0000-0000-0000-000000000002
        assert task["company_id"] == "b0000000-0000-0000-0000-000000000002"


def test_live_alpha_employee_sees_only_assigned_tasks(live_client, emp_alpha_jwt):
    """Real test: Alpha employee sees ONLY tasks assigned directly to their profile."""
    response = live_client.get("/tasks", headers={"Authorization": f"Bearer {emp_alpha_jwt}"})
    assert response.status_code == 200
    data = response.json()
    for task in data["items"]:
        assert task["assigned_to"] == "a2222222-2222-2222-2222-222222222222"


def test_live_cross_company_patch_returns_404(live_client, mgr_beta_jwt):
    """Real test: Beta manager attempting to access Alpha task ID receives 404 (anti-enumeration)."""
    alpha_task_id = "a1000000-0000-0000-0000-000000000001"
    response = live_client.patch(
        f"/tasks/{alpha_task_id}",
        json={"status": "in_progress"},
        headers={"Authorization": f"Bearer {mgr_beta_jwt}"},
    )
    assert response.status_code == 404


def test_live_cross_company_assignment_prevented(live_client, mgr_alpha_jwt):
    """Real test: Manager in Alpha cannot assign a task to Eve in Beta."""
    eve_beta_id = "b2222222-2222-2222-2222-222222222222"
    payload = {
        "title": "Cross-Company Assignment Probe",
        "assigned_to": eve_beta_id,
        "priority": "high",
    }
    response = live_client.post(
        "/tasks",
        json=payload,
        headers={"Authorization": f"Bearer {mgr_alpha_jwt}"},
    )
    assert response.status_code == 400
    assert "does not exist within company" in response.json()["detail"]


def test_live_direct_postgrest_access_restricted_by_rls(mgr_alpha_jwt):
    """
    Real test: Direct PostgREST query bypassing FastAPI still evaluates PostgreSQL RLS.
    Executing SELECT * FROM tasks directly with Alpha Manager token returns only Alpha tasks.
    """
    postgrest_url = f"{settings.supabase_url}/rest/v1/tasks?select=*"
    headers = {
        "apikey": settings.supabase_publishable_key,
        "Authorization": f"Bearer {mgr_alpha_jwt}",
    }
    with httpx.Client() as http_client:
        res = http_client.get(postgrest_url, headers=headers)
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) > 0
        for row in rows:
            assert row["company_id"] == "a0000000-0000-0000-0000-000000000001"

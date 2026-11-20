"""
Automated Pytest Suite for Multi-Tenant Task Management API
Validates Bearer token authentication, Role-Based Access Control (RBAC),
tenant isolation, state machine transitions, and error handling.
"""

from app.api.deps import get_default_repository
from app.main import app
from app.repositories.supabase_task_repository import DatabaseOperationError


def test_health_endpoint(client):
    """Health check endpoint returns 200 and service metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data


# ============================================================================
# Authentication & Authorization Tests
# ============================================================================

def test_missing_bearer_token_rejected(client):
    """Requests without Authorization Bearer header must be rejected with 401."""
    response = client.get("/tasks")
    assert response.status_code == 401
    assert "Authorization Bearer token required" in response.json()["detail"]


def test_invalid_bearer_token_rejected(client):
    """Requests with invalid or expired tokens must be rejected with 401."""
    response = client.get(
        "/tasks",
        headers={"Authorization": "Bearer invalid_expired_jwt_token"},
    )
    assert response.status_code == 401
    assert "Invalid, expired, or revoked" in response.json()["detail"]


def test_valid_manager_authentication(client, mgr_alpha_headers):
    """A valid manager Bearer token grants access to company resources."""
    response = client.get("/tasks", headers=mgr_alpha_headers)
    assert response.status_code == 200
    assert "items" in response.json()


def test_valid_employee_authentication(client, emp_alpha_headers):
    """A valid employee Bearer token grants access to assigned resources."""
    response = client.get("/tasks", headers=emp_alpha_headers)
    assert response.status_code == 200
    assert "items" in response.json()


# ============================================================================
# POST /tasks (Create Task)
# ============================================================================

def test_manager_can_create_task(client, mgr_alpha_headers):
    """Managers can create a task; company_id and created_by derived from profile."""
    payload = {
        "title": "Setup Multi-Tenant RLS Integration",
        "description": "Connect FastAPI to Supabase PostgreSQL with user-scoped JWTs",
        "priority": "high",
        "assigned_to": "a2222222-2222-2222-2222-222222222222",  # Bob in Alpha
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == payload["title"]
    assert data["company_id"] == "a0000000-0000-0000-0000-000000000001"
    assert data["status"] == "pending"
    assert data["priority"] == "high"
    assert data["created_by"] == "a1111111-1111-1111-1111-111111111111"  # Alice's profile UUID
    assert data["assigned_to"] == "a2222222-2222-2222-2222-222222222222"
    assert "id" in data
    assert "created_at" in data


def test_employee_cannot_create_task(client, emp_alpha_headers):
    """Employees attempting to create a task must be rejected with 403 Forbidden."""
    payload = {
        "title": "Unauthorized Employee Task",
        "priority": "low",
    }
    response = client.post("/tasks", json=payload, headers=emp_alpha_headers)
    assert response.status_code == 403
    assert "Only managers are authorized" in response.json()["detail"]


def test_manager_cannot_assign_task_to_different_company_employee(client, mgr_alpha_headers):
    """Assigning a task to an employee in another company is rejected with 400 Bad Request."""
    payload = {
        "title": "Cross Tenant Leak Attempt",
        "priority": "urgent",
        "assigned_to": "b2222222-2222-2222-2222-222222222222",  # Eve in Beta
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 400
    assert "does not exist within company" in response.json()["detail"]


def test_client_supplied_company_id_cannot_override_tenant(client, mgr_alpha_headers):
    """Even if an attacker supplies company_id in payload, the API uses the manager's tenant."""
    payload = {
        "title": "Tampered Company Payload",
        "company_id": "b0000000-0000-0000-0000-000000000002",  # Beta's UUID
        "priority": "medium",
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 201
    # Must be Alpha, never the client-supplied Beta
    assert response.json()["company_id"] == "a0000000-0000-0000-0000-000000000001"


def test_create_task_validation_error(client, mgr_alpha_headers):
    """Validation errors (empty title or whitespace) must return 422 Unprocessable Entity."""
    payload = {
        "title": "   ",
        "priority": "medium",
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 422


# ============================================================================
# GET /tasks (Retrieve Tasks & Tenant Scoping)
# ============================================================================

def test_manager_sees_all_own_company_tasks(client, mgr_alpha_headers, mgr_beta_headers):
    """Managers see all tasks in their company, and zero tasks from other tenants."""
    res_alpha = client.get("/tasks", headers=mgr_alpha_headers)
    assert res_alpha.status_code == 200
    alpha_data = res_alpha.json()

    res_beta = client.get("/tasks", headers=mgr_beta_headers)
    assert res_beta.status_code == 200
    beta_data = res_beta.json()

    # Company Alpha has 3 seeded tasks
    assert alpha_data["total"] == 3
    assert all(t["company_id"] == "a0000000-0000-0000-0000-000000000001" for t in alpha_data["items"])
    assert not any(t["company_id"] == "b0000000-0000-0000-0000-000000000002" for t in alpha_data["items"])

    # Company Beta has 1 seeded task
    assert beta_data["total"] == 1
    assert all(t["company_id"] == "b0000000-0000-0000-0000-000000000002" for t in beta_data["items"])


def test_employee_sees_only_assigned_tasks(client, emp_alpha_headers):
    """
    Employees see ONLY tasks assigned to their profile.
    Bob has 2 assigned tasks in Alpha (task 101, task 102).
    Carol has task 103, which Bob must NOT see.
    """
    response = client.get("/tasks", headers=emp_alpha_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    for t in data["items"]:
        assert t["assigned_to"] == "a2222222-2222-2222-2222-222222222222"  # Bob's profile ID
    # Carol's task 103 must be excluded
    assert not any(t["id"] == "a1000000-0000-0000-0000-000000000003" for t in data["items"])


def test_employee_cannot_bypass_assigned_to_filter(client, emp_alpha_headers):
    """
    If an employee manipulates query parameters like ?assigned_to=<Carol>,
    the service enforces employee assigned-only visibility.
    """
    carol_id = "a3333333-3333-3333-3333-333333333333"
    response = client.get(f"/tasks?assigned_to={carol_id}", headers=emp_alpha_headers)
    assert response.status_code == 200
    data = response.json()

    # Bob still only sees his own tasks, never Carol's
    assert data["total"] == 2
    assert all(t["assigned_to"] == "a2222222-2222-2222-2222-222222222222" for t in data["items"])


def test_get_tasks_metrics_calculation(client, mgr_alpha_headers):
    """GET /tasks computes total, completed_count, pending_count, and completion_percentage."""
    response = client.get("/tasks", headers=mgr_alpha_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert data["completed_count"] == 1
    assert data["pending_count"] == 1
    assert data["completion_percentage"] == 33.33


def test_get_tasks_filter_by_status(client, mgr_alpha_headers):
    """Filtering tasks by status returns matching tasks only."""
    response = client.get("/tasks?status=completed", headers=mgr_alpha_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "completed"
    assert data["items"][0]["id"] == "a1000000-0000-0000-0000-000000000001"


# ============================================================================
# PATCH /tasks/{id} (Update Task Status)
# ============================================================================

def test_assigned_employee_can_update_task_status(client, emp_alpha_headers):
    """An employee assigned to a task can update its status to completed."""
    # a1000000-0000-0000-0000-000000000002 is in_progress and assigned to Bob
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000002",
        json={"status": "completed"},
        headers=emp_alpha_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "a1000000-0000-0000-0000-000000000002"
    assert data["status"] == "completed"


def test_employee_cannot_update_unassigned_task(client, emp_alpha_headers):
    """An employee cannot update tasks assigned to other employees (returns 404 Not Found to prevent enumeration)."""
    # a1000000-0000-0000-0000-000000000003 is assigned to Carol, Bob tries to update it
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000003",
        json={"status": "completed"},
        headers=emp_alpha_headers,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_manager_can_update_any_task_in_their_company(client, mgr_alpha_headers):
    """Managers can update any task within their company."""
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000003",
        json={"status": "in_progress"},
        headers=mgr_alpha_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_cross_tenant_patch_manipulation_returns_404(client, mgr_beta_headers):
    """
    If a user in Company Beta attempts to update a task belonging to Company Alpha,
    the API returns 404 Not Found to prevent ID enumeration.
    """
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000001",
        json={"status": "in_progress"},
        headers=mgr_beta_headers,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_employee_cannot_reopen_completed_task(client, emp_alpha_headers):
    """Reopening completed tasks requires manager permissions; returns 403 Forbidden."""
    # a1000000-0000-0000-0000-000000000001 is completed and assigned to Bob
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000001",
        json={"status": "in_progress"},
        headers=emp_alpha_headers,
    )
    assert response.status_code == 403
    assert "Only managers can reopen completed tasks" in response.json()["detail"]


def test_invalid_status_enum_rejected(client, mgr_alpha_headers):
    """Submitting an invalid status string returns 422 Unprocessable Entity."""
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000001",
        json={"status": "not_a_valid_status"},
        headers=mgr_alpha_headers,
    )
    assert response.status_code == 422


# ============================================================================
# Database Error Handling Tests
# ============================================================================

def test_database_error_handling_returns_500_without_leaks(client, mgr_alpha_headers):
    """DatabaseOperationError is mapped to HTTP 500 without leaking internal technical details."""
    class FailingRepo:
        def list_by_company(self, *args, **kwargs):
            raise DatabaseOperationError("Database query failed while accessing tasks.")

    app.dependency_overrides[get_default_repository] = lambda: FailingRepo()

    try:
        response = client.get("/tasks", headers=mgr_alpha_headers)
        assert response.status_code == 500
        data = response.json()
        assert data["error_type"] == "database_error"
        assert "postgrest" not in data["detail"].lower()
        assert "traceback" not in data["detail"].lower()
        assert "password" not in data["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_default_repository, None)


def test_missing_supabase_config_returns_503(client, mgr_alpha_headers, monkeypatch):
    """When Supabase is unconfigured, production repository raises SupabaseConfigurationError resulting in HTTP 503."""
    from app.config import settings

    # Remove mock repo override so get_default_repository executes
    app.dependency_overrides.pop(get_default_repository, None)
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_publishable_key", "")

    try:
        response = client.get("/tasks", headers=mgr_alpha_headers)
        assert response.status_code == 503
        data = response.json()
        assert data["error_type"] == "service_unavailable"
        assert "Supabase is not configured" in data["detail"]
    finally:
        pass


def test_task_immutable_fields_cannot_be_altered_via_patch(client, mgr_alpha_headers):
    """TaskUpdate schema only accepts status; fields like assigned_to, created_by, company_id cannot be tampered with."""
    tampered_payload = {
        "status": "completed",
        "assigned_to": "b2222222-2222-2222-2222-222222222222",
        "company_id": "b0000000-0000-0000-0000-000000000002",
        "created_by": "b1111111-1111-1111-1111-111111111111",
    }
    response = client.patch(
        "/tasks/a1000000-0000-0000-0000-000000000002",
        json=tampered_payload,
        headers=mgr_alpha_headers,
    )
    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "completed"
    assert task["assigned_to"] == "a2222222-2222-2222-2222-222222222222"
    assert task["company_id"] == "a0000000-0000-0000-0000-000000000001"


def test_get_tasks_pagination_limit_and_offset(client, mgr_alpha_headers):
    """GET /tasks supports limit and offset parameters."""
    res_all = client.get("/tasks", headers=mgr_alpha_headers)
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 3

    res_paged = client.get("/tasks?limit=2&offset=1", headers=mgr_alpha_headers)
    assert res_paged.status_code == 200
    data = res_paged.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2

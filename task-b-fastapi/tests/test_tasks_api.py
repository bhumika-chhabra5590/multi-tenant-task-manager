def test_unauthenticated_request_rejected(client):
    """Requests without authentication headers must be rejected with 401."""
    response = client.get("/tasks")
    assert response.status_code == 401
    assert "X-User-Id header required" in response.json()["detail"]


def test_invalid_user_rejected(client):
    """Requests with unknown user IDs must be rejected with 401."""
    response = client.get("/tasks", headers={"X-User-Id": "non_existent_user"})
    assert response.status_code == 401


def test_spoofed_company_header_rejected(client, mgr_alpha_headers):
    """If a client provides an X-Company-Id that mismatches the user's company, reject with 403."""
    headers = {**mgr_alpha_headers, "X-Company-Id": "comp_beta"}
    response = client.get("/tasks", headers=headers)
    assert response.status_code == 403
    assert "Tenant mismatch detected" in response.json()["detail"]


# ============================================================================
# POST /tasks (Create Task)
# ============================================================================

def test_manager_can_create_task(client, mgr_alpha_headers):
    """Managers can create a task for their company; status code should be 201."""
    payload = {
        "title": "Build Multi-Tenant Security Docs",
        "description": "Document RLS and API tenant context guarantees",
        "priority": "high",
        "assigned_to": "usr_emp_alpha_1",
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == payload["title"]
    assert data["company_id"] == "comp_alpha"
    assert data["status"] == "pending"
    assert data["priority"] == "high"
    assert data["created_by"] == "usr_mgr_alpha"
    assert data["assigned_to"] == "usr_emp_alpha_1"
    assert "id" in data
    assert "created_at" in data


def test_employee_cannot_create_task(client, emp_alpha_headers):
    """Employees attempting to create a task must be forbidden (403)."""
    payload = {
        "title": "Unauthorized Employee Task",
        "priority": "low",
    }
    response = client.post("/tasks", json=payload, headers=emp_alpha_headers)
    assert response.status_code == 403
    assert "Only managers are authorized" in response.json()["detail"]


def test_manager_cannot_assign_task_to_different_company_employee(client, mgr_alpha_headers):
    """Assigning a task to an employee in another company is rejected with 400."""
    payload = {
        "title": "Cross Tenant Assignment Leak Attempt",
        "priority": "urgent",
        "assigned_to": "usr_emp_beta_1", # User belongs to comp_beta, not comp_alpha
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 400
    assert "does not exist within company" in response.json()["detail"]


def test_create_task_validation_error(client, mgr_alpha_headers):
    """Validation errors (empty title) must return 422 Unprocessable Entity."""
    payload = {
        "title": "   ",  # Whitespace only
        "priority": "medium",
    }
    response = client.post("/tasks", json=payload, headers=mgr_alpha_headers)
    assert response.status_code == 422


# ============================================================================
# GET /tasks (Retrieve Tasks & Tenant Scoping)
# ============================================================================

def test_tenant_data_isolation_between_companies(client, mgr_alpha_headers, mgr_beta_headers):
    """
    Critical Multi-Tenant Test:
    Company Alpha users only see Alpha tasks.
    Company Beta users only see Beta tasks.
    """
    # Manager Alpha fetches tasks
    res_alpha = client.get("/tasks", headers=mgr_alpha_headers)
    assert res_alpha.status_code == 200
    alpha_data = res_alpha.json()

    # Manager Beta fetches tasks
    res_beta = client.get("/tasks", headers=mgr_beta_headers)
    assert res_beta.status_code == 200
    beta_data = res_beta.json()

    # Verify Company Alpha tasks
    alpha_items = alpha_data["items"]
    assert len(alpha_items) == 3
    assert all(t["company_id"] == "comp_alpha" for t in alpha_items)
    assert any(t["id"] == "task_alpha_101" for t in alpha_items)
    # Ensure no Beta tasks leaked into Alpha
    assert not any(t["id"] == "task_beta_201" for t in alpha_items)

    # Verify Company Beta tasks
    beta_items = beta_data["items"]
    assert len(beta_items) == 1
    assert all(t["company_id"] == "comp_beta" for t in beta_items)
    assert beta_items[0]["id"] == "task_beta_201"
    # Ensure no Alpha tasks leaked into Beta
    assert not any(t["id"] == "task_alpha_101" for t in beta_items)


def test_get_tasks_metrics_calculation(client, mgr_alpha_headers):
    """GET /tasks computes total, completed_count, pending_count, and completion_percentage."""
    response = client.get("/tasks", headers=mgr_alpha_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 3
    assert data["completed_count"] == 1
    assert data["pending_count"] == 1
    # 1 completed / 3 total = 33.33%
    assert data["completion_percentage"] == 33.33


def test_get_tasks_filter_by_status(client, mgr_alpha_headers):
    """Filtering tasks by status returns matching tasks only."""
    response = client.get("/tasks?status=completed", headers=mgr_alpha_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "completed"
    assert data["items"][0]["id"] == "task_alpha_101"


def test_get_tasks_filter_by_assignee(client, mgr_alpha_headers):
    """Filtering tasks by assigned_to returns assignee's tasks."""
    response = client.get("/tasks?assigned_to=usr_emp_alpha_2", headers=mgr_alpha_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["assigned_to"] == "usr_emp_alpha_2"
    assert data["items"][0]["id"] == "task_alpha_103"


# ============================================================================
# PATCH /tasks/{id} (Update Task Status)
# ============================================================================

def test_assigned_employee_can_update_task_status(client, emp_alpha_headers):
    """An employee assigned to a task can update its status to completed."""
    # task_alpha_102 is currently in_progress and assigned to usr_emp_alpha_1
    response = client.patch(
        "/tasks/task_alpha_102",
        json={"status": "completed"},
        headers=emp_alpha_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "task_alpha_102"
    assert data["status"] == "completed"


def test_unassigned_employee_cannot_update_task(client, emp_alpha_2_headers):
    """An employee cannot update tasks assigned to other employees (403 Forbidden)."""
    # task_alpha_102 is assigned to usr_emp_alpha_1, emp_alpha_2 tries to update it
    response = client.patch(
        "/tasks/task_alpha_102",
        json={"status": "completed"},
        headers=emp_alpha_2_headers,
    )
    assert response.status_code == 403
    assert "only permitted to update tasks assigned to them" in response.json()["detail"]


def test_manager_can_update_any_task_in_their_company(client, mgr_alpha_headers):
    """Managers can update any task within their company."""
    response = client.patch(
        "/tasks/task_alpha_103",
        json={"status": "in_progress"},
        headers=mgr_alpha_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_cross_tenant_patch_manipulation_returns_404(client, mgr_beta_headers):
    """
    Crucial Security Test:
    If a manager in Company Beta tries to update task_alpha_101 belonging to Company Alpha,
    the API returns 404 Not Found to prevent data exposure and ID enumeration.
    """
    response = client.patch(
        "/tasks/task_alpha_101",
        json={"status": "in_progress"},
        headers=mgr_beta_headers, # Company Beta manager
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_employee_cannot_reopen_completed_task(client, emp_alpha_headers):
    """Reopening completed tasks requires manager permissions; returns 403."""
    response = client.patch(
        "/tasks/task_alpha_101", # currently completed and assigned to emp_alpha_1
        json={"status": "in_progress"},
        headers=emp_alpha_headers,
    )
    assert response.status_code == 403
    assert "Only managers can reopen completed tasks" in response.json()["detail"]


def test_invalid_status_enum_rejected(client, mgr_alpha_headers):
    """Submitting an invalid status string returns 422 Unprocessable Entity."""
    response = client.patch(
        "/tasks/task_alpha_101",
        json={"status": "invalid_status_string"},
        headers=mgr_alpha_headers,
    )
    assert response.status_code == 422

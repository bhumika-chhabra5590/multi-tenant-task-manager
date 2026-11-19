# Multi-Tenant Data Security & Isolation Architecture

## 1. Executive Summary

In a multi-tenant software system serving multiple companies, **data isolation is paramount**. A critical vulnerability in multi-tenant architectures is **Insecure Direct Object Reference (IDOR)** coupled with **Parameter Tampering**, where a malicious or compromised user modifies URL query strings, request bodies, or headers to read, update, or corrupt another tenant's private records.

This document details the multi-layered **Defense-in-Depth** architecture implemented across the **FastAPI Application Layer** and the **PostgreSQL / Supabase Database Layer**. It demonstrates why **no user can access or manipulate data belonging to another company**, even when intentionally altering request parameters, fabricating payloads, or guessing resource IDs.

---

## 2. Threat Model & Attack Vectors Analyzed

| Threat ID | Attack Vector | Attacker Action | System Defense Mechanism |
|---|---|---|---|
| **T-1** | **Query Parameter Tampering** | Alice (Company A) appends `?company_id=comp_beta` to `GET /tasks`. | Application ignores client-provided tenant queries; DB RLS overrides with authenticated tenant context. |
| **T-2** | **Body Payload Spoofing** | Alice sends `POST /tasks` with `"company_id": "comp_beta"` in JSON. | `TaskCreate` schema omits `company_id`; service injects verified tenant context from JWT. |
| **T-3** | **Cross-Tenant IDOR Probing** | Alice sends `PATCH /tasks/{beta_task_id}` trying to modify Beta's task. | Repository queries `WHERE id = :id AND company_id = :auth_company_id`. Returns **404 Not Found** (anti-enumeration). |
| **T-4** | **Cross-Tenant Assignee Injection** | Alice creates a task but assigns it to Eve (Employee in Company B). | Service validates tenant membership; DB composite foreign key `(company_id, assigned_to)` blocks at schema level. |
| **T-5** | **Privilege Escalation** | Bob (Employee in Company A) tries to create tasks or re-open completed tasks. | RBAC enforcement in FastAPI dependencies + Service layer + RLS policy (`is_company_manager()`). |
| **T-6** | **Header Tampering** | Attacker injects `X-Company-Id: comp_beta` while authenticated as User A. | Auth guard validates cryptographic token/user registry; detects mismatch and rejects with **403 Forbidden**. |

---

## 3. Four Pillars of Defense-in-Depth

```
                         [ INCOMING CLIENT REQUEST ]
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ LAYER 1: IDENTITY & AUTHENTICATION CONTEXT                             │
 │ - Cryptographic JWT signature verification (Supabase auth / Gateway)   │
 │ - Immutable user claims: user_id & verified company_id                 │
 │ - Header anti-spoofing validation (rejects mismatched tenant headers)  │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ LAYER 2: APPLICATION SERVICE & REPOSITORY BOUNDARY                     │
 │ - Zero-trust input: Pydantic schemas never accept company_id in payload│
 │ - Strict RBAC: Managers create/assign; Employees update assigned tasks │
 │ - Repository calls ALWAYS scoped: get_by_id(task_id, company_id)       │
 │ - Cross-tenant IDOR returns 404 (prevents ID enumeration)              │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ LAYER 3: DATABASE ENGINE ROW LEVEL SECURITY (RLS)                      │
 │ - PostgreSQL FORCE ROW LEVEL SECURITY enabled on all tenant tables     │
 │ - Policies execute get_current_user_company_id() via auth.uid()        │
 │ - Database itself filters out foreign rows even if app layer has a bug │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ LAYER 4: RELATIONAL SCHEMA INTEGRITY CONSTRAINTS                       │
 │ - Composite Foreign Key: (company_id, assigned_to) -> users(...)       │
 │ - Database physically refuses to assign tasks to cross-company users   │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Deep-Dive: Prevention of Parameter Manipulation

### Scenario A: Attacker manipulates Query Parameters (`GET /tasks?company_id=comp_beta`)

1. **Client Action**: An employee of Company Alpha intercepts their HTTP traffic and issues:
   ```http
   GET /tasks?company_id=b0000000-0000-0000-0000-000000000002 HTTP/1.1
   Host: api.platform.com
   X-User-Id: usr_emp_alpha_1
   ```
2. **Application Layer Processing**:
   - The route handler in `app/api/v1/tasks.py` derives the tenant strictly from `current_user: Annotated[AuthUser, Depends(get_current_user)]`.
   - The service method `service.get_tasks(user=current_user, ...)` uses `user.company_id` (`comp_alpha`).
   - The repository query executes:
     ```sql
     SELECT * FROM tasks WHERE company_id = 'comp_alpha';
     ```
   - Any query parameter named `company_id` sent by the client is discarded.
3. **Database Layer Enforcement (Supabase RLS)**:
   - When the SQL query executes, PostgreSQL evaluates the RLS policy:
     ```sql
     CREATE POLICY tasks_select_policy ON tasks
         FOR SELECT TO authenticated
         USING (
             company_id = get_current_user_company_id()
             AND (is_company_manager() OR assigned_to = auth.uid() OR created_by = auth.uid())
         );
     ```
   - Even if raw SQL `SELECT * FROM tasks` were executed, PostgreSQL silences and filters out all rows where `company_id != comp_alpha`.
4. **Outcome**: The attacker receives only Company Alpha's tasks. Zero data leakage occurs.

---

### Scenario B: Attacker manipulates JSON Body (`POST /tasks`)

1. **Client Action**: An attacker sends a POST request attempting to insert a task directly into a competitor's company workspace:
   ```http
   POST /tasks HTTP/1.1
   Host: api.platform.com
   X-User-Id: usr_mgr_alpha
   Content-Type: application/json

   {
     "title": "Malicious Injected Task",
     "company_id": "b0000000-0000-0000-0000-000000000002",
     "priority": "urgent"
   }
   ```
2. **Pydantic Validation**:
   - The `TaskCreate` schema defines:
     ```python
     class TaskCreate(BaseModel):
         title: str
         description: Optional[str] = None
         priority: TaskPriority = TaskPriority.MEDIUM
         assigned_to: Optional[str] = None
         due_date: Optional[datetime] = None
     ```
   - `company_id` is **not a field** on `TaskCreate`. Pydantic strips or ignores extraneous fields, preventing parameter pollution.
3. **Service Layer Injection**:
   - `TaskService.create_task()` assigns:
     ```python
     company_id = user.company_id  # Injected directly from trusted server session
     created_by = user.id
     ```
4. **Database RLS Insertion Policy**:
   - The database requires:
     ```sql
     WITH CHECK (
         company_id = get_current_user_company_id()
         AND is_company_manager()
         AND created_by = auth.uid()
     );
     ```
   - If an insert contains a `company_id` that does not match `get_current_user_company_id()`, PostgreSQL terminates the transaction with an RLS check violation.
5. **Outcome**: The task is created solely inside Company Alpha.

---

### Scenario C: Cross-Tenant Resource Probing (`PATCH /tasks/{id}`)

1. **Client Action**: A malicious employee at Company Alpha guesses or enumerates task IDs belonging to Company Beta:
   ```http
   PATCH /tasks/task_beta_201 HTTP/1.1
   Host: api.platform.com
   X-User-Id: usr_emp_alpha_1
   Content-Type: application/json

   { "status": "completed" }
   ```
2. **Tenant Scoping in Data Layer**:
   - `task_service.update_task_status(user=current_user, task_id="task_beta_201", ...)` calls:
     ```python
     task = self.repo.get_by_id(task_id="task_beta_201", company_id=user.company_id)
     if not task:
         raise EntityNotFoundError(entity_name="Task", entity_id=task_id)
     ```
   - Because `task_beta_201` belongs to `comp_beta` and not `comp_alpha`, the repository returns `None`.
3. **Information Disclosure Prevention**:
   - Returning `403 Forbidden` would confirm to the attacker that the task exists in another company.
   - Returning `404 Not Found` ensures that the attacker cannot distinguish between a non-existent task and a task belonging to another company.
4. **Outcome**: Request returns `404 Not Found`.

---

### Scenario D: Cross-Tenant Foreign Key Assignment

1. **Client Action**: A manager at Company Alpha attempts to assign a task to Eve, who works at Company Beta:
   ```http
   POST /tasks HTTP/1.1
   Host: api.platform.com
   X-User-Id: usr_mgr_alpha
   Content-Type: application/json

   {
     "title": "Confidential Alpha Research",
     "assigned_to": "b2222222-2222-2222-2222-222222222222"
   }
   ```
2. **Application Validation**:
   - `TaskService` checks:
     ```python
     if not self.repo.user_exists_in_company(payload.assigned_to, user.company_id):
         raise BusinessRuleViolationError(...)
     ```
   - The request is halted with `400 Bad Request`.
3. **Schema-Level Composite Foreign Key (Database Level)**:
   - In `task-c-database/schema.sql`, the relationship is defined as:
     ```sql
     CONSTRAINT fk_tasks_assigned_to_company_user
         FOREIGN KEY (company_id, assigned_to)
         REFERENCES users(company_id, id)
     ```
   - Even if the application logic failed or a direct database query was executed, PostgreSQL requires that the `company_id` on the `tasks` row matches the `company_id` on the `users` row.
   - If `assigned_to` belongs to Company Beta, the composite foreign key constraint is violated, and the database rejects the write!

---

## 5. Row Level Security (RLS) Policy Mechanics

Supabase uses PostgreSQL Row Level Security to evaluate permissions per individual row.

### Helper Function: `get_current_user_company_id()`
```sql
CREATE OR REPLACE FUNCTION get_current_user_company_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT COALESCE(
        NULLIF(current_setting('request.jwt.claims', true)::jsonb->'app_metadata'->>'company_id', '')::UUID,
        (SELECT company_id FROM public.users WHERE id = auth.uid() LIMIT 1)
    );
$$;
```
- **Performance**: Declared `STABLE` so PostgreSQL caches the function result for the duration of a query execution, avoiding repeated lookups.
- **Security**: Declared `SECURITY DEFINER` with `SET search_path = public` to prevent search-path hijacking attacks.

### Why FORCE ROW LEVEL SECURITY Matters
By default, PostgreSQL bypasses RLS for the table owner. In our configuration:
```sql
ALTER TABLE companies FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
```
This guarantees that **all queries**—including those issued by migrations or internal backend connections—must satisfy RLS conditions unless explicitly running under a designated superuser.

---

## 6. Summary of Guarantees

| Security Property | Application Guarantee | Database Guarantee |
|---|---|---|
| **Tenant Isolation** | All repo queries filtered by `company_id` | RLS policy enforces `company_id = get_current_user_company_id()` |
| **Tamper Resistance** | Schemas strip client `company_id`; context derived from session | `WITH CHECK` constraint rejects cross-tenant writes |
| **Assignee Integrity** | Service verifies employee belongs to tenant | Composite FK `(company_id, assigned_to)` enforces at schema level |
| **RBAC Enforcement** | Managers create/reopen; Employees update assigned tasks | RLS policies verify `is_company_manager()` or `assigned_to = auth.uid()` |
| **Anti-Enumeration** | Foreign resources return `404 Not Found` | Cross-tenant rows are invisible in `SELECT` output |

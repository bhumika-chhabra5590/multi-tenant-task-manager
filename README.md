# Multi-Tenant Task Management System

A production-grade, multi-tenant task management system designed for a multi-company environment. Built with **TypeScript**, **Python / FastAPI**, and **PostgreSQL / Supabase** with Row Level Security (RLS).

---

## 📋 Table of Contents

- [Overview & Scenario](#overview--scenario)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Task A – TypeScript Module](#task-a--typescript-module)
- [Task B – Python / FastAPI REST API](#task-b--python--fastapi-rest-api)
- [Task C – Supabase / PostgreSQL Database & RLS](#task-c--supabase--postgresql-database--rls)
- [Multi-Tenant Data Security & Anti-Tampering](#multi-tenant-data-security--anti-tampering)
- [Setup & Installation](#setup--installation)
- [Running Test Suites](#running-test-suites)

---

## 🏢 Overview & Scenario

The system models a multi-company SaaS platform:
1. **Multi-Tenancy**: Data is strictly partitioned by Company. Users in Company A cannot see or manipulate tasks in Company B.
2. **Role-Based Access Control (RBAC)**:
   - **Managers**: Can create and assign tasks to employees within their company, view all company tasks, and update any company task.
   - **Employees**: Can view tasks in their company, and update the status of tasks assigned specifically to them.
3. **Data Security**: Defense-in-depth across Application and Database layers prevents parameter tampering, IDOR, and tenant data leaks.

---

## 🏗️ System Architecture

```
                                  [ CLIENT REQUEST ]
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────┐
                │             FastAPI Application Layer            │
                │  - Auth Dependency: Cryptographic User Context   │
                │  - Pydantic v2: Strict Request Validation        │
                │  - Service Layer: RBAC & State Transition Rules  │
                │  - Repository: Tenant-Scoped Queries             │
                └─────────────────────────┬────────────────────────┘
                                          │
                                          ▼
                ┌──────────────────────────────────────────────────┐
                │          PostgreSQL / Supabase Database          │
                │  - Row Level Security (FORCE RLS)                │
                │  - Composite FKs: (company_id, assigned_to)      │
                │  - Optimized Multi-Tenant B-Tree Indexes         │
                │  - Automated updated_at Triggers                 │
                └──────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
multi-tenant-task-manager/
├── README.md                          # Comprehensive documentation & setup instructions
├── package.json                       # TypeScript test & build scripts
├── tsconfig.json                      # Strict TypeScript compiler configuration
├── task-a-typescript/                 # Task A: TypeScript Library
│   ├── src/
│   │   ├── types.ts                   # Interfaces, Enums, and Custom Error hierarchy
│   │   ├── taskService.ts             # filterByStatus, calculateCompletionPercentage, fetchTasks
│   │   └── index.ts                   # Public module exports
│   └── tests/
│       └── taskService.test.ts        # Comprehensive unit tests (18 tests)
├── task-b-fastapi/                    # Task B: Python / FastAPI REST API
│   ├── app/
│   │   ├── main.py                    # App entry point, CORS, and HTTP exception handlers
│   │   ├── config.py                  # Environment & App configuration
│   │   ├── core/
│   │   │   ├── auth.py                # Authentication, tenant derivation & anti-spoofing
│   │   │   └── exceptions.py          # Domain-level exception hierarchy
│   │   ├── schemas/
│   │   │   ├── task.py                # Pydantic v2 schemas (TaskCreate, TaskResponse, etc.)
│   │   │   └── user.py                # Company & User response schemas
│   │   ├── models/
│   │   │   └── domain.py              # Domain entities
│   │   ├── repositories/
│   │   │   └── task_repository.py     # Tenant-scoped data access layer
│   │   ├── services/
│   │   │   └── task_service.py        # Business logic, RBAC, and lifecycle state machine
│   │   └── api/
│   │       ├── deps.py                # Dependency injection (Auth & Services)
│   │       └── v1/
│   │           └── tasks.py           # REST endpoints (POST, GET, PATCH)
│   ├── tests/
│   │   ├── conftest.py                # Pytest fixtures and mock tenant users
│   │   └── test_tasks_api.py          # Unit & integration tests (17 tests)
│   └── requirements.txt               # Pinned Python dependencies
└── task-c-database/                   # Task C: Database, SQL & RLS
    ├── schema.sql                     # Tables, constraints, composite FKs, triggers, indexes
    ├── rls.sql                        # Row Level Security policies & security definer functions
    ├── queries.sql                    # Parameterized queries (fetch by company, completed vs pending)
    ├── seed.sql                       # Multi-tenant mock data (Acme & Beta Robotics)
    └── security_architecture.md       # In-depth security analysis on parameter tampering defense
```

---

## 🟦 Task A – TypeScript Module

Located in `task-a-typescript/src/`.

### 1. Types & Interfaces (`types.ts`)
- **Enums & Types**: `TaskStatus` (`pending`, `in_progress`, `completed`, `cancelled`), `TaskPriority`, `UserRole`.
- **Core Entities**: `Company`, `User`, `Task`.
- **Options & Payloads**: `TaskFilterOptions`, `CompletionPercentageOptions`, `FetchTasksParams`, `FetchTasksOptions`.
- **Custom Error Hierarchy**:
  - `TaskServiceError` (base)
  - `ApiError` (contains `statusCode` and response details)
  - `NetworkError` (handles connection failures)
  - `TimeoutError` (handles request cancellation / aborts)
  - `ValidationError` (schema mismatch and invalid input reporting)

### 2. Core Functions (`taskService.ts`)

#### `filterTasksByStatus(tasks: Task[], status: TaskStatus | TaskStatus[]): Task[]`
Filters tasks matching a single status or multiple statuses with runtime validation.
```typescript
const inFlight = filterTasksByStatus(tasks, ['pending', 'in_progress']);
```

#### `calculateCompletionPercentage(tasks: Task[], options?: CompletionPercentageOptions): number`
Calculates completion percentage with support for:
- Empty array protection (returns `0` instead of `NaN` / division by zero).
- `excludeCancelled`: Option to omit cancelled tasks from total denominator.
- `decimalPrecision`: Configurable decimal rounding (defaults to `2`).
```typescript
const rate = calculateCompletionPercentage(tasks, { excludeCancelled: true, decimalPrecision: 1 });
```

#### `fetchTasks(options?: FetchTasksOptions): Promise<Task[]>`
Asynchronous API consumer supporting:
- Multi-tenant query parameter serialization (`companyId`, `status`, `assignedTo`, `limit`).
- Configurable timeout and `AbortSignal` cancellation.
- Custom `fetch` dependency injection (enables testing and isomorphic support).
- Response unwrapping (supports both direct arrays and `{ items: [...] }` envelopes).
- Runtime schema validation throwing typed `ValidationError` on malformed payloads.

---

## 🐍 Task B – Python / FastAPI REST API

Located in `task-b-fastapi/app/`.

### 1. Endpoints

| Method | Path | Summary | Auth Required | Description |
|---|---|---|---|---|
| `POST` | `/tasks` | Create Task | Manager | Creates a task for the manager's company. Validates assignee belongs to same company. |
| `GET` | `/tasks` | Retrieve Tasks | Manager / Employee | Retrieves tasks strictly within user's company. Calculates completion metrics. |
| `PATCH` | `/tasks/{id}` | Update Task Status | Assigned Employee / Manager | Updates status. Enforces valid lifecycle transitions and RBAC permissions. |
| `GET` | `/health` | Health Check | Public | Returns service health status. |

### 2. HTTP Status Code Conventions
- `201 Created`: Successfully created a new task.
- `200 OK`: Successful retrieval or update.
- `400 Bad Request`: Business rule violation (e.g. cross-company assignment) or illegal status transition.
- `401 Unauthorized`: Missing or invalid authentication credentials (`X-User-Id`).
- `403 Forbidden`: Insufficient role permissions (e.g. employee attempting to create task) or tenant header mismatch.
- `404 Not Found`: Task does not exist **or belongs to another tenant** (anti-enumeration).
- `422 Unprocessable Entity`: Pydantic payload validation failure (e.g. blank title, invalid enum).

### 3. Separation of Concerns
The FastAPI application adheres to strict layered architecture:
- **Routes (`api/v1/tasks.py`)**: Thin HTTP transport layer handling HTTP status codes, query parameters, and response serialization.
- **Dependencies (`api/deps.py`)**: Injects authenticated `AuthUser` and `TaskService`.
- **Services (`services/task_service.py`)**: Encapsulates business logic, RBAC, tenant isolation, and task state machine.
- **Repositories (`repositories/task_repository.py`)**: Data access layer enforcing tenant filtering on every query.
- **Schemas (`schemas/task.py`)**: Pydantic v2 validation models.

---

## 🐘 Task C – Supabase / PostgreSQL Database & RLS

Located in `task-c-database/`.

### 1. Relational Schema (`schema.sql`)
- **Entities**:
  - `companies`: Primary tenant table (`id`, `name`, `created_at`, `updated_at`).
  - `users`: Employees & managers scoped by `company_id`.
  - `tasks`: Tasks scoped by `company_id`, `created_by`, `assigned_to`.
- **Composite Foreign Key Guarantee**:
  ```sql
  CONSTRAINT fk_tasks_assigned_to_company_user
      FOREIGN KEY (company_id, assigned_to)
      REFERENCES users(company_id, id)
      ON DELETE SET NULL
  ```
  *This constraint physically prohibits a task in Company A from being assigned to an employee in Company B at the database schema level.*

### 2. Row Level Security (`rls.sql`)
- Enabled with `FORCE ROW LEVEL SECURITY` on all tenant tables.
- Helper functions:
  - `get_current_user_company_id()`: Extracts tenant UUID from JWT claims or user record with `SECURITY DEFINER` and `STABLE` caching.
  - `is_company_manager()`: Verifies if the authenticated user has the `manager` role.
- Policies:
  - **SELECT**: Managers view all tasks in their company; Employees view assigned tasks.
  - **INSERT**: Only managers can insert tasks within their verified company.
  - **UPDATE**: Managers can update any company task; Employees can update their assigned tasks.
  - **DELETE**: Only managers can delete tasks within their company.

### 3. Optimized Queries (`queries.sql`)
- **Fetch Tasks by Company**: Parameterized query joining assignee and creator details.
- **Count Completed & Pending**: Uses PostgreSQL conditional aggregation:
  ```sql
  SELECT
      COUNT(*) AS total_tasks,
      COUNT(*) FILTER (WHERE status = 'completed') AS completed_tasks,
      COUNT(*) FILTER (WHERE status = 'pending') AS pending_tasks,
      ROUND((COUNT(*) FILTER (WHERE status = 'completed')::NUMERIC / NULLIF(COUNT(*), 0)) * 100, 2) AS completion_percentage
  FROM tasks
  WHERE company_id = :company_id;
  ```

---

## 🛡️ Multi-Tenant Data Security & Anti-Tampering

For complete technical documentation, see [`task-c-database/security_architecture.md`](file:///task-c-database/security_architecture.md).

### How the system prevents cross-tenant access if a user manipulates parameters:

1. **Zero Client Trust for Tenant Keys**:
   The API does **not** accept `company_id` in request bodies (`TaskCreate`). Tenant identity is derived exclusively from the verified server-side authentication context (`AuthUser.company_id`).
2. **Anti-Spoofing Header Guard**:
   If a client injects a custom `X-Company-Id` header that contradicts their authenticated identity, the request is terminated with `403 Forbidden`.
3. **Defense Against IDOR (Insecure Direct Object References)**:
   When modifying or fetching `/tasks/{id}`, the repository executes:
   ```python
   task = repo.get_by_id(task_id=id, company_id=user.company_id)
   ```
   If an attacker in Company A provides an ID belonging to Company B, the query returns `None`, resulting in a **404 Not Found**. This prevents attackers from enumerating valid IDs across other companies.
4. **Database-Level Row Level Security (RLS)**:
   Even in the event of an application-layer bug or direct SQL execution, PostgreSQL RLS silently filters out all rows where `company_id != get_current_user_company_id()`.

---

## 🚀 Setup & Installation

### Prerequisites
- **Node.js** v20+ / v22+ / v24+
- **Python** 3.10+ (tested on Python 3.14)
- **PostgreSQL 14+** (or Supabase instance)

### 1. Clone & TypeScript Setup
```powershell
# Install Node dependencies
npm install

# Build TypeScript
npm run build:ts
```

### 2. Python / FastAPI Setup
```powershell
# Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Windows
# source .venv/bin/activate     # On Linux / macOS

# Install Python requirements
pip install -r task-b-fastapi/requirements.txt
```

### 3. Run the FastAPI Development Server
```powershell
$env:PYTHONPATH="task-b-fastapi"
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```
Interactive API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 🧪 Running Test Suites

Both test suites are automated and require no external services or live databases.

### Run TypeScript Tests (Task A)
```powershell
npm run test:ts
```
**Expected Output:**
```
✔ Task A: TypeScript Task Management Module
  ✔ filterTasksByStatus()
  ✔ calculateCompletionPercentage()
  ✔ fetchTasks()
ℹ tests 18
ℹ pass 18
ℹ fail 0
```

### Run FastAPI Pytest Suite (Task B)
```powershell
$env:PYTHONPATH="task-b-fastapi"
.\.venv\Scripts\pytest.exe -v task-b-fastapi/tests
```
**Expected Output:**
```
task-b-fastapi/tests/test_tasks_api.py::test_unauthenticated_request_rejected PASSED
task-b-fastapi/tests/test_tasks_api.py::test_invalid_user_rejected PASSED
task-b-fastapi/tests/test_tasks_api.py::test_spoofed_company_header_rejected PASSED
task-b-fastapi/tests/test_tasks_api.py::test_manager_can_create_task PASSED
task-b-fastapi/tests/test_tasks_api.py::test_employee_cannot_create_task PASSED
task-b-fastapi/tests/test_tasks_api.py::test_manager_cannot_assign_task_to_different_company_employee PASSED
task-b-fastapi/tests/test_tasks_api.py::test_create_task_validation_error PASSED
task-b-fastapi/tests/test_tasks_api.py::test_tenant_data_isolation_between_companies PASSED
task-b-fastapi/tests/test_tasks_api.py::test_get_tasks_metrics_calculation PASSED
task-b-fastapi/tests/test_tasks_api.py::test_get_tasks_filter_by_status PASSED
task-b-fastapi/tests/test_tasks_api.py::test_get_tasks_filter_by_assignee PASSED
task-b-fastapi/tests/test_tasks_api.py::test_assigned_employee_can_update_task_status PASSED
task-b-fastapi/tests/test_tasks_api.py::test_unassigned_employee_cannot_update_task PASSED
task-b-fastapi/tests/test_tasks_api.py::test_manager_can_update_any_task_in_their_company PASSED
task-b-fastapi/tests/test_tasks_api.py::test_cross_tenant_patch_manipulation_returns_404 PASSED
task-b-fastapi/tests/test_tasks_api.py::test_employee_cannot_reopen_completed_task PASSED
task-b-fastapi/tests/test_tasks_api.py::test_invalid_status_enum_rejected PASSED
======================== 17 passed in 0.14s ========================
```

---

## 📄 License & Attribution

Designed and implemented for the Multi-Tenant Task Management API technical assessment. Clean-room implementation with zero external proprietary code.

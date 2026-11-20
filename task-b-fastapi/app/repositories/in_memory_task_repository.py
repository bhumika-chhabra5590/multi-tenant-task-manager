"""
In-Memory Task Repository (Test Double)
Used for fast, isolated unit tests without requiring a live Supabase connection.
Uses real UUIDs matching task-c-database/seed.sql.
"""

import threading
from datetime import datetime, timezone
from typing import Optional
from app.models.domain import TaskEntity
from app.schemas.task import TaskStatus, TaskPriority

# Pre-seeded test users mapping profile UUID to company UUID
TEST_PROFILES = {
    "a1111111-1111-1111-1111-111111111111": "a0000000-0000-0000-0000-000000000001",  # Alice (Mgr Alpha)
    "a2222222-2222-2222-2222-222222222222": "a0000000-0000-0000-0000-000000000001",  # Bob (Emp Alpha)
    "a3333333-3333-3333-3333-333333333333": "a0000000-0000-0000-0000-000000000001",  # Carol (Emp Alpha)
    "b1111111-1111-1111-1111-111111111111": "b0000000-0000-0000-0000-000000000002",  # David (Mgr Beta)
    "b2222222-2222-2222-2222-222222222222": "b0000000-0000-0000-0000-000000000002",  # Eve (Emp Beta)
}


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskEntity] = {}
        self.reset()

    def reset(self) -> None:
        """Resets repository data to default seed tasks."""
        with self._lock:
            self._tasks.clear()
            seed_tasks = [
                TaskEntity(
                    id="a1000000-0000-0000-0000-000000000001",
                    company_id="a0000000-0000-0000-0000-000000000001",
                    title="Setup PostgreSQL RLS",
                    description="Implement row level security policies for multi-tenancy",
                    status=TaskStatus.COMPLETED,
                    priority=TaskPriority.HIGH,
                    created_by="a1111111-1111-1111-1111-111111111111",
                    assigned_to="a2222222-2222-2222-2222-222222222222",
                    created_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
                ),
                TaskEntity(
                    id="a1000000-0000-0000-0000-000000000002",
                    company_id="a0000000-0000-0000-0000-000000000001",
                    title="Implement TypeScript Helpers",
                    description="Filter by status and calculate completion percentage",
                    status=TaskStatus.IN_PROGRESS,
                    priority=TaskPriority.MEDIUM,
                    created_by="a1111111-1111-1111-1111-111111111111",
                    assigned_to="a2222222-2222-2222-2222-222222222222",
                    created_at=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc),
                ),
                TaskEntity(
                    id="a1000000-0000-0000-0000-000000000003",
                    company_id="a0000000-0000-0000-0000-000000000001",
                    title="Run Security Audit",
                    description="Test cross-tenant tampering and verify role checks",
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.URGENT,
                    created_by="a1111111-1111-1111-1111-111111111111",
                    assigned_to="a3333333-3333-3333-3333-333333333333",
                    created_at=datetime(2026, 11, 3, 8, 30, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 11, 3, 8, 30, tzinfo=timezone.utc),
                ),
                # Separate tenant: Company Beta
                TaskEntity(
                    id="b1000000-0000-0000-0000-000000000001",
                    company_id="b0000000-0000-0000-0000-000000000002",
                    title="Beta Marketing Campaign",
                    description="Confidential launch strategy for Company Beta",
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.HIGH,
                    created_by="b1111111-1111-1111-1111-111111111111",
                    assigned_to="b2222222-2222-2222-2222-222222222222",
                    created_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
                    updated_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
                ),
            ]
            for task in seed_tasks:
                self._tasks[task.id] = task

    def create(self, task: TaskEntity, access_token: str = "") -> TaskEntity:
        with self._lock:
            self._tasks[task.id] = task
            return task

    def get_by_id(
        self, task_id: str, company_id: str, access_token: str = ""
    ) -> Optional[TaskEntity]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.company_id == company_id:
                return task
            return None

    def list_by_company(
        self,
        company_id: str,
        status: Optional[TaskStatus] = None,
        assigned_to: Optional[str] = None,
        access_token: str = "",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TaskEntity]:
        with self._lock:
            results = [
                task for task in self._tasks.values()
                if task.company_id == company_id
            ]

            if status is not None:
                results = [t for t in results if t.status == status]

            if assigned_to is not None:
                results = [t for t in results if t.assigned_to == assigned_to]

            sorted_results = sorted(results, key=lambda t: t.created_at, reverse=True)

            if offset is not None and offset > 0:
                sorted_results = sorted_results[offset:]

            if limit is not None and limit > 0:
                sorted_results = sorted_results[:limit]

            return sorted_results

    def update_status(
        self,
        task_id: str,
        company_id: str,
        new_status: TaskStatus,
        access_token: str = "",
    ) -> TaskEntity:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.company_id != company_id:
                raise ValueError(f"Task '{task_id}' not found in company '{company_id}'.")
            task.status = new_status
            task.updated_at = datetime.now(timezone.utc)
            self._tasks[task.id] = task
            return task

    def user_exists_in_company(
        self, user_id: str, company_id: str, access_token: str = ""
    ) -> bool:
        return TEST_PROFILES.get(user_id) == company_id

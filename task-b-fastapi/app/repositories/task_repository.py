import threading
from datetime import datetime, timezone
from typing import Optional
from app.core.auth import SEED_USERS
from app.models.domain import TaskEntity
from app.schemas.task import TaskStatus, TaskPriority


class TaskRepository:
    """
    Thread-safe repository for task management with multi-tenant scoping.
    Every query enforces tenant isolation by requiring company_id.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskEntity] = {}
        self._seed_default_data()

    def _seed_default_data(self) -> None:
        """Seed initial tasks across multiple companies to verify tenant boundaries."""
        sample_tasks = [
            TaskEntity(
                id="task_alpha_101",
                company_id="comp_alpha",
                title="Design PostgreSQL Schema & RLS",
                description="Create tables for companies, users, and tasks with security policies",
                status=TaskStatus.COMPLETED,
                priority=TaskPriority.HIGH,
                created_by="usr_mgr_alpha",
                assigned_to="usr_emp_alpha_1",
                created_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
            ),
            TaskEntity(
                id="task_alpha_102",
                company_id="comp_alpha",
                title="Implement TypeScript Helpers",
                description="Filter by status and calculate completion percentage",
                status=TaskStatus.IN_PROGRESS,
                priority=TaskPriority.MEDIUM,
                created_by="usr_mgr_alpha",
                assigned_to="usr_emp_alpha_1",
                created_at=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc),
            ),
            TaskEntity(
                id="task_alpha_103",
                company_id="comp_alpha",
                title="Run Security Audit",
                description="Test cross-tenant tampering and verify role checks",
                status=TaskStatus.PENDING,
                priority=TaskPriority.URGENT,
                created_by="usr_mgr_alpha",
                assigned_to="usr_emp_alpha_2",
                created_at=datetime(2026, 11, 3, 8, 30, tzinfo=timezone.utc),
                updated_at=datetime(2026, 11, 3, 8, 30, tzinfo=timezone.utc),
            ),
            # Separate tenant: Company Beta
            TaskEntity(
                id="task_beta_201",
                company_id="comp_beta",
                title="Beta Marketing Campaign",
                description="Confidential launch strategy for Company Beta",
                status=TaskStatus.PENDING,
                priority=TaskPriority.HIGH,
                created_by="usr_mgr_beta",
                assigned_to="usr_emp_beta_1",
                created_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
            ),
        ]
        for task in sample_tasks:
            self._tasks[task.id] = task

    def create(self, task: TaskEntity) -> TaskEntity:
        with self._lock:
            self._tasks[task.id] = task
            return task

    def get_by_id(self, task_id: str, company_id: str) -> Optional[TaskEntity]:
        """
        Retrieves a task strictly within the specified company_id.
        Returns None if task does not exist OR belongs to another tenant.
        """
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
    ) -> list[TaskEntity]:
        """
        Retrieves all tasks strictly matching the tenant's company_id,
        with optional filters for status and assignee.
        """
        with self._lock:
            results = [
                task for task in self._tasks.values()
                if task.company_id == company_id
            ]

            if status is not None:
                results = [task for task in results if task.status == status]

            if assigned_to is not None:
                results = [task for task in results if task.assigned_to == assigned_to]

            # Return sorted by created_at descending
            return sorted(results, key=lambda t: t.created_at, reverse=True)

    def update(self, task: TaskEntity) -> TaskEntity:
        with self._lock:
            task.updated_at = datetime.now(timezone.utc)
            self._tasks[task.id] = task
            return task

    def user_exists_in_company(self, user_id: str, company_id: str) -> bool:
        """Verifies if an assignee exists and belongs to the given company."""
        user = SEED_USERS.get(user_id)
        if not user:
            return False
        return user.company_id == company_id


# Global singleton repository instance
task_repository = TaskRepository()

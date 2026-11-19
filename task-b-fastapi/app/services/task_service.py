import uuid
from datetime import datetime, timezone
from typing import Optional
from app.core.auth import AuthUser, UserRole
from app.core.exceptions import (
    EntityNotFoundError,
    ForbiddenActionError,
    BusinessRuleViolationError,
    InvalidStateTransitionError,
)
from app.models.domain import TaskEntity
from app.repositories.task_repository import TaskRepository, task_repository
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskStatus,
)


class TaskService:
    """
    Business logic layer for multi-tenant task management.
    Enforces RBAC rules, tenant isolation boundaries, and status transitions.
    """

    def __init__(self, repo: TaskRepository = task_repository) -> None:
        self.repo = repo

    def create_task(self, user: AuthUser, payload: TaskCreate) -> TaskEntity:
        """
        Creates a task within the authenticated user's company tenant.
        
        Business Rules:
        - Only Managers can create and assign tasks.
        - Assignees must belong to the exact same company.
        """
        if user.role != UserRole.MANAGER:
            raise ForbiddenActionError("Only managers are authorized to create tasks.")

        # If assignee specified, enforce company membership
        if payload.assigned_to:
            if not self.repo.user_exists_in_company(payload.assigned_to, user.company_id):
                raise BusinessRuleViolationError(
                    f"Assignee '{payload.assigned_to}' does not exist within company '{user.company_id}'."
                )

        new_task = TaskEntity(
            id=f"task_{uuid.uuid4().hex[:12]}",
            company_id=user.company_id,
            title=payload.title,
            description=payload.description,
            status=TaskStatus.PENDING,
            priority=payload.priority,
            created_by=user.id,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        return self.repo.create(new_task)

    def get_tasks(
        self,
        user: AuthUser,
        status: Optional[TaskStatus] = None,
        assigned_to: Optional[str] = None,
    ) -> TaskListResponse:
        """
        Retrieves tasks scoped strictly to the authenticated user's company tenant.
        Calculates completion metrics and counts.
        """
        tasks = self.repo.list_by_company(
            company_id=user.company_id,
            status=status,
            assigned_to=assigned_to,
        )

        total = len(tasks)
        completed_count = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        pending_count = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        completion_percentage = (
            round((completed_count / total) * 100, 2) if total > 0 else 0.0
        )

        items = [TaskResponse.model_validate(t) for t in tasks]

        return TaskListResponse(
            items=items,
            total=total,
            completed_count=completed_count,
            pending_count=pending_count,
            completion_percentage=completion_percentage,
        )

    def update_task_status(
        self,
        user: AuthUser,
        task_id: str,
        new_status: TaskStatus,
    ) -> TaskEntity:
        """
        Updates task status with state transition validation and permission checks.
        
        Business Rules:
        - Scoped strictly to company: 404 returned if task belongs to another company.
        - Managers can update any task within their company.
        - Employees can only update tasks assigned directly to them.
        - Enforces valid status state transitions.
        """
        task = self.repo.get_by_id(task_id=task_id, company_id=user.company_id)
        if not task:
            raise EntityNotFoundError(entity_name="Task", entity_id=task_id)

        # RBAC Check: Employees can only update tasks assigned to them
        if user.role == UserRole.EMPLOYEE and task.assigned_to != user.id:
            raise ForbiddenActionError(
                f"Forbidden: Employee '{user.id}' is only permitted to update tasks assigned to them."
            )

        # Validate Status Transitions
        if task.status != new_status:
            self._validate_status_transition(task.status, new_status, user.role)
            task.status = new_status

        return self.repo.update(task)

    @staticmethod
    def _validate_status_transition(
        current_status: TaskStatus,
        target_status: TaskStatus,
        user_role: UserRole,
    ) -> None:
        """
        Finite state machine validation for task lifecycles:
        
        [PENDING]     --> [IN_PROGRESS], [CANCELLED]
        [IN_PROGRESS] --> [COMPLETED], [PENDING], [CANCELLED]
        [COMPLETED]   --> [IN_PROGRESS] (Reopening requires Manager role)
        [CANCELLED]   --> [PENDING]     (Reactivation requires Manager role)
        """
        if current_status == TaskStatus.COMPLETED:
            if target_status == TaskStatus.IN_PROGRESS:
                if user_role != UserRole.MANAGER:
                    raise ForbiddenActionError("Only managers can reopen completed tasks.")
            else:
                raise InvalidStateTransitionError(
                    current_status.value,
                    target_status.value,
                    reason="Completed tasks can only be transitioned back to in_progress by a manager.",
                )

        elif current_status == TaskStatus.CANCELLED:
            if target_status == TaskStatus.PENDING:
                if user_role != UserRole.MANAGER:
                    raise ForbiddenActionError("Only managers can reactivate cancelled tasks.")
            else:
                raise InvalidStateTransitionError(
                    current_status.value,
                    target_status.value,
                    reason="Cancelled tasks can only be reactivated to pending by a manager.",
                )


# Global singleton service
task_service = TaskService()

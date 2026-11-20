"""
Task Business Logic Service Layer
Enforces multi-tenant isolation, Role-Based Access Control (RBAC),
and task lifecycle finite state machine rules.
"""

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
from app.repositories.task_repository import TaskRepository
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskStatus,
)


class TaskService:
    """
    Business logic layer for multi-tenant task management.
    Enforces RBAC rules, tenant boundaries, and status transitions.
    """

    def __init__(self, repo: TaskRepository) -> None:
        self.repo: TaskRepository = repo

    def create_task(self, user: AuthUser, payload: TaskCreate) -> TaskEntity:
        """
        Creates a task within the authenticated user's company tenant.
        
        Business Rules:
        - Only Managers can create and assign tasks.
        - Assignees must belong to the exact same company.
        - created_by is derived from user.profile_id.
        """
        if user.role != UserRole.MANAGER:
            raise ForbiddenActionError("Only managers are authorized to create tasks.")

        # If assignee specified, enforce that they belong to the same company
        if payload.assigned_to:
            if not self.repo.user_exists_in_company(
                payload.assigned_to, user.company_id, user.access_token
            ):
                raise BusinessRuleViolationError(
                    f"Assignee '{payload.assigned_to}' does not exist within company '{user.company_id}'."
                )

        new_task = TaskEntity(
            id=str(uuid.uuid4()),
            company_id=user.company_id,
            title=payload.title,
            description=payload.description,
            status=TaskStatus.PENDING,
            priority=payload.priority,
            created_by=user.profile_id,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        return self.repo.create(new_task, access_token=user.access_token)

    def get_tasks(
        self,
        user: AuthUser,
        status: Optional[TaskStatus] = None,
        assigned_to: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TaskListResponse:
        """
        Retrieves tasks scoped strictly to the authenticated user's company tenant.
        
        Security & Visibility Rules:
        - Managers see all tasks in their company (and can filter by assigned_to).
        - Employees see ONLY tasks assigned to their profile_id.
        - Parameter manipulation defense: If an employee supplies assigned_to, it is ignored
          and forced to user.profile_id so employees can never view others' tasks.
        """
        effective_assigned_to: Optional[str]
        if user.role == UserRole.EMPLOYEE:
            effective_assigned_to = user.profile_id
        else:
            effective_assigned_to = assigned_to

        tasks = self.repo.list_by_company(
            company_id=user.company_id,
            status=status,
            assigned_to=effective_assigned_to,
            access_token=user.access_token,
            limit=limit,
            offset=offset,
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
        
        Security Rules:
        - Scoped strictly to company: 404 returned if task belongs to another company.
        - Under RLS, unassigned tasks are hidden from employees at SELECT time.
          Therefore, an unassigned task consistently returns 404 Not Found to prevent
          resource existence enumeration.
        - Managers can update any task within their company.
        - Enforces valid status state transitions.
        """
        task = self.repo.get_by_id(
            task_id=task_id,
            company_id=user.company_id,
            access_token=user.access_token,
        )
        if not task:
            raise EntityNotFoundError(entity_name="Task", entity_id=task_id)

        # RBAC Check: Employees can only update tasks assigned to them.
        # Returning 404 prevents leaking whether a task exists in the company.
        if user.role == UserRole.EMPLOYEE and task.assigned_to != user.profile_id:
            raise EntityNotFoundError(entity_name="Task", entity_id=task_id)

        # Validate Status Transitions
        if task.status != new_status:
            self._validate_status_transition(task.status, new_status, user.role)

        return self.repo.update_status(
            task_id=task_id,
            company_id=user.company_id,
            new_status=new_status,
            access_token=user.access_token,
        )

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

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from app.api.deps import get_current_user, get_task_service
from app.core.auth import AuthUser
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskStatus,
    TaskUpdateStatus,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    description="Allows managers to create and assign tasks within their company tenant.",
)
def create_task(
    payload: TaskCreate,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    task = service.create_task(user=current_user, payload=payload)
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve tasks",
    description="Fetches tasks belonging strictly to the authenticated user's company.",
)
def get_tasks(
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
    task_status: Optional[TaskStatus] = Query(
        default=None,
        alias="status",
        description="Filter tasks by status",
    ),
    assigned_to: Optional[str] = Query(
        default=None,
        description="Filter tasks by assigned user ID",
    ),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=100,
        description="Pagination limit",
    ),
    offset: Optional[int] = Query(
        default=None,
        ge=0,
        description="Pagination offset",
    ),
) -> TaskListResponse:
    return service.get_tasks(
        user=current_user,
        status=task_status,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update task status",
    description="Updates task status. Employees can only update their assigned tasks; managers can update any task in their company.",
)
def update_task_status(
    id: str,
    payload: TaskUpdateStatus,
    current_user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskResponse:
    task = service.update_task_status(
        user=current_user,
        task_id=id,
        new_status=payload.status,
    )
    return TaskResponse.model_validate(task)

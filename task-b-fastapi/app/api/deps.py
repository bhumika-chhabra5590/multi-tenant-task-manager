from typing import Annotated
from fastapi import Depends
from app.core.auth import AuthUser, authenticate_request
from app.services.task_service import TaskService, task_service


def get_current_user(
    user: Annotated[AuthUser, Depends(authenticate_request)],
) -> AuthUser:
    """Dependency that extracts and validates the authenticated multi-tenant user."""
    return user


def get_task_service() -> TaskService:
    """Dependency injecting the TaskService instance."""
    return task_service

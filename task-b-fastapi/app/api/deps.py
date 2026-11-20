from typing import Annotated
from fastapi import Depends
from app.core.auth import AuthUser, authenticate_bearer_token
from app.repositories.task_repository import TaskRepository, get_default_repository
from app.services.task_service import TaskService


def get_current_user(
    user: Annotated[AuthUser, Depends(authenticate_bearer_token)],
) -> AuthUser:
    """Dependency extracting and validating the authenticated multi-tenant user from Bearer JWT."""
    return user


def get_task_service(
    repo: Annotated[TaskRepository, Depends(get_default_repository)],
) -> TaskService:
    """Dependency injecting TaskService initialized with the active repository."""
    return TaskService(repo=repo)

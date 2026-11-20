"""
Repository Provider & Protocols
Defines the repository interface and supplies the active production repository.
SupabaseTaskRepository is the ONLY production repository.
InMemoryTaskRepository is strictly a test double, activated via explicit dependency overrides.
"""

from typing import Protocol, Optional
from app.config import settings
from app.core.supabase_client import SupabaseConfigurationError
from app.models.domain import TaskEntity
from app.schemas.task import TaskStatus
from app.repositories.supabase_task_repository import SupabaseTaskRepository
from app.repositories.in_memory_task_repository import InMemoryTaskRepository


class TaskRepository(Protocol):
    def create(self, task: TaskEntity, access_token: str) -> TaskEntity: ...
    def get_by_id(
        self, task_id: str, company_id: str, access_token: str
    ) -> Optional[TaskEntity]: ...
    def list_by_company(
        self,
        company_id: str,
        status: Optional[TaskStatus],
        assigned_to: Optional[str],
        access_token: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TaskEntity]: ...
    def update_status(
        self,
        task_id: str,
        company_id: str,
        new_status: TaskStatus,
        access_token: str,
    ) -> TaskEntity: ...
    def user_exists_in_company(
        self, user_id: str, company_id: str, access_token: str
    ) -> bool: ...


def get_default_repository() -> TaskRepository:
    """
    Supplies the production repository implementation.
    Fails safely if Supabase credentials are missing or unconfigured.
    Never silently falls back to in-memory data in production.
    """
    if not settings.is_supabase_configured:
        raise SupabaseConfigurationError(
            "Supabase is not configured. Please define SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env."
        )
    return SupabaseTaskRepository()

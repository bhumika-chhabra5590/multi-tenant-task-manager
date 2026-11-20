"""
Supabase PostgreSQL Task Repository
Executes multi-tenant database operations using a request-scoped Supabase client
with the caller's verified JWT Bearer token, enforcing Row Level Security (RLS).
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from app.core.exceptions import DomainException, EntityNotFoundError
from app.core.supabase_client import get_user_scoped_supabase_client
from app.models.domain import TaskEntity
from app.schemas.task import TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


class DatabaseOperationError(DomainException):
    """Raised when a Supabase PostgREST operation encounters an error."""
    pass


class SupabaseTaskRepository:
    """
    Production repository using Supabase PostgREST database operations.
    Every query forwards the authenticated user's token so PostgreSQL evaluates
    Row Level Security (RLS) policies at the database layer.
    """

    def create(self, task: TaskEntity, access_token: str) -> TaskEntity:
        client = get_user_scoped_supabase_client(access_token)
        payload = {
            "id": task.id,
            "company_id": task.company_id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority.value,
            "assigned_to": task.assigned_to,
            "created_by": task.created_by,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }

        try:
            res = client.table("tasks").insert(payload).execute()
            if not res.data:
                raise DatabaseOperationError("An internal database error occurred while creating the task.")
            return self._row_to_entity(res.data[0])
        except DomainException:
            raise
        except Exception as exc:
            logger.error("Failed to create task in Supabase: %s", exc, exc_info=True)
            raise DatabaseOperationError("An internal database error occurred while creating the task.")

    def get_by_id(
        self, task_id: str, company_id: str, access_token: str
    ) -> Optional[TaskEntity]:
        client = get_user_scoped_supabase_client(access_token)
        try:
            res = (
                client.table("tasks")
                .select("*")
                .eq("id", task_id)
                .eq("company_id", company_id)
                .execute()
            )
            if not res.data or len(res.data) == 0:
                return None
            return self._row_to_entity(res.data[0])
        except Exception as exc:
            logger.error("Failed to fetch task '%s' from Supabase: %s", task_id, exc, exc_info=True)
            raise DatabaseOperationError("An internal database error occurred while fetching the task.")

    def list_by_company(
        self,
        company_id: str,
        status: Optional[TaskStatus],
        assigned_to: Optional[str],
        access_token: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TaskEntity]:
        client = get_user_scoped_supabase_client(access_token)
        try:
            query = (
                client.table("tasks")
                .select("*")
                .eq("company_id", company_id)
            )

            if status is not None:
                query = query.eq("status", status.value)

            if assigned_to is not None:
                query = query.eq("assigned_to", assigned_to)

            query = query.order("created_at", desc=True)

            if limit is not None and limit > 0:
                start = offset or 0
                end = start + limit - 1
                query = query.range(start, end)
            elif offset is not None and offset > 0:
                query = query.range(offset, offset + 999)

            res = query.execute()

            return [self._row_to_entity(row) for row in res.data]
        except Exception as exc:
            logger.error("Failed to list tasks for company '%s' from Supabase: %s", company_id, exc, exc_info=True)
            raise DatabaseOperationError("An internal database error occurred while retrieving tasks.")

    def update_status(
        self,
        task_id: str,
        company_id: str,
        new_status: TaskStatus,
        access_token: str,
    ) -> TaskEntity:
        client = get_user_scoped_supabase_client(access_token)
        now_utc = datetime.now(timezone.utc)
        payload = {
            "status": new_status.value,
            "updated_at": now_utc.isoformat(),
        }

        try:
            res = (
                client.table("tasks")
                .update(payload)
                .eq("id", task_id)
                .eq("company_id", company_id)
                .execute()
            )
            if not res.data or len(res.data) == 0:
                logger.warning("Task update returned 0 rows for task '%s' in company '%s'", task_id, company_id)
                raise EntityNotFoundError("Task", task_id)
            return self._row_to_entity(res.data[0])
        except DomainException:
            raise
        except Exception as exc:
            logger.error("Failed to update task '%s' status in Supabase: %s", task_id, exc, exc_info=True)
            raise DatabaseOperationError("An internal database error occurred while updating the task.")

    def user_exists_in_company(
        self, user_id: str, company_id: str, access_token: str
    ) -> bool:
        client = get_user_scoped_supabase_client(access_token)
        try:
            res = (
                client.table("users")
                .select("id")
                .eq("id", user_id)
                .eq("company_id", company_id)
                .execute()
            )
            return bool(res.data and len(res.data) > 0)
        except Exception as exc:
            logger.error("Database query failed verifying user existence in company: %s", exc, exc_info=True)
            raise DatabaseOperationError("An internal database error occurred while verifying user organization membership.")

    @staticmethod
    def _row_to_entity(row: dict) -> TaskEntity:
        created_at = (
            datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if isinstance(row["created_at"], str)
            else row["created_at"]
        )
        updated_at = (
            datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
            if isinstance(row["updated_at"], str)
            else row["updated_at"]
        )
        due_date = None
        if row.get("due_date"):
            due_date = (
                datetime.fromisoformat(row["due_date"].replace("Z", "+00:00"))
                if isinstance(row["due_date"], str)
                else row["due_date"]
            )

        return TaskEntity(
            id=str(row["id"]),
            company_id=str(row["company_id"]),
            title=row["title"],
            description=row.get("description"),
            status=TaskStatus(row["status"]),
            priority=TaskPriority(row["priority"]),
            created_by=str(row["created_by"]),
            assigned_to=str(row["assigned_to"]) if row.get("assigned_to") else None,
            due_date=due_date,
            created_at=created_at,
            updated_at=updated_at,
        )

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from app.core.auth import UserRole
from app.schemas.task import TaskStatus, TaskPriority


@dataclass
class CompanyEntity:
    id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserEntity:
    id: str
    company_id: str
    email: str
    full_name: str
    role: UserRole
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskEntity:
    id: str
    company_id: str
    title: str
    status: TaskStatus
    priority: TaskPriority
    created_by: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

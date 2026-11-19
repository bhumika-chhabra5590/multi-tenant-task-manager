from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(default=None, max_length=2000, description="Task details")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Priority level")
    assigned_to: Optional[str] = Field(default=None, description="User ID of assignee within same company")
    due_date: Optional[datetime] = Field(default=None, description="Target completion timestamp (UTC)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Task title cannot be empty or whitespace only")
        return trimmed


class TaskUpdateStatus(BaseModel):
    status: TaskStatus = Field(..., description="Target status for task update")


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    assigned_to: Optional[str]
    created_by: str
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    completed_count: int
    pending_count: int
    completion_percentage: float

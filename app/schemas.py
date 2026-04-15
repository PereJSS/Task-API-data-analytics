from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["pending", "in_progress", "blocked", "completed", "cancelled"]


class TaskBase(BaseModel):
    """Shared fields used by both input and output task models."""

    title: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    created_by: Optional[str] = Field(default=None, max_length=120)
    assigned_to: Optional[str] = Field(default=None, max_length=120)
    status: TaskStatus = "pending"
    completed: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title no puede estar vacio")
        return stripped


class TaskCreate(TaskBase):
    """Payload required to create a new task."""

    pass


class TaskUpdate(BaseModel):
    """Partial update payload so clients can patch only the fields they need."""

    title: Optional[str] = Field(default=None, min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    created_by: Optional[str] = Field(default=None, max_length=120)
    assigned_to: Optional[str] = Field(default=None, max_length=120)
    status: Optional[TaskStatus] = None
    completed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_optional_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("title no puede estar vacio")
        return stripped


class TaskResponse(TaskBase):
    """API response model returned for task resources."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    completion_time_minutes: Optional[int]
    archived: bool
    created_at: datetime
    updated_at: datetime


class TaskStats(BaseModel):
    """Aggregate counters used by analytics views and summary cards."""

    total: int
    completed: int
    pending: int
    in_progress: int
    blocked: int
    cancelled: int
    archived: int
    avg_completion_minutes: Optional[float]

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    title = Column(String(120), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    created_by = Column(String(120), nullable=True, index=True)
    assigned_to = Column(String(120), nullable=True, index=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    completed = Column(Boolean, default=False, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completion_time_minutes = Column(Integer, nullable=True)
    archived = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import TaskDB
from app.schemas import TaskCreate, TaskStats, TaskUpdate

COMPLETED_STATUS = "completed"
PENDING_STATUS = "pending"


def _sync_completion_fields(db_task: TaskDB, was_completed: bool) -> None:
    """Keep status, completion timestamps and duration consistent after any write."""
    if db_task.completed:
        if db_task.status != COMPLETED_STATUS:
            db_task.status = COMPLETED_STATUS

        if db_task.completed_at is None:
            db_task.completed_at = datetime.utcnow()

        start_reference = db_task.started_at or db_task.created_at
        if start_reference and db_task.completed_at and db_task.completed_at >= start_reference:
            delta = db_task.completed_at - start_reference
            db_task.completion_time_minutes = int(delta.total_seconds() // 60)
        else:
            db_task.completion_time_minutes = 0
        return

    if db_task.status == COMPLETED_STATUS:
        db_task.status = PENDING_STATUS

    if was_completed:
        db_task.completed_at = None
        db_task.completion_time_minutes = None


def create_task(db: Session, payload: TaskCreate) -> TaskDB:
    """Create a task and immediately normalize any completion-related fields."""
    db_task = TaskDB(id=str(uuid4()), **payload.model_dump())

    if db_task.status == COMPLETED_STATUS:
        db_task.completed = True

    _sync_completion_fields(db_task, was_completed=False)

    updated_candidates = [
        candidate
        for candidate in [db_task.created_at, db_task.started_at, db_task.completed_at]
        if candidate is not None
    ]
    if updated_candidates:
        db_task.updated_at = max(updated_candidates)

    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def get_task(db: Session, task_id: str, include_archived: bool = False) -> Optional[TaskDB]:
    """Fetch one task, optionally including soft-deleted records."""
    query = db.query(TaskDB).filter(TaskDB.id == task_id)
    if not include_archived:
        query = query.filter(TaskDB.archived.is_(False))
    return query.first()


def list_tasks(
    db: Session,
    completed: Optional[bool],
    status: Optional[str],
    assigned_to: Optional[str],
    search: Optional[str],
    include_archived: bool,
    limit: int,
    offset: int,
) -> List[TaskDB]:
    """Return a filtered, paginated task list ready for the API layer."""
    query = db.query(TaskDB)

    if not include_archived:
        query = query.filter(TaskDB.archived.is_(False))

    if completed is not None:
        query = query.filter(TaskDB.completed.is_(completed))

    if status:
        query = query.filter(TaskDB.status == status)

    if assigned_to:
        query = query.filter(TaskDB.assigned_to.ilike(f"%{assigned_to.strip()}%"))

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                TaskDB.title.ilike(term),
                TaskDB.description.ilike(term),
                TaskDB.created_by.ilike(term),
                TaskDB.assigned_to.ilike(term),
                TaskDB.status.ilike(term),
            )
        )

    return query.order_by(TaskDB.created_at.desc()).offset(offset).limit(limit).all()


def update_task(db: Session, db_task: TaskDB, payload: TaskUpdate) -> TaskDB:
    """Apply partial updates and recompute derived completion fields when needed."""
    was_completed = db_task.completed
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(db_task, key, value)

    if "status" in data and "completed" not in data:
        db_task.completed = db_task.status == COMPLETED_STATUS

    if "completed" in data and "status" not in data and db_task.completed:
        db_task.status = COMPLETED_STATUS

    _sync_completion_fields(db_task, was_completed=was_completed)

    db.commit()
    db.refresh(db_task)
    return db_task


def archive_task(db: Session, db_task: TaskDB) -> None:
    """Soft delete a task so it disappears from default listings without losing history."""
    db_task.archived = True
    db.commit()


def task_stats(db: Session) -> TaskStats:
    """Compute aggregate status metrics used by dashboards and summary endpoints."""
    total = db.query(func.count(TaskDB.id)).scalar() or 0
    completed = db.query(func.count(TaskDB.id)).filter(TaskDB.completed.is_(True)).scalar() or 0
    archived = db.query(func.count(TaskDB.id)).filter(TaskDB.archived.is_(True)).scalar() or 0

    grouped_status = dict(
        db.query(TaskDB.status, func.count(TaskDB.id))
        .group_by(TaskDB.status)
        .all()
    )

    avg_completion_minutes = (
        db.query(func.avg(TaskDB.completion_time_minutes))
        .filter(TaskDB.completion_time_minutes.is_not(None))
        .scalar()
    )

    return TaskStats(
        total=total,
        completed=completed,
        pending=grouped_status.get(PENDING_STATUS, 0),
        in_progress=grouped_status.get("in_progress", 0),
        blocked=grouped_status.get("blocked", 0),
        cancelled=grouped_status.get("cancelled", 0),
        archived=archived,
        avg_completion_minutes=(
            round(float(avg_completion_minutes), 2)
            if avg_completion_minutes is not None
            else None
        ),
    )

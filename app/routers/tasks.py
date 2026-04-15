from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import TaskCreate, TaskResponse, TaskStats, TaskStatus, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    """Create a task record."""
    return crud.create_task(db, payload)


@router.get("", response_model=List[TaskResponse])
def list_tasks(
    completed: Optional[bool] = Query(default=None),
    status: Optional[TaskStatus] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None, min_length=1, max_length=120),
    search: Optional[str] = Query(default=None, min_length=1, max_length=120),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List tasks with optional filters for status, assignee, search and archive visibility."""
    return crud.list_tasks(
        db=db,
        completed=completed,
        status=status,
        assigned_to=assigned_to,
        search=search,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Return one task by id or raise a 404 if it does not exist."""
    task = crud.get_task(db, task_id, include_archived=include_archived)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, payload: TaskUpdate, db: Session = Depends(get_db)):
    """Update an existing task using a partial payload."""
    db_task = crud.get_task(db, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not payload.model_dump(exclude_unset=True):
        raise HTTPException(status_code=400, detail="At least one field is required")

    return crud.update_task(db, db_task, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_task(task_id: str, db: Session = Depends(get_db)):
    """Soft delete a task."""
    db_task = crud.get_task(db, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    crud.archive_task(db, db_task)
    return None


@router.get("/stats/summary", response_model=TaskStats)
def get_stats(db: Session = Depends(get_db)):
    """Expose aggregate task counters for reporting clients."""
    return crud.task_stats(db)

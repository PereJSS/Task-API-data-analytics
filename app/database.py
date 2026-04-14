from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_tasks_schema() -> None:
    """Lightweight schema evolution for SQLite without Alembic."""
    with engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        ).fetchone()

        if not table_exists:
            return

        existing_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
        }

        alter_statements = {
            "created_by": "ALTER TABLE tasks ADD COLUMN created_by VARCHAR(120)",
            "assigned_to": "ALTER TABLE tasks ADD COLUMN assigned_to VARCHAR(120)",
            "status": "ALTER TABLE tasks ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'pending'",
            "started_at": "ALTER TABLE tasks ADD COLUMN started_at DATETIME",
            "completed_at": "ALTER TABLE tasks ADD COLUMN completed_at DATETIME",
            "completion_time_minutes": (
                "ALTER TABLE tasks ADD COLUMN completion_time_minutes INTEGER"
            ),
        }

        for column_name, statement in alter_statements.items():
            if column_name not in existing_columns:
                conn.execute(text(statement))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    if not settings.auto_init_db:
        return

    Base.metadata.create_all(bind=engine)
    ensure_tasks_schema()

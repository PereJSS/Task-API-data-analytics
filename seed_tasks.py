import random
from datetime import datetime, timedelta
from uuid import uuid4

from app.database import SessionLocal
from app.models import TaskDB

CREATORS = [
    "Ana",
    "Luis",
    "Marta",
    "Pere",
    "Carlos",
    "Nuria",
    "Elena",
    "Javier",
    "Raul",
    "Sofia",
]

ASSIGNEES = [
    "Equipo BI",
    "DataOps",
    "Analista 1",
    "Analista 2",
    "Backend 1",
    "Backend 2",
    "Product",
    "QA",
    "Infra",
    "Freelance",
]

TITLE_PREFIX = [
    "Implementar",
    "Revisar",
    "Automatizar",
    "Corregir",
    "Validar",
    "Documentar",
    "Optimizar",
    "Monitorizar",
    "Auditar",
    "Preparar",
]

TITLE_SUBJECT = [
    "pipeline de ventas",
    "informe semanal",
    "tablero de conversion",
    "integracion ERP",
    "modelo de forecasting",
    "dataset de clientes",
    "alertas de calidad",
    "API de tareas",
    "proceso ETL",
    "migracion de tablas",
]

DETAILS = [
    "Incluye validaciones y control de calidad",
    "Dependiente de aprobacion de negocio",
    "Coordinar con QA y DataOps",
    "Revisar impacto en reporting mensual",
    "Agregar trazabilidad para auditoria",
    "Requiere pruebas de carga y regresion",
    "Prioridad media con ventana de despliegue corta",
    "Alinear con requisitos del equipo comercial",
    "Agregar documentacion tecnica y funcional",
    "Pendiente de confirmacion de datos maestros",
]


def random_datetime(start: datetime, end: datetime) -> datetime:
    """Return a random timestamp inside the requested interval."""
    delta_seconds = int((end - start).total_seconds())
    if delta_seconds <= 0:
        return start
    return start + timedelta(seconds=random.randint(0, delta_seconds))


def build_task(now: datetime, period_start: datetime) -> TaskDB:
    """Build one realistic demo task with coherent status and duration fields."""
    created_at = random_datetime(period_start, now)
    title = f"{random.choice(TITLE_PREFIX)} {random.choice(TITLE_SUBJECT)}"
    description = random.choice(DETAILS)
    created_by = random.choice(CREATORS)
    assigned_to = random.choice(ASSIGNEES)

    status = random.choices(
        population=["completed", "in_progress", "pending", "blocked", "cancelled"],
        weights=[55, 18, 16, 7, 4],
        k=1,
    )[0]

    completed = status == "completed"
    archived = random.random() < 0.08

    started_at = None
    completed_at = None
    completion_time_minutes = None

    if status in {"completed", "in_progress", "blocked"}:
        started_at = created_at + timedelta(hours=random.randint(0, 96))

    if completed:
        # Resoluciones entre 30 minutos y 40 dias para variedad analitica.
        resolution_minutes = random.randint(30, 40 * 24 * 60)
        if started_at is None:
            started_at = created_at
        completed_at = started_at + timedelta(minutes=resolution_minutes)
        if completed_at > now:
            completed_at = now - timedelta(minutes=random.randint(1, 120))
        if completed_at < started_at:
            completed_at = started_at + timedelta(minutes=1)
        completion_time_minutes = int((completed_at - started_at).total_seconds() // 60)

    updated_candidates = [created_at]
    if started_at is not None:
        updated_candidates.append(started_at)
    if completed_at is not None:
        updated_candidates.append(completed_at)
    updated_at = max(updated_candidates)

    return TaskDB(
        id=str(uuid4()),
        title=title,
        description=description,
        created_by=created_by,
        assigned_to=assigned_to,
        status=status,
        completed=completed,
        started_at=started_at,
        completed_at=completed_at,
        completion_time_minutes=completion_time_minutes,
        archived=archived,
        created_at=created_at,
        updated_at=updated_at,
    )


def seed_tasks(task_count: int = 700) -> int:
    """Insert a batch of demo tasks spanning the last three years."""
    now = datetime.utcnow()
    period_start = now - timedelta(days=365 * 3)

    db = SessionLocal()
    try:
        tasks = [build_task(now=now, period_start=period_start) for _ in range(task_count)]
        db.add_all(tasks)
        db.commit()
        return len(tasks)
    finally:
        db.close()


if __name__ == "__main__":
    random.seed(42)
    # A fixed seed makes demo deployments reproducible and easier to reason about.
    inserted = seed_tasks(task_count=700)
    print(f"Inserted {inserted} tasks")
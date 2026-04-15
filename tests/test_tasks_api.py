import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TASKFLOW_DATABASE_URL", "sqlite:///./test_tasks.db")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings, settings
from app.database import SessionLocal, init_db
from app.main import app
from app.models import TaskDB

client = TestClient(app)


def setup_function():
    """Reset the test database before every test so assertions stay isolated."""
    settings.write_api_key = ""
    init_db()
    db = SessionLocal()
    try:
        db.query(TaskDB).delete()
        db.commit()
    finally:
        db.close()


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "TaskFlow API activa",
        "docs": "/docs",
        "health": "/health",
        "tasks": "/tasks",
    }


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_task():
    settings.write_api_key = "test-key"
    payload = {
        "title": "Preparar demo tecnica",
        "description": "API con filtros y metricas",
        "created_by": "Pere",
        "assigned_to": "Equipo Data",
        "status": "in_progress",
        "completed": False,
    }

    create_response = client.post("/tasks", json=payload, headers={"X-API-Key": "test-key"})
    assert create_response.status_code == 201

    created = create_response.json()
    task_id = created["id"]

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["title"] == payload["title"]
    assert data["created_by"] == payload["created_by"]
    assert data["assigned_to"] == payload["assigned_to"]
    assert data["status"] == payload["status"]


def test_create_task_accepts_historical_dates():
    settings.write_api_key = "test-key"
    payload = {
        "title": "Importar historico",
        "description": "Carga inicial",
        "created_by": "Pere",
        "assigned_to": "DataOps",
        "status": "completed",
        "completed": True,
        "created_at": "2024-01-10T09:00:00",
        "started_at": "2024-01-10T10:00:00",
        "completed_at": "2024-01-11T10:30:00",
        "archived": True,
    }

    response = client.post("/tasks", json=payload, headers={"X-API-Key": "test-key"})
    assert response.status_code == 201

    data = response.json()
    assert data["archived"] is True
    assert data["created_at"].startswith("2024-01-10T09:00:00")
    assert data["started_at"].startswith("2024-01-10T10:00:00")
    assert data["completed_at"].startswith("2024-01-11T10:30:00")
    assert data["completion_time_minutes"] == 1470


def test_archive_task_hides_from_default_list():
    settings.write_api_key = "test-key"
    create_response = client.post(
        "/tasks",
        json={"title": "Tarea temporal", "description": "A borrar", "completed": False},
        headers={"X-API-Key": "test-key"},
    )
    task_id = create_response.json()["id"]

    delete_response = client.delete(f"/tasks/{task_id}", headers={"X-API-Key": "test-key"})
    assert delete_response.status_code == 204

    list_response = client.get("/tasks")
    assert all(task["id"] != task_id for task in list_response.json())

    archived_response = client.get("/tasks", params={"include_archived": True})
    assert any(task["id"] == task_id for task in archived_response.json())


def test_complete_task_sets_resolution_metrics():
    settings.write_api_key = "test-key"
    create_response = client.post(
        "/tasks",
        json={
            "title": "Cerrar informe semanal",
            "description": "Pendiente de validar",
            "created_by": "Pere",
            "assigned_to": "Analista 1",
            "status": "in_progress",
            "completed": False,
        },
        headers={"X-API-Key": "test-key"},
    )
    task_id = create_response.json()["id"]

    update_response = client.put(
        f"/tasks/{task_id}",
        json={"completed": True},
        headers={"X-API-Key": "test-key"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["completed"] is True
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None
    assert updated["completion_time_minutes"] is not None
    assert updated["completion_time_minutes"] >= 0


def test_stats_return_real_pending_count():
    settings.write_api_key = "test-key"
    client.post(
        "/tasks",
        json={"title": "Pendiente", "status": "pending", "completed": False},
        headers={"X-API-Key": "test-key"},
    )
    client.post(
        "/tasks",
        json={"title": "Bloqueada", "status": "blocked", "completed": False},
        headers={"X-API-Key": "test-key"},
    )

    response = client.get("/tasks/stats/summary")
    assert response.status_code == 200
    stats = response.json()
    assert stats["pending"] == 1
    assert stats["blocked"] == 1


def test_normalize_database_url_strips_quotes_and_uses_psycopg_driver():
    normalized = Settings._normalize_database_url('"postgresql://user:secret@db.example.com:5432/postgres"')
    assert normalized == "postgresql+psycopg://user:secret@db.example.com:5432/postgres"


def test_normalize_database_url_rejects_placeholder_values():
    with pytest.raises(ValueError, match="marcadores de ejemplo"):
        Settings._normalize_database_url(
            "postgresql://postgres:[YOUR-PASSWORD]@db.example.com:5432/postgres"
        )


def test_write_operations_require_api_key_when_configured():
    settings.write_api_key = "secret-key"

    response = client.post(
        "/tasks",
        json={"title": "No permitida", "status": "pending", "completed": False},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"

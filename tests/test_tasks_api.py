import os

from fastapi.testclient import TestClient

os.environ.setdefault("TASKFLOW_DATABASE_URL", "sqlite:///./test_tasks.db")

from app.database import SessionLocal, init_db
from app.main import app
from app.models import TaskDB

client = TestClient(app)


def setup_function():
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
    payload = {
        "title": "Preparar demo tecnica",
        "description": "API con filtros y metricas",
        "created_by": "Pere",
        "assigned_to": "Equipo Data",
        "status": "in_progress",
        "completed": False,
    }

    create_response = client.post("/tasks", json=payload)
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


def test_archive_task_hides_from_default_list():
    create_response = client.post(
        "/tasks",
        json={"title": "Tarea temporal", "description": "A borrar", "completed": False},
    )
    task_id = create_response.json()["id"]

    delete_response = client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/tasks")
    assert all(task["id"] != task_id for task in list_response.json())

    archived_response = client.get("/tasks", params={"include_archived": True})
    assert any(task["id"] == task_id for task in archived_response.json())


def test_complete_task_sets_resolution_metrics():
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
    )
    task_id = create_response.json()["id"]

    update_response = client.put(
        f"/tasks/{task_id}",
        json={"completed": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["completed"] is True
    assert updated["status"] == "completed"
    assert updated["completed_at"] is not None
    assert updated["completion_time_minutes"] is not None
    assert updated["completion_time_minutes"] >= 0


def test_stats_return_real_pending_count():
    client.post(
        "/tasks",
        json={"title": "Pendiente", "status": "pending", "completed": False},
    )
    client.post(
        "/tasks",
        json={"title": "Bloqueada", "status": "blocked", "completed": False},
    )

    response = client.get("/tasks/stats/summary")
    assert response.status_code == 200
    stats = response.json()
    assert stats["pending"] == 1
    assert stats["blocked"] == 1

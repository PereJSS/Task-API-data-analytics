from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI

from app.database import init_db
from app.routers.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run one-time startup initialization before the app serves traffic."""
    init_db()
    yield

app = FastAPI(
    title="TaskFlow API",
    description="REST API profesional para gestion de tareas con FastAPI y SQLAlchemy.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", tags=["System"])
def root() -> Dict[str, str]:
    """Provide a simple landing payload for browsers and health checks."""
    return {
        "message": "TaskFlow API activa",
        "docs": "/docs",
        "health": "/health",
        "tasks": "/tasks",
    }


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """Return a minimal health response used by orchestrators and uptime checks."""
    return {"status": "ok"}


app.include_router(tasks_router)

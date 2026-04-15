import os

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings:
    """Centralize environment-driven settings and normalize them once at startup."""

    def __init__(self) -> None:
        self.environment = os.getenv("TASKFLOW_ENV", "development")
        raw_database_url = os.getenv("TASKFLOW_DATABASE_URL", "sqlite:///./tareas.db")
        self.database_url = self._normalize_database_url(raw_database_url)
        raw_api_base_url = os.getenv("TASKFLOW_API_BASE_URL", "http://127.0.0.1:8000")
        self.streamlit_api_base_url = self._normalize_http_url(raw_api_base_url)
        self.auto_init_db = os.getenv("TASKFLOW_AUTO_INIT_DB", "true").lower() == "true"

    @staticmethod
    def _normalize_database_url(database_url: str) -> str:
        """Translate shorthand Postgres URLs into the SQLAlchemy driver form used by the app."""
        normalized_url = database_url.strip().strip('"').strip("'")

        if normalized_url.startswith("postgres://"):
            normalized_url = normalized_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif normalized_url.startswith("postgresql://"):
            normalized_url = normalized_url.replace("postgresql://", "postgresql+psycopg://", 1)

        if normalized_url.startswith("postgresql+psycopg://"):
            Settings._validate_postgres_url(normalized_url)

        return normalized_url

    @staticmethod
    def _validate_postgres_url(database_url: str) -> None:
        """Raise a clear error for malformed Postgres URLs before SQLAlchemy tries to connect."""
        if any(marker in database_url for marker in ("<", ">", "[", "]")):
            raise ValueError(
                "TASKFLOW_DATABASE_URL contiene marcadores de ejemplo. "
                "Usa la cadena real de Supabase, "
                "sin <>, [] ni textos como YOUR-PASSWORD."
            )

        try:
            parsed_url = make_url(database_url)
        except ArgumentError as exc:
            raise ValueError(
                "TASKFLOW_DATABASE_URL no es valida. "
                "Copia la connection string completa de Supabase "
                "y, si la contraseña tiene caracteres especiales, usa su version URL-encoded."
            ) from exc

        if not parsed_url.host:
            raise ValueError(
                "TASKFLOW_DATABASE_URL no incluye un host valido. "
                "Revisa que el secret de Hugging Face contenga la URL completa "
                "de Supabase y no un texto incompleto o con saltos de linea."
            )

    @staticmethod
    def _normalize_http_url(raw_url: str) -> str:
        """Allow host:port values in env vars while still producing a valid HTTP base URL."""
        if raw_url.startswith(("http://", "https://")):
            return raw_url
        return f"http://{raw_url}"


settings = Settings()
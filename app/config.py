import os


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
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url

    @staticmethod
    def _normalize_http_url(raw_url: str) -> str:
        """Allow host:port values in env vars while still producing a valid HTTP base URL."""
        if raw_url.startswith(("http://", "https://")):
            return raw_url
        return f"http://{raw_url}"


settings = Settings()
import os


class Settings:
    def __init__(self) -> None:
        self.environment = os.getenv("TASKFLOW_ENV", "development")
        raw_database_url = os.getenv("TASKFLOW_DATABASE_URL", "sqlite:///./tareas.db")
        self.database_url = self._normalize_database_url(raw_database_url)
        self.streamlit_api_base_url = os.getenv(
            "TASKFLOW_API_BASE_URL", "http://127.0.0.1:8000"
        )
        self.auto_init_db = os.getenv("TASKFLOW_AUTO_INIT_DB", "true").lower() == "true"

    @staticmethod
    def _normalize_database_url(database_url: str) -> str:
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url


settings = Settings()
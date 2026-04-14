import os


class Settings:
    def __init__(self) -> None:
        self.environment = os.getenv("TASKFLOW_ENV", "development")
        self.database_url = os.getenv("TASKFLOW_DATABASE_URL", "sqlite:///./tareas.db")
        self.streamlit_api_base_url = os.getenv(
            "TASKFLOW_API_BASE_URL", "http://127.0.0.1:8000"
        )
        self.auto_init_db = os.getenv("TASKFLOW_AUTO_INIT_DB", "true").lower() == "true"


settings = Settings()
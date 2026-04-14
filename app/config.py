import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("TASKFLOW_DATABASE_URL", "sqlite:///./tareas.db")
        self.streamlit_api_base_url = os.getenv(
            "TASKFLOW_API_BASE_URL", "http://127.0.0.1:8000"
        )


settings = Settings()
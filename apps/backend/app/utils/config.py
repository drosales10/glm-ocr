"""
Gestión de la configuración de la aplicación
"""
from pydantic_settings import BaseSettings
from typing import Literal, Optional
from pathlib import Path


class Settings(BaseSettings):
    """Configuración de la aplicación"""

    # Configuración básica
    APP_NAME: str = "OCR Task System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Configuración de la base de datos
    DATABASE_URL: str = "sqlite+aiosqlite:///./tasks.db"

    # Directorio de salida
    OUTPUT_DIR: str = "./data"

    # Configuración de Workers
    RUN_WORKERS: bool = True
    WORKER_COUNT: int = 2
    WORKER_POLL_INTERVAL: int = 5  # segundos
    TASK_TIMEOUT: int = 3600  # segundos (1 hora)

    # Configuración de tareas
    MAX_QUEUE_SIZE: int = 100
    MAX_CONCURRENT_TASKS: int = 2
    DEFAULT_MAX_RETRIES: int = 3
    DEFAULT_RETRY_DELAY: int = 60  # segundos

    # Configuración de limpieza
    CLEANUP_INTERVAL: int = 300  # segundos (5 minutos)
    OLD_TASK_DAYS: int = 30  # días

    # Configuración de recuperación
    RECOVERY_INTERVAL: int = 3600  # segundos (1 hora)

    # Configuración de monitoreo
    METRICS_ENABLED: bool = True
    METRICS_INTERVAL: int = 60  # segundos

    # Configuración de logs
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    environment: Literal["development", "testing", "production"] = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Asegura que el directorio de salida exista
        Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


# Crear la instancia global de configuración
settings = Settings()

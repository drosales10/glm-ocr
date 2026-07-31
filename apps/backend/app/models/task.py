"""
Modelo de datos de tareas
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, Integer, Float, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TaskStatus:
    """Constantes de estado de tarea"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


class TaskPriority:
    """Constantes de prioridad de tarea"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class Task(Base, TimestampMixin):
    """
    Modelo de tarea
    """
    __tablename__ = "tasks"

    # Clave primaria e identificadores únicos
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )

    # Información del documento
    document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Configuración de procesamiento
    processing_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=TaskPriority.NORMAL)
    output_format: Mapped[str] = mapped_column(String(50), default="markdown")

    # Estado de la tarea
    status: Mapped[str] = mapped_column(
        String(50),
        default=TaskStatus.PENDING,
        index=True,
        nullable=False
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )  # Nombre del paso en ejecución (p. ej.: pdf_to_images, ocr_processing)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resultado
    result_file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Configuración
    ocr_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Marcas de tiempo
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relacionado con reintentos
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay: Mapped[int] = mapped_column(Integer, default=60)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relacionado con Workers (para bloqueos distribuidos)
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )
    lock_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<Task(task_id={self.task_id}, status={self.status}, progress={self.progress})>"

    @property
    def is_locked(self) -> bool:
        """Comprueba si la tarea está bloqueada"""
        if not self.lock_expires_at:
            return False
        return self.lock_expires_at > datetime.now()

    @property
    def is_expired(self) -> bool:
        """Comprueba si el bloqueo de la tarea ha expirado"""
        if not self.lock_expires_at:
            return False
        return self.lock_expires_at <= datetime.now()

    @property
    def can_retry(self) -> bool:
        """Comprueba si la tarea se puede reintentar"""
        return self.retry_count < self.max_retries

    @property
    def execution_time(self) -> Optional[float]:
        """Calcula el tiempo de ejecución de la tarea (segundos)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

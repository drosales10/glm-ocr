"""
Esquemas Pydantic relacionados con tareas
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class TaskSubmitRequest(BaseModel):
    """Solicitud de envío de tarea"""

    original_filename: str = Field(..., description="Nombre original del archivo")
    file_type: str = Field(..., description="Tipo de archivo")
    file_size: int = Field(..., gt=0, description="Tamaño del archivo")
    file_path: str = Field(..., description="Ruta del archivo")
    processing_mode: str = Field(default="pipeline", description="Modo de procesamiento")
    priority: int = Field(default=2, ge=1, le=4, description="Prioridad (1-4)")
    ocr_config: Optional[Dict[str, Any]] = Field(default=None, description="Configuración OCR")
    output_format: str = Field(default="markdown", description="Formato de salida")
    retry_config: Optional[Dict[str, Any]] = Field(default=None, description="Configuración de reintentos")

    class Config:
        json_schema_extra = {
            "example": {
                "original_filename": "document.pdf",
                "file_type": "pdf",
                "file_size": 1024000,
                "file_path": "/path/to/document.pdf",
                "processing_mode": "pipeline",
                "priority": 2,
                "ocr_config": {"dpi": 300, "image_format": "png", "language": "mixed"},
                "output_format": "markdown",
            }
        }


class TaskSubmitResponse(BaseModel):
    """Respuesta de envío de tarea"""

    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Respuesta de estado de tarea"""

    task_id: str
    document_id: str
    status: str
    progress: float
    current_step: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result_file_path: Optional[str]
    processing_mode: str
    priority: int
    retry_count: int
    worker_id: Optional[str]
    metadata: Optional[Dict] = None
    full_markdown: Optional[str] = None
    layout: Optional[List] = None


class TaskInfo(BaseModel):
    """Información de tarea (para listados)"""

    task_id: str
    document_id: str
    status: str
    progress: float
    current_step: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    processing_mode: str
    priority: int


class TaskListResponse(BaseModel):
    """Respuesta de lista de tareas"""

    tasks: List[TaskInfo]
    total: int


class TaskCancelResponse(BaseModel):
    """Respuesta de cancelación de tarea"""

    task_id: str
    status: str
    message: str

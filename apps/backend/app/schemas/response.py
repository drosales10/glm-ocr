"""
Modelo de respuesta común
"""
from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """Formato unificado de respuesta de la API"""
    success: bool = Field(..., description="Indica si la solicitud fue exitosa")
    data: Optional[T] = Field(None, description="Datos de la respuesta")
    message: Optional[str] = Field(None, description="Mensaje de la respuesta")
    error_code: Optional[str] = Field(None, description="Código de error")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"key": "value"},
                "message": "Operación exitosa",
                "error_code": None
            }
        }


class TaskData(BaseModel):
    """Datos de la tarea"""
    task_id: str
    document_id: str
    status: str
    processing_mode: str
    priority: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time: Optional[float] = Field(
        None, description="Segundos entre started_at y completed_at"
    )
    progress: Optional[float] = None
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    worker_id: Optional[str] = None


class TaskResultData(BaseModel):
    """Datos del resultado de la tarea"""
    metadata: Optional[dict] = None
    full_markdown: Optional[str] = None
    layout: Optional[list] = None

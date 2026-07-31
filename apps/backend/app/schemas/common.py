"""
Esquemas Pydantic comunes
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, TypeVar, Generic
from datetime import datetime


T = TypeVar('T')


class ErrorResponse(BaseModel):
    """Respuesta de error"""
    error: str = Field(..., description="Tipo de error")
    message: str = Field(..., description="Mensaje de error")
    detail: Optional[str] = Field(None, description="Información detallada del error")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid input",
                "detail": "File size must be greater than 0"
            }
        }


class MessageResponse(BaseModel):
    """Respuesta de mensaje genérica"""
    message: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta paginada"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProgressUpdate(BaseModel):
    """Actualización de progreso"""
    task_id: str
    step_name: str
    progress: float
    overall_progress: float
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

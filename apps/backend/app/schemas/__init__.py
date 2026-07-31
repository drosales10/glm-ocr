"""
Definiciones de esquemas Pydantic

Proporciona modelos unificados de solicitud y respuesta de la API
"""

from app.schemas.task import (
    TaskSubmitRequest,
    TaskSubmitResponse,
    TaskStatusResponse,
    TaskListResponse,
    TaskCancelResponse,
    TaskInfo,
)

from app.schemas.system import (
    WorkerStats,
    TasksMetrics,
    WorkersMetrics,
    MetricsResponse,
    HealthResponse,
    SystemInfoResponse,
)

from app.schemas.common import (
    ErrorResponse,
    MessageResponse,
    PaginatedResponse,
    ProgressUpdate,
)

from app.schemas.response import ApiResponse, TaskData, TaskResultData

__all__ = [
    # Task schemas
    "TaskSubmitRequest",
    "TaskSubmitResponse",
    "TaskStatusResponse",
    "TaskListResponse",
    "TaskCancelResponse",
    "TaskInfo",
    # System schemas
    "WorkerStats",
    "TasksMetrics",
    "WorkersMetrics",
    "MetricsResponse",
    "HealthResponse",
    "SystemInfoResponse",
    # Common schemas
    "ErrorResponse",
    "MessageResponse",
    "PaginatedResponse",
    "ProgressUpdate",
    # Response schemas
    "ApiResponse",
    "TaskData",
    "TaskResultData",
]

"""
Esquemas Pydantic relacionados con el sistema
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class WorkerStats(BaseModel):
    """Estadísticas del Worker"""
    worker_id: str
    is_running: bool
    current_task: Optional[str]
    tasks_completed: int
    tasks_failed: int
    avg_execution_time: float


class TasksMetrics(BaseModel):
    """Métricas de tareas"""
    status_counts: Dict[str, int]
    total: int


class WorkersMetrics(BaseModel):
    """Métricas de Workers"""
    total: int
    active: int
    idle: int
    busy: int
    stats: List[WorkerStats]


class MetricsResponse(BaseModel):
    """Respuesta de métricas del sistema"""
    tasks: TasksMetrics
    workers: WorkersMetrics
    timestamp: str


class HealthResponse(BaseModel):
    """Respuesta de comprobación de salud"""
    status: str
    task_manager_running: Optional[bool] = None
    workers_count: Optional[int] = None
    active_workers: Optional[int] = None
    version: Optional[str] = None
    error: Optional[str] = None


class SystemInfoResponse(BaseModel):
    """Respuesta de información del sistema"""
    name: str
    version: str
    status: str

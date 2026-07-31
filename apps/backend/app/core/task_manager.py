"""
Implementación del administrador de tareas
"""

import asyncio
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC

from app.db.database import AsyncSessionLocal
from app.models.task import Task, TaskStatus, TaskPriority
from app.repository.task import TaskRepository
from app.core.worker import Worker
from app.core.lock_manager import LockManager
from app.core.recovery_handler import RecoveryHandler
from app.utils.logger import logger
from app.utils.config import settings


class TaskManager:
    """
    Administrador de tareas

    Responsable del envío, la programación y el monitoreo de tareas
    """

    def __init__(self, max_concurrent_tasks: int = 5, worker_count: int = 5):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.worker_count = worker_count

        # Workers
        self.workers: List[Worker] = []

        # Gestión de estado
        self.is_running = False
        self._shutdown_event = asyncio.Event()

        logger.info(
            f"TaskManager initialized: "
            f"max_concurrent={max_concurrent_tasks}, workers={worker_count}"
        )

    async def start(self):
        """Inicia el administrador de tareas"""
        if self.is_running:
            logger.warning("TaskManager is already running")
            return

        logger.info("Starting TaskManager...")

        self.is_running = True
        self._shutdown_event.clear()

        # Recupera tareas al iniciar
        await self._recover_tasks()

        # Iniciar Workers
        for i in range(self.worker_count):
            worker = Worker(
                worker_id=f"worker-{i+1}",
                poll_interval=settings.WORKER_POLL_INTERVAL,
                task_timeout=settings.TASK_TIMEOUT,
            )
            self.workers.append(worker)

            # Iniciar el worker en segundo plano
            asyncio.create_task(worker.start())

        # Iniciar las corrutinas de monitoreo y limpieza
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._cleanup_loop())

        logger.info(f"TaskManager started with {len(self.workers)} workers")

    async def stop(self):
        """Detiene el administrador de tareas"""
        if not self.is_running:
            return

        logger.info("Stopping TaskManager...")

        self.is_running = False
        self._shutdown_event.set()

        # Detener todos los Workers
        for worker in self.workers:
            await worker.stop()

        self.workers.clear()

        logger.info("TaskManager stopped")

    async def submit_task(
        self,
        task_id: Optional[str],
        document_id: str,
        original_filename: str,
        file_type: str,
        file_size: int,
        file_path: str,
        processing_mode: str = "pipeline",
        priority: int = TaskPriority.NORMAL,
        ocr_config: Optional[Dict[str, Any]] = None,
        output_format: str = "markdown",
        retry_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Envía una nueva tarea

        Args:
            document_id: ID del documento
            original_filename: Nombre original del archivo
            file_type: Tipo de archivo
            file_size: Tamaño del archivo
            file_path: Ruta del archivo
            processing_mode: Modo de procesamiento
            priority: Prioridad
            ocr_config: Configuración OCR
            output_format: Formato de salida
            retry_config: Configuración de reintentos

        Returns:
            str: ID de la tarea
        """
        if not self.is_running:
            raise RuntimeError("TaskManager is not running")
        if task_id is None :
            # Generar el ID de la tarea
            task_id = str(uuid.uuid4())

        logger.info(
            f"Submitting task: {task_id}, "
            f"file={original_filename}, mode={processing_mode}"
        )

        try:
            async with AsyncSessionLocal() as db:
                task_repo = TaskRepository(db)

                # Crea una tarea
                task = await task_repo.create_task(
                    task_id=task_id,
                    document_id=document_id,
                    original_filename=original_filename,
                    file_type=file_type,
                    file_size=file_size,
                    file_path=file_path,
                    processing_mode=processing_mode,
                    priority=priority,
                    ocr_config=ocr_config,
                    output_format=output_format,
                    retry_config=retry_config,
                )

                await db.commit()
                logger.info(f"Task created: {task_id}")

                return task_id

        except Exception as e:
            logger.error(f"Failed to submit task: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado de la tarea

        Args:
            task_id: ID de la tarea

        Returns:
            Optional[Dict]: Información de la tarea
        """
        async with AsyncSessionLocal() as db:
            task_repo = TaskRepository(db)
            task = await task_repo.get_by_task_id(task_id)

            if not task:
                return None

            return {
                "task_id": task.task_id,
                "document_id": task.document_id,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "execution_time": task.execution_time,
                "error_message": task.error_message,
                "result_file_path": task.result_file_path,
                "processing_mode": task.processing_mode,
                "priority": task.priority,
                "retry_count": task.retry_count,
                "worker_id": task.worker_id,
            }

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancela la tarea

        Args:
            task_id: ID de la tarea

        Returns:
            bool: Si se canceló correctamente
        """
        try:
            async with AsyncSessionLocal() as db:
                task_repo = TaskRepository(db)
                task = await task_repo.get_by_task_id(task_id)

                if not task:
                    return False

                # Solo se pueden cancelar tareas pending o processing
                if task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                    return False

                # Actualizar el estado
                await task_repo.update_task_status(
                    task_id=task_id, status=TaskStatus.CANCELLED
                )
                await db.commit()

                logger.info(f"Task cancelled: {task_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False

    async def list_tasks(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lista las tareas

        Args:
            status: Estado de filtro
            limit: Límite de cantidad a devolver
            offset: Desplazamiento (offset)

        Returns:
            List[Dict]: Lista de tareas
        """
        async with AsyncSessionLocal() as db:
            task_repo = TaskRepository(db)
            tasks = await task_repo.list_tasks_by_status(
                status=status, skip=offset, limit=limit
            )

            return [
                {
                    "task_id": task.task_id,
                    "document_id": task.document_id,
                    "status": task.status,
                    "progress": task.progress,
                    "current_step": task.current_step,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "processing_mode": task.processing_mode,
                    "priority": task.priority,
                }
                for task in tasks
            ]

    async def get_metrics(self) -> Dict[str, Any]:
        """Obtiene las métricas del sistema"""
        async with AsyncSessionLocal() as db:
            task_repo = TaskRepository(db)

            # Contar tareas por cada estado
            status_counts = await task_repo.count_tasks_by_status()

            # Construir las métricas de tareas
            tasks_metrics = {
                "status_counts": status_counts,
                "total": sum(status_counts.values()),
            }

            # Estadísticas de Workers
            worker_stats = []
            for worker in self.workers:
                worker_stats.append(
                    {
                        "worker_id": worker.worker_id,
                        "is_running": worker.is_running,
                        "current_task": worker.current_task_id,
                        "tasks_completed": worker.metrics.tasks_completed,
                        "tasks_failed": worker.metrics.tasks_failed,
                        "avg_execution_time": worker.metrics.avg_execution_time,
                    }
                )

            # Construir las métricas de Workers
            workers_metrics = {
                "total": len(self.workers),
                "active": sum(1 for w in self.workers if w.is_running),
                "idle": sum(1 for w in self.workers if w.current_task_id is None),
                "busy": sum(1 for w in self.workers if w.current_task_id is not None),
                "stats": worker_stats,
            }

            return {
                "tasks": tasks_metrics,
                "workers": workers_metrics,
                "timestamp": datetime.now(UTC).isoformat(),
            }

    async def _recover_tasks(self):
        """Recupera tareas al iniciar"""
        logger.info("Recovering tasks on startup...")

        try:
            async with AsyncSessionLocal() as db:
                task_repo = TaskRepository(db)
                recovery_handler = RecoveryHandler(task_repo)

                stats = await recovery_handler.recover_on_startup()
                await db.commit()

                logger.info(f"Task recovery completed: {stats}")

        except Exception as e:
            logger.error(f"Task recovery failed: {e}")

    async def _monitoring_loop(self):
        """Corrutina de monitoreo"""
        logger.info("Monitoring loop started")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(settings.METRICS_INTERVAL)

                # Recuperar bloqueos expirados
                async with AsyncSessionLocal() as db:
                    lock_manager = LockManager(db)
                    recovered = await lock_manager.recover_expired_locks()
                    if recovered > 0:
                        logger.info(
                            f"Recovered {recovered} expired locks in monitoring loop"
                        )

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

        logger.info("Monitoring loop stopped")

    async def _cleanup_loop(self):
        """Corrutina de limpieza"""
        logger.info("Cleanup loop started")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(settings.CLEANUP_INTERVAL)

                # Limpia tareas antiguas
                async with AsyncSessionLocal() as db:
                    task_repo = TaskRepository(db)
                    deleted = await task_repo.cleanup_old_tasks(
                        days=settings.OLD_TASK_DAYS
                    )
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old tasks")

            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

        logger.info("Cleanup loop stopped")

    def __repr__(self) -> str:
        return (
            f"<TaskManager(running={self.is_running}, " f"workers={len(self.workers)})>"
        )


# Instancia global del administrador de tareas
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Obtiene la instancia del administrador de tareas"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(
            max_concurrent_tasks=settings.MAX_CONCURRENT_TASKS,
            worker_count=settings.WORKER_COUNT,
        )
    return _task_manager


async def init_task_system():
    """Inicializa el sistema de tareas"""
    task_manager = get_task_manager()
    await task_manager.start()
    logger.info("Task system initialized")


async def shutdown_task_system():
    """Cierra el sistema de tareas"""
    global _task_manager
    if _task_manager:
        await _task_manager.stop()
        logger.info("Task system shutdown")

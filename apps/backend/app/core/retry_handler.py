"""
Procesador de reintentos de tareas
"""
import random
from typing import Optional

from app.models.task import Task, TaskStatus
from app.repository.task import TaskRepository
from app.utils.logger import logger


class RetryHandler:
    """Procesador de reintentos de tareas"""

    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo

    async def handle_failure(
        self,
        task: Task,
        error_message: str,
        error_type: str = "unknown"
    ) -> bool:
        """
        Gestiona el fallo de una tarea

        Args:
            task: Tarea fallida
            error_message: Mensaje de error
            error_type: Tipo de error

        Returns:
            bool: Si se puede reintentar
        """
        logger.warning(
            f"Task {task.task_id} failed (attempt {task.retry_count + 1}/{task.max_retries}): {error_message}"
        )

        # Comprobar si se puede reintentar
        if not task.can_retry:
            logger.error(f"Task {task.task_id} exceeded max retries, moving to dead letter")
            await self._move_to_dead_letter(task, error_message, error_type)
            return False

        # Comprobar si el tipo de error es reintentable
        if not self._is_retryable_error(error_type):
            logger.error(f"Task {task.task_id} failed with non-retryable error: {error_type}")
            await self._move_to_dead_letter(task, error_message, error_type)
            return False

        # Calcular el retraso de reintento
        retry_delay = self._calculate_retry_delay(task.retry_count, task.retry_delay)

        logger.info(
            f"Scheduling retry for task {task.task_id} in {retry_delay}s "
            f"(attempt {task.retry_count + 1}/{task.max_retries})"
        )

        # Restablecer el estado de la tarea a PENDING
        await self.task_repo.reset_task_for_retry(
            task_id=task.task_id,
            error_message=error_message
        )

        return True

    def _calculate_retry_delay(self, retry_count: int, base_delay: int) -> int:
        """
        Calcula el retraso de reintento (retroceso exponencial + jitter aleatorio)

        Args:
            retry_count: Número actual de reintentos
            base_delay: Retraso base (segundos)

        Returns:
            int: Tiempo de retraso (segundos)
        """
        # Retroceso exponencial
        exponential_delay = base_delay * (2 ** retry_count)

        # Añadir jitter aleatorio (10%)
        jitter = random.randint(0, int(exponential_delay * 0.1))

        # Retraso máximo de 1 hora
        return min(exponential_delay + jitter, 3600)

    def _is_retryable_error(self, error_type: str) -> bool:
        """
        Determina si el error es reintentable

        Args:
            error_type: Tipo de error

        Returns:
            bool: Si es reintentable
        """
        # Tipos de error reintentables
        retryable_errors = {
            "timeout",
            "connection_error",
            "service_unavailable",
            "rate_limit_exceeded",
            "transient_error",
            "resource_temporarily_unavailable"
        }

        # Tipos de error no reintentables
        non_retryable_errors = {
            "validation_error",
            "authentication_error",
            "authorization_error",
            "not_found",
            "invalid_input",
            "file_not_found"
        }

        if error_type in non_retryable_errors:
            return False

        if error_type in retryable_errors:
            return True

        # Por defecto, los errores desconocidos son reintentables
        return True

    async def _move_to_dead_letter(
        self,
        task: Task,
        error_message: str,
        error_type: str
    ):
        """Marca la tarea como carta muerta (dead letter)"""
        # Actualiza el estado de la tarea
        await self.task_repo.update_task_status(
            task_id=task.task_id,
            status=TaskStatus.DEAD_LETTER,
            error_message=f"Moved to dead letter: {error_message} (error_type: {error_type})"
        )

        logger.warning(f"Task {task.task_id} moved to dead letter")

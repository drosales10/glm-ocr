"""
Procesador de recuperación de tareas
"""
from typing import Dict, Any

from app.models.task import Task, TaskStatus
from app.repository.task import TaskRepository
from app.utils.logger import logger


class RecoveryHandler:
    """Procesador de recuperación de tareas"""

    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo

    async def recover_on_startup(self) -> Dict[str, int]:
        """
        Recupera tareas al iniciar el sistema

        Returns:
            Dict[str, int]: Estadísticas de recuperación
        """
        logger.info("Starting task recovery on startup")

        stats = {
            "total_checked": 0,
            "expired_locks_recovered": 0,
            "failed_recoveries": 0
        }

        try:
            # Recupera tareas con bloqueo expirado
            expired_count = await self._recover_expired_locks()
            stats["expired_locks_recovered"] = expired_count

            stats["total_checked"] = expired_count

            logger.info(f"Task recovery completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Task recovery failed: {e}")
            stats["failed_recoveries"] = 1
            return stats

    async def _recover_expired_locks(self) -> int:
        """Recupera tareas con bloqueo expirado"""
        expired_tasks = await self.task_repo.get_expired_locks(limit=1000)

        recovered_count = 0
        for task in expired_tasks:
            try:
                await self._recover_single_task(task, reason="lock_expired")
                recovered_count += 1
            except Exception as e:
                logger.error(f"Failed to recover task {task.task_id}: {e}")

        if recovered_count > 0:
            logger.info(f"Recovered {recovered_count} tasks with expired locks")

        return recovered_count

    async def _recover_single_task(self, task: Task, reason: str):
        """Recupera una sola tarea"""
        logger.info(f"Recovering task {task.task_id}, reason: {reason}")

        # Comprobar si se puede reintentar
        if not task.can_retry:
            # Se superó el número máximo de reintentos; marcar como carta muerta
            await self.task_repo.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.DEAD_LETTER,
                error_message=f"Task recovered but max retries exceeded: {reason}"
            )
            logger.warning(f"Task {task.task_id} marked as dead letter (max retries exceeded)")
            return

        # Restablecer la tarea al estado PENDING
        await self.task_repo.update_task_status(
            task_id=task.task_id,
            status=TaskStatus.PENDING,
            error_message=f"Task recovered: {reason}"
        )

        # Restablecer al estado inicial
        from sqlalchemy import update

        stmt = (
            update(Task)
            .where(Task.task_id == task.task_id)
            .values(
                worker_id=None,
                lock_expires_at=None,
                retry_count=task.retry_count + 1,
                started_at=None,
                current_step=None,
                progress=0.0
            )
        )
        await self.task_repo.session.execute(stmt)

        logger.info(f"Task {task.task_id} recovered successfully")

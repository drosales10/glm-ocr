"""
Administrador de bloqueos de tareas
"""
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus
from app.repository.task import TaskRepository
from app.utils.logger import logger


class LockManager:
    """Administrador de bloqueos de tareas"""

    def __init__(self, session: AsyncSession, default_timeout: int = 3600):
        self.session = session
        self.default_timeout = default_timeout
        self.task_repo = TaskRepository(session)

    async def acquire(
        self,
        task_id: str,
        worker_id: str,
        timeout: Optional[int] = None
    ) -> Optional[Task]:
        """
        Adquiere el bloqueo de la tarea

        Args:
            task_id: ID de la tarea
            worker_id: Worker ID
            timeout: Tiempo de espera del bloqueo (segundos)

        Returns:
            Optional[Task]: Devuelve la tarea si tiene éxito; None si falla
        """
        lock_timeout = timeout or self.default_timeout

        try:
            task = await self.task_repo.acquire_task_lock(
                task_id=task_id,
                worker_id=worker_id,
                lock_timeout=lock_timeout
            )

            if task:
                logger.info(f"Lock acquired for task {task_id} by worker {worker_id}")
            else:
                logger.warning(f"Failed to acquire lock for task {task_id} by worker {worker_id}")

            return task

        except Exception as e:
            logger.error(f"Failed to acquire lock for task {task_id}: {e}")
            return None

    async def release(
        self,
        task_id: str,
        worker_id: str,
        status: str = TaskStatus.COMPLETED,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Libera el bloqueo de la tarea

        Args:
            task_id: ID de la tarea
            worker_id: Worker ID
            status: Estado final
            error_message: Mensaje de error

        Returns:
            bool: Si se liberó correctamente
        """
        try:
            success = await self.task_repo.release_task_lock(
                task_id=task_id,
                worker_id=worker_id,
                status=status,
                error_message=error_message
            )

            if success:
                logger.info(f"Lock released for task {task_id} by worker {worker_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to release lock for task {task_id}: {e}")
            return False

    async def renew(self, task_id: str, worker_id: str) -> bool:
        """
        Renueva el bloqueo de la tarea

        Args:
            task_id: ID de la tarea
            worker_id: Worker ID

        Returns:
            bool: Si se renovó correctamente
        """
        try:
            success = await self.task_repo.renew_task_lock(
                task_id=task_id,
                worker_id=worker_id,
                lock_timeout=self.default_timeout
            )

            if success:
                logger.debug(f"Lock renewed for task {task_id} by worker {worker_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to renew lock for task {task_id}: {e}")
            return False

    async def recover_expired_locks(self) -> int:
        """
        Recupera bloqueos expirados

        Returns:
            int: Número de tareas recuperadas
        """
        try:
            expired_tasks = await self.task_repo.get_expired_locks(limit=100)

            recovered_count = 0
            for task in expired_tasks:
                try:
                    # Comprobar si se puede reintentar
                    if task.can_retry:
                        await self.task_repo.reset_task_for_retry(
                            task_id=task.task_id,
                            error_message="Lock expired, recovered for retry"
                        )
                        recovered_count += 1
                        logger.info(f"Recovered task {task.task_id} (lock expired)")
                    else:
                        # Se superó el número máximo de reintentos; marcar como carta muerta
                        await self.task_repo.update_task_status(
                            task_id=task.task_id,
                            status=TaskStatus.DEAD_LETTER,
                            error_message="Lock expired and max retries exceeded"
                        )
                        logger.warning(f"Task {task.task_id} moved to dead letter (lock expired)")

                except Exception as e:
                    logger.error(f"Failed to recover task {task.task_id}: {e}")

            if recovered_count > 0:
                logger.info(f"Recovered {recovered_count} tasks with expired locks")
                await self.session.commit()

            return recovered_count

        except Exception as e:
            logger.error(f"Failed to recover expired locks: {e}")
            await self.session.rollback()
            return 0

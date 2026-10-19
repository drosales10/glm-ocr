"""
Clase base y contexto del flujo de procesamiento de tareas
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Type, List
from dataclasses import dataclass
from datetime import datetime, UTC

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repository.task import TaskRepository
from app.models.task import TaskStatus
from app.utils.logger import logger


@dataclass
class StepProgress:
    """Información de progreso del paso"""

    step_name: str  # Nombre del paso
    progress: float  # Progreso del paso actual (0.0-100.0)
    overall_progress: float  # Progreso global (0.0-100.0)
    message: Optional[str] = None  # Mensaje de progreso
    metadata: Optional[Dict[str, Any]] = None  # Metadatos adicionales


class ProcessingContext:
    """
    Contexto de procesamiento de tareas

    Pasa datos y configuración durante la ejecución de la tarea
    """

    def __init__(
        self,
        task_id: str,
        document_id: str,
        file_path: str,
        file_type: str,
        processing_mode: str,
        ocr_config: Dict[str, Any],
        output_format: str,
        metadata: Dict[str, Any] = None,
        db_session: Optional[AsyncSession] = None,
        progress_callback: Optional[Callable[[StepProgress], None]] = None,
    ):
        self.task_id = task_id
        self.document_id = document_id
        self.file_path = file_path
        self.file_type = file_type
        self.processing_mode = processing_mode
        self.ocr_config = ocr_config
        self.output_format = output_format
        self.db_session = db_session
        self.progress_callback = progress_callback
        self.metadata = metadata
        # Almacenamiento de datos durante la ejecución
        self._data: Dict[str, Any] = {}

        # Directorio de salida
        self._output_dir: Optional[str] = None

    def set(self, key: str, value: Any):
        """Almacena datos intermedios"""
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene datos intermedios"""
        return self._data.get(key, default)

    def set_output_dir(self, output_dir: str):
        """Establece el directorio de salida"""
        self._output_dir = output_dir

    def get_output_dir(self) -> Optional[str]:
        """Obtiene el directorio de salida"""
        return self._output_dir

    async def update_task_progress(
        self, current_step: str, progress: float, message: Optional[str] = None
    ):
        """Actualiza el progreso de la tarea en la base de datos"""
        if not self.db_session:
            return

        try:
            task_repo = TaskRepository(self.db_session)
            await task_repo.update_task_progress(
                task_id=self.task_id, progress=progress, current_step=current_step
            )
            await self.db_session.commit()
        except Exception as e:
            # Un fallo al actualizar el progreso no debe afectar el flujo principal
            logger.warning(f"No se pudo guardar el progreso de {self.task_id}: {e}")


class TaskProcessingFlow(ABC):
    """
    Clase base abstracta del flujo de procesamiento de tareas

    Las subclases deben implementar el método process() y definir en él el flujo de procesamiento
    """

    def __init__(self, context: ProcessingContext):
        self.context = context

    @abstractmethod
    async def process(self) -> Dict[str, Any]:
        """
        Ejecuta el flujo de procesamiento completo

        Al implementarlo en la subclase, defina ahí los pasos de procesamiento concretos

        Returns:
            Dict[str, Any]: Resultado del procesamiento; debe incluir el campo success
        """
        pass

    async def update_progress(
        self,
        step_name: str,
        progress: float,
        overall_progress: Optional[float] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Actualiza el progreso de la tarea

        Args:
            step_name: Nombre del paso actual
            progress: Progreso del paso actual (0.0-100.0)
            overall_progress: Progreso global (0.0-100.0); si no se proporciona, se calcula automáticamente
            message: Mensaje de progreso
            metadata: Metadatos adicionales
        """
        if overall_progress is None:
            overall_progress = progress

        # Crear información de progreso
        progress_info = StepProgress(
            step_name=step_name,
            progress=progress,
            overall_progress=overall_progress,
            message=message,
            metadata=metadata,
        )

        # Notificación por callback (si existe)
        if self.context.progress_callback:
            try:
                await self.context.progress_callback(progress_info)
            except Exception as e:
                # Un fallo del callback no afecta el flujo principal
                pass

        # Actualizar la base de datos
        await self.context.update_task_progress(
            current_step=step_name, progress=overall_progress, message=message
        )


class FlowFactory:
    """Fábrica de flujos de procesamiento"""

    # Clases de flujo registradas
    _flows: Dict[str, Type[TaskProcessingFlow]] = {}

    @classmethod
    def register_flow(cls, processing_mode: str, flow_class: Type[TaskProcessingFlow]):
        """
        Registra un flujo de procesamiento

        Args:
            processing_mode: Nombre del modo de procesamiento
            flow_class: Clase del flujo
        """
        cls._flows[processing_mode] = flow_class

    @classmethod
    def create_flow(
        cls, processing_mode: str, context: ProcessingContext
    ) -> TaskProcessingFlow:
        """
        Crea una instancia del flujo de procesamiento

        Args:
            processing_mode: Modo de procesamiento
            context: Contexto de procesamiento

        Returns:
            TaskProcessingFlow: Instancia del flujo de procesamiento

        Raises:
            ValueError: Modo de procesamiento no admitido
        """
        flow_class = cls._flows.get(processing_mode)

        if not flow_class:
            raise ValueError(
                f"Unsupported processing mode: {processing_mode}. "
                f"Available modes: {list(cls._flows.keys())}"
            )

        return flow_class(context)

    @classmethod
    def get_registered_modes(cls) -> List[str]:
        """Obtiene todos los modos de procesamiento registrados"""
        return list(cls._flows.keys())

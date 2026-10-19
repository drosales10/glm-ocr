"""
API relacionada con tareas
"""

import json
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Response
from mimetypes import guess_type

from app.schemas.response import ApiResponse, TaskData, TaskResultData
from app.core.task_manager import get_task_manager
from app.utils.logger import logger
from app.utils.upload_file_manager import file_upload_handler
from app.utils.config import settings


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_iso_utc(value: Optional[datetime]) -> Optional[str]:
    """Serializa datetimes en ISO-8601 con Z (UTC) para el cronómetro del frontend."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


@router.post(
    "/upload",
    response_model=ApiResponse[TaskData],
    status_code=status.HTTP_201_CREATED,
)
async def submit_task(
    file: UploadFile = File(..., description="Archivo a procesar"),
    processing_mode: str = Form("pipeline"),
    priority: int = Form(2, description="1=baja,2=normal,3=alta,4=urgente"),
    custom_url: str = Form(None, description=""),
    ocr_profile: str = Form(
        "balanced",
        description="Perfil OCR: fast | balanced | math",
    ),
    output_format: str = Form("markdown"),
):
    """
    Envía una nueva tarea

    - **file**: Archivo subido
    - **processing_mode**: Modo de procesamiento; por defecto pipeline
    - **priority**: Prioridad (1=baja, 2=normal, 3=alta, 4=urgente)
    - **ocr_profile**: Perfil de velocidad/calidad (fast, balanced, math)
    - **ocr_config**: Configuración OCR (cadena JSON, opcional)
    - **output_format**: Formato de salida; por defecto markdown
    - **retry_config**: Configuración de reintentos (cadena JSON, opcional)
    """
    try:
        # Generar document_id
        document_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())

        profile = (ocr_profile or "balanced").strip().lower()
        if profile not in {"fast", "balanced", "math"}:
            profile = "balanced"

        parsed_ocr_config: dict = {"ocr_profile": profile}
        if custom_url is not None:
            parsed_ocr_config["custom_url"] = custom_url

        # Guardar el archivo
        save_dir = str(Path(settings.OUTPUT_DIR) / task_id)
        saved_path = await file_upload_handler.save_to_path(
            file=file,
            filename=file.filename,
            upload_dir=save_dir,
        )
        saved_path_obj = Path(saved_path)
        file_size = saved_path_obj.stat().st_size
        file_type = saved_path_obj.suffix.lstrip(".").lower()

        # Enviar la tarea
        task_manager = get_task_manager()
        await task_manager.submit_task(
            task_id=task_id,
            document_id=document_id,
            original_filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            file_path=str(saved_path_obj),
            processing_mode=processing_mode,
            priority=priority,
            ocr_config=parsed_ocr_config,
            output_format=output_format,
        )

        return ApiResponse(
            success=True,
            data={
                "task_id": task_id,
                "document_id": document_id,
                "status": "pending",
                "processing_mode": processing_mode,
                "priority": priority,
                "created_at": datetime.now(UTC).isoformat(),
            },
            message="Task submitted successfully",
        )

    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}",
        )


@router.get("/file")
async def read_file(path: str):
    """
    Lee el contenido del archivo en la ruta indicada

    Para archivos de imagen, devuelve directamente los datos de la imagen
    Para otros archivos, devuelve la información del archivo en formato JSON

    - **path**: Ruta del archivo
    """
    try:
        file_path = Path(path)

        # Comprobar si el archivo existe
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {path}",
            )

        # Comprobar si es un archivo
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path is not a file: {path}",
            )

        # Obtener el tipo MIME del archivo
        mime_type, _ = guess_type(file_path.name)
        if mime_type is None:
            mime_type = "application/octet-stream"

        # Leer el contenido del archivo
        with open(file_path, "rb") as f:
            content = f.read()

        # Si es un archivo de imagen, devolver directamente los datos binarios
        if mime_type.startswith("image/"):
            return Response(
                content=content,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f"inline; filename=\"{file_path.name}\""
                }
            )

        # Otros tipos de archivo: devolver en formato JSON
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = "(binary file)"

        return ApiResponse(
            success=True,
            data={
                "path": str(file_path.absolute()),
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "mime_type": mime_type,
                "content": text_content,
            },
            message="File read successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}",
        )


@router.get("/{task_id}", response_model=ApiResponse[dict])
async def get_task_status(task_id: str):
    """
    Obtiene el estado de la tarea

    - **task_id**: ID de la tarea
    """
    try:
        task_manager = get_task_manager()
        task_info = await task_manager.get_task_status(task_id)

        if not task_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        # Si hay result_file_path, leer y fusionar el contenido
        result_file_path = task_info.get("result_file_path")
        result_data = None
        if result_file_path:
            try:
                result_path = Path(result_file_path)
                if result_path.exists():
                    with open(result_path, "r", encoding="utf-8") as f:
                        result_data = json.load(f)
                        logger.info(f"Loaded result data for task {task_id}")
                else:
                    logger.warning(f"Result file not found: {result_file_path}")
            except Exception as e:
                logger.warning(f"Failed to read result file: {e}")

        # Construir los datos de la respuesta
        response_data = {
            "task_id": task_info.get("task_id"),
            "document_id": task_info.get("document_id"),
            "status": task_info.get("status"),
            "progress": task_info.get("progress"),
            "current_step": task_info.get("current_step"),
            "created_at": _to_iso_utc(task_info.get("created_at")),
            "started_at": _to_iso_utc(task_info.get("started_at")),
            "completed_at": _to_iso_utc(task_info.get("completed_at")),
            "execution_time": task_info.get("execution_time"),
            "error_message": task_info.get("error_message"),
            "processing_mode": task_info.get("processing_mode"),
            "priority": task_info.get("priority"),
            "retry_count": task_info.get("retry_count"),
            "worker_id": task_info.get("worker_id"),
        }

        # Añadir los datos del resultado
        if result_data:
            response_data["metadata"]= result_data.get("metadata")
            response_data["full_markdown"] = result_data.get("full_markdown")
            response_data["layout"] = result_data.get("layout")

        return ApiResponse(
            success=True,
            data=response_data,
            message="Task status retrieved successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}",
        )


@router.delete("/{task_id}", response_model=ApiResponse[dict])
async def cancel_task(task_id: str):
    """
    Cancela la tarea

    - **task_id**: ID de la tarea
    """
    try:
        task_manager = get_task_manager()
        success = await task_manager.cancel_task(task_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found or cannot be cancelled: {task_id}",
            )

        return ApiResponse(
            success=True,
            data={
                "task_id": task_id,
                "status": "cancelled",
            },
            message="Task cancelled successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.get("/", response_model=ApiResponse[dict])
async def list_tasks(status: Optional[str] = None, limit: int = 100, offset: int = 0):
    """
    Lista las tareas

    - **status**: Estado de filtro (pending, processing, completed, failed, cancelled)
    - **limit**: Límite de cantidad a devolver
    - **offset**: Desplazamiento (offset)
    """
    try:
        task_manager = get_task_manager()
        tasks = await task_manager.list_tasks(status=status, limit=limit, offset=offset)

        return ApiResponse(
            success=True,
            data={
                "tasks": tasks,
                "total": len(tasks),
                "limit": limit,
                "offset": offset,
            },
            message="Tasks retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}",
        )

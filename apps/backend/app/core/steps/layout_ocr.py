"""
Paso de análisis de diseño y procesamiento OCR
"""

import json
import asyncio
from typing import Dict, Any, Optional, Callable, List, Union, Awaitable
from pathlib import Path
from app.core.ocr_client import LayoutAndOCRClient
import httpx
import base64
import os
from app.core.flows.base import ProcessingContext
from app.utils.config import settings
from app.utils.image_processer import crop_image_by_bbox_to_path, vlm_bbox_convert
from app.utils.logger import logger


async def _ocr_with_progress_heartbeat(
    coro: Awaitable[Any],
    progress_callback: Optional[Callable[[float, str], Awaitable[None]]],
    start_pct: float,
    end_pct: float,
    message: str,
) -> Any:
    """Ejecuta el OCR y publica progreso intermedio (evita quedarse congelado en 20%)."""
    if progress_callback:
        await progress_callback(start_pct, message)

    task = asyncio.create_task(coro)
    pct = start_pct
    # Acercamiento asintótico a end_pct mientras espera la respuesta del pipeline
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except asyncio.TimeoutError:
            span = max(0.0, end_pct - start_pct)
            pct = min(end_pct - 0.5, pct + max(0.8, span * 0.06))
            if progress_callback:
                await progress_callback(pct, message)
    return await task


class LayoutOcrStepInput:
    image_files_path: List[str]  # Lista de rutas de archivos de imagen
    page_count: Optional[int]  # Número de páginas
    images_dir: Optional[str]  # Directorio de imágenes

    def __init__(
        self,
        image_files_path: List[str],
        page_count: Optional[int] = None,
        images_dir: Optional[str] = None,
    ) -> None:
        self.image_files_path = image_files_path
        self.page_count = page_count
        self.images_dir = images_dir


async def layout_and_ocr(
    context: ProcessingContext,
    input: LayoutOcrStepInput,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el análisis de diseño y el procesamiento OCR

    Args:
        context: Contexto de procesamiento
        pdf_result: Resultado de PDF a imagen, incluye:
            - output_files: list[str] - Lista de rutas de archivos de imagen
            - page_count: int - Número de páginas
            - images_dir: str - Directorio de imágenes
        progress_callback: Función de callback de progreso

    Returns:
        Dict[str, Any]: Resultado OCR
    """
    task_id = context.task_id
    ocr_config = context.ocr_config

    # Obtener la lista de archivos de imagen
    image_files = input.image_files_path
    images_dir = input.images_dir
    page_count = input.page_count
    page_size = context.metadata.get("page_size")
    logger.info(f"[{task_id}] Starting layout and OCR processing")
    logger.info(f"[{task_id}] Processing {page_count} pages from {images_dir}")

    try:
        # Llamar al servicio real de análisis de diseño y OCR
        # Aquí hay que implementarlo según la API OCR real

        # Ejemplo: supongamos que tenemos un cliente OCR
        result = await _call_ocr_service(
            page_size=page_size,
            image_files=image_files,
            images_dir=images_dir,
            page_count=page_count,
            config=ocr_config,
            output_dir=context.get_output_dir(),
            progress_callback=progress_callback,
        )

        logger.info(f"[{task_id}] Layout and OCR processing completed")

        return result

    except Exception as e:
        logger.error(f"[{task_id}] Layout and OCR processing failed: {e}")
        raise


async def _call_ocr_service(
    image_files: list[str],
    images_dir: str,
    page_count: int,
    config: Dict[str, Any],
    output_dir: str,
    page_size: Dict[str, Any],
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Llama al servicio OCR

    Esta es una implementación de ejemplo; ajústela según su servicio OCR

    Args:
        image_files: Lista de rutas de archivos de imagen
        images_dir: Directorio de imágenes
        page_count: Número de páginas
        config: Configuración OCR
        output_dir: Directorio de salida
        progress_callback: Callback de progreso
    """

    safe_page_count = max(page_count or len(image_files) or 1, 1)
    if progress_callback:
        await progress_callback(
            1.0, f"Inicializando OCR ({safe_page_count} página(s))"
        )
    custom_url = config.get("custom_url", None)
    ocr_profile = config.get("ocr_profile") or "balanced"
    cli = LayoutAndOCRClient()
    pages_result = []
    page_width = page_size.get("width")
    page_height = page_size.get("height")
    block_idx = 1
    ref_image_paths = []
    for i, image_file in enumerate(image_files):
        page_num = i + 1
        start_pct = (i / safe_page_count) * 100.0
        # Deja margen antes del 100% de la página para el post-proceso local
        end_pct = ((i + 0.92) / safe_page_count) * 100.0
        result = await _ocr_with_progress_heartbeat(
            cli.process_single_image(
                image_file, custom_url=custom_url, profile=ocr_profile
            ),
            progress_callback,
            start_pct=max(2.0, start_pct),
            end_pct=end_pct,
            message=f"Reconociendo página {page_num}/{safe_page_count}",
        )
        if progress_callback:
            await progress_callback(
                ((i + 1) / safe_page_count) * 100.0,
                f"Página {page_num}/{safe_page_count} reconocida",
            )
        page_blocks = []
        for idx, block in enumerate(result):
            block_label = block.get("label", "text")
            block_bbox = block.get("bbox_2d", [0, 0, 0, 0])
            block_content = block.get("content", None)
            block_index = block_idx
            normalized_box = vlm_bbox_convert(block_bbox, page_width, page_height)

            # Si label es image, recortar la imagen y añadirla al campo image_path
            image_path_field = None
            if block_label == "image":
                try:
                    # Generar el nombre del archivo segmentado
                    split_filename = f"split_{page_num}_{block_idx:04d}.png"
                    split_path = os.path.join(output_dir, split_filename)
                    crop_image_by_bbox_to_path(image_file, normalized_box, split_path)
                    image_path_field = split_path
                    ref_image_paths.append(image_path_field)
                    logger.info(f"Recortando bloque de imagen {block_idx}: {split_filename}")
                except Exception as e:
                    logger.warning(f"Error al recortar el bloque de imagen {block_idx}: {str(e)}")

            # Construir la información del bloque, añadiendo el campo image_path
            block_info = {
                "layout_type": block_label,
                "layout_box": normalized_box,
                "content": block_content,
                "index": block_index,
                "image_path": image_path_field,  # Para tipo imagen, incluye la ruta recortada
                "page_index": page_num,
            }
            page_blocks.append(block_info)
            block_idx += 1
        # Ejemplo: resultado OCR de cada página
        pages_result.append(
            {
                "page_index": page_num,
                "image_file": image_file,
                "layout": {"blocks": page_blocks},
            }
        )

    if progress_callback:
        await progress_callback(100.0, "OCR processing completed")

    # Guardar el resultado OCR en JSON
    ocr_result_file = Path(output_dir) / "ocr_result.json"
    ocr_result_data = {
        "success": True,
        "pages": pages_result,
        "total_pages": page_count,
        "images_dir": images_dir,
        "ocr_result_file": f"{ocr_result_file}",
        "ref_image_paths": ref_image_paths,
    }

    try:
        with open(ocr_result_file, "w", encoding="utf-8") as f:
            json.dump(ocr_result_data, f, ensure_ascii=False, indent=2)
        logger.info(f"OCR results saved to: {ocr_result_file}")
    except Exception as e:
        logger.error(f"Failed to save OCR results: {e}")

    return ocr_result_data


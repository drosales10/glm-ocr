"""
Implementación del flujo de procesamiento Pipeline

Flujo: PDF a imagen -> análisis de diseño y OCR -> fusión de resultados
"""

import os
from typing import Dict, Any
from pathlib import Path

from app.core.flows.base import FlowFactory, TaskProcessingFlow, ProcessingContext
from app.core.steps.pdf_to_image import PdfToImageStepInput, pdf_to_image
from app.core.steps.layout_ocr import LayoutOcrStepInput, layout_and_ocr
from app.core.steps.merge_results import MergeResultsStepInput, merge_results

from app.utils.logger import logger
from app.utils.config import settings


class PipelineFlow(TaskProcessingFlow):
    """
    Flujo de procesamiento Pipeline

    Pasos de procesamiento:
    1. PDF a imagen (0-20%)
    2. Análisis de diseño y OCR (20-85%)
    3. Fusión de resultados (85-100%)
    """

    # Configuración de pesos de los pasos
    STEP_WEIGHTS = {
        "pdf_to_image": 0.20,  # PDF a imagen representa el 20%
        "layout_and_ocr": 0.65,  # Análisis de diseño + OCR representa el 65%
        "result_merge": 0.15,  # Fusión de resultados representa el 15%
    }

    async def process(self) -> Dict[str, Any]:
        """Ejecuta el flujo Pipeline completo"""

        logger.info(f"[{self.context.task_id}] Starting Pipeline flow")

        # Prepara el directorio de salida
        output_dir = self._prepare_output_dir()
        self.context.set_output_dir(output_dir)

        # Paso 1: PDF a imagen (0-20%)
        pdf_result = await self._step_pdf_to_image()
        self.context.set("pdf_result", pdf_result)
        self.context.set("metadata", pdf_result.get("metadata"))
        self.context.metadata = pdf_result.get("metadata")
        # Paso 2: análisis de diseño y OCR (20-85%)
        ocr_results = await self._step_layout_and_ocr(pdf_result)
        self.context.set("ocr_results", ocr_results)

        # Paso 3: fusión de resultados (85-100%)
        final_result = await self._step_result_merge(ocr_results)

        logger.info(f"[{self.context.task_id}] Pipeline flow completed")

        return {
            "success": True,
            "md_output_path": final_result["md_output_path"],
            "json_output_path": final_result["json_output_path"],
            "output_files": final_result.get("output_files", []),
            "metadata": final_result.get("metadata", {}),
        }

    def _prepare_output_dir(self) -> str:
        """Prepara el directorio de salida"""

        # Crear directorio de salida: output/<task_id>/
        output_base = Path(settings.OUTPUT_DIR) / self.context.task_id
        output_base.mkdir(parents=True, exist_ok=True)

        return str(output_base)

    async def _step_pdf_to_image(self) -> Dict[str, Any]:
        """Paso 1: PDF a imagen"""
        step_name = "pdf_to_image"
        logger.info(f"[{self.context.task_id}] Starting step: {step_name}")

        await self.update_progress(
            step_name=step_name,
            progress=0.0,
            overall_progress=0.0,
            message="Converting PDF to images",
        )

        # Lógica de procesamiento real
        result = await pdf_to_image(
            context=self.context,
            input=PdfToImageStepInput(
                file_path=self.context.file_path,
                output_dir=self.context.get_output_dir(),
                dpi=self.context.ocr_config.get("dpi", 200),
                format=self.context.ocr_config.get("image_format", "png"),
            ),
            progress_callback=lambda p, msg: self.update_progress(
                step_name=step_name,
                progress=p,
                overall_progress=p * self.STEP_WEIGHTS["pdf_to_image"],
                message=msg,
            ),
        )

        await self.update_progress(
            step_name=step_name,
            progress=100.0,
            overall_progress=self.STEP_WEIGHTS["pdf_to_image"] * 100,
            message=f"Converted {result['page_count']} pages to images",
        )

        return result

    async def _step_layout_and_ocr(self, pdf_result: Dict[str, Any]) -> Dict[str, Any]:
        """Paso 2: análisis de diseño y OCR"""
        step_name = "layout_and_ocr"
        logger.info(f"[{self.context.task_id}] Starting step: {step_name}")

        base_progress = self.STEP_WEIGHTS["pdf_to_image"] * 100  # Comienza en el 20%

        await self.update_progress(
            step_name=step_name,
            progress=0.0,
            overall_progress=base_progress,
            message="Starting layout analysis and OCR",
        )

        # Lógica de procesamiento real
        result = await layout_and_ocr(
            context=self.context,
            input=LayoutOcrStepInput(
                image_files_path=pdf_result.get("output_files", []),
                page_count=pdf_result.get("page_count", 0),
                images_dir=pdf_result.get("images_dir", ""),
            ),
            progress_callback=lambda p, msg: self.update_progress(
                step_name=step_name,
                progress=p,
                overall_progress=base_progress
                + p * self.STEP_WEIGHTS["layout_and_ocr"],
                message=msg,
            ),
        )

        await self.update_progress(
            step_name=step_name,
            progress=100.0,
            overall_progress=(
                self.STEP_WEIGHTS["pdf_to_image"] + self.STEP_WEIGHTS["layout_and_ocr"]
            )
            * 100,
            message="Layout analysis and OCR completed",
        )

        return result

    async def _step_result_merge(self, ocr_results: Dict[str, Any]) -> Dict[str, Any]:
        """Paso 3: fusión de resultados"""
        step_name = "result_merge"
        logger.info(f"[{self.context.task_id}] Starting step: {step_name}")

        base_progress = (
            self.STEP_WEIGHTS["pdf_to_image"] + self.STEP_WEIGHTS["layout_and_ocr"]
        ) * 100  # Comienza en el 85%

        await self.update_progress(
            step_name=step_name,
            progress=0.0,
            overall_progress=base_progress,
            message="Merging results",
        )
        input = MergeResultsStepInput(
            ocr_result_path=ocr_results.get("ocr_result_file"),
        )
        # Lógica de procesamiento real
        result = await merge_results(
            context=self.context,
            input=input,
            progress_callback=lambda p, msg: self.update_progress(
                step_name=step_name,
                progress=p,
                overall_progress=base_progress + p * self.STEP_WEIGHTS["result_merge"],
                message=msg,
            ),
        )

        await self.update_progress(
            step_name=step_name,
            progress=100.0,
            overall_progress=100.0,
            message="Results merged",
        )

        return result

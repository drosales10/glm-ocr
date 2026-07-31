"""
Convertidor de PDF
"""

from __future__ import annotations

import io
import os
from typing import Dict, Any

from PIL import Image
import fitz

from app.utils.converters.base import BaseConverter
from app.utils.converters.exceptions import ConversionFailedError
from app.utils.logger import logger


class PDFConverter(BaseConverter):
    """Convertidor de PDF a imagen"""

    name = "pdf_converter"

    supported_extensions = {".pdf"}

    async def convert(
        self,
        file_path: str,
        output_dir: str,
        dpi: int = 200,
        format: str = "png",
        **kwargs
    ) -> Dict[str, Any]:
        """Convierte un PDF a imágenes

        Args:
            file_path: Ruta del archivo PDF
            output_dir: Directorio de salida
            dpi: Configuración de DPI
            format: Formato de salida (png, jpg)
            **kwargs: Otros parámetros

        Returns:
            Dict: Resultado de la conversión
        """
        self.ensure_output_dir(output_dir)

        output_files = []

        try:
            # Abrir el archivo PDF
            pdf_document = fitz.open(file_path)
            page_count = pdf_document.page_count

            # Extraer metadatos del PDF
            metadata = self.get_metadata(file_path)
            metadata.update({
                "title": pdf_document.metadata.get("title", ""),
                "author": pdf_document.metadata.get("author", ""),
                "subject": pdf_document.metadata.get("subject", ""),
                "creator": pdf_document.metadata.get("creator", ""),
                "producer": pdf_document.metadata.get("producer", ""),
                "creation_date": str(pdf_document.metadata.get("creationDate", "")),
                "modification_date": str(pdf_document.metadata.get("modDate", "")),
                "pages": page_count,
                "format": format,
                "dpi": dpi,
            })

            # Establecer la escala (basada en DPI)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            # Almacenar las dimensiones de la primera página
            target_width = None
            target_height = None

            # Convertir cada página
            for page_num in range(page_count):
                # Informar del progreso
                progress = (page_num / page_count) * 100
                if page_num % 5 == 0:  # Informar cada 5 páginas
                    logger.info(
                        f"Progreso de conversión PDF: {progress:.1f}% ({page_num + 1}/{page_count})"
                    )

                page = pdf_document[page_num]

                # Renderizar la página como imagen
                pix = page.get_pixmap(matrix=mat)

                # Si es la primera página, registrar las dimensiones y usarlas como tamaño objetivo
                if page_num == 0:
                    target_width = pix.width
                    target_height = pix.height
                    metadata["page_size"] = {
                        "width": pix.width,
                        "height": pix.height,
                        "dpi": dpi,
                    }
                    metadata["width"] = target_width
                    metadata["height"] = target_height
                    logger.info(f"Dimensiones de la primera página: {pix.width}x{pix.height} (DPI: {dpi})")
                else:
                    # Comprobar si las dimensiones de la página actual coinciden con la primera
                    if pix.width != target_width or pix.height != target_height:
                        logger.warning(
                            f"Las dimensiones de la página {page_num + 1} ({pix.width}x{pix.height}) no coinciden con la primera página ({target_width}x{target_height})"
                        )
                        # Unificar tamaño: redimensionar la página actual al tamaño de la primera
                        img_data = pix.tobytes("png")
                        pil_image = Image.open(io.BytesIO(img_data))
                        resized_image = pil_image.resize(
                            (target_width, target_height), Image.Resampling.LANCZOS
                        )

                        # Guardar la imagen ajustada
                        output_filename = f"page_{page_num + 1:04d}.{format}"
                        output_path = os.path.join(output_dir, output_filename)

                        if format == "png":
                            resized_image.save(output_path, "PNG")
                        elif format == "jpg":
                            resized_image.save(output_path, "JPEG", quality=95)
                        else:
                            raise ValueError(f"Formato de imagen no admitido: {format}")

                        logger.info(
                            f"Página {page_num + 1} ajustada al tamaño unificado: {target_width}x{target_height}"
                        )

                        output_files.append(output_path)
                        continue  # Omitir el flujo normal de guardado

                # Guardar la imagen
                output_filename = f"page_{page_num + 1:04d}.{format}"
                output_path = os.path.join(output_dir, output_filename)

                if format == "png":
                    pix.save(output_path)
                elif format == "jpg":
                    pix.save(output_path, jpeg=True)
                else:
                    raise ValueError(f"Formato de imagen no admitido: {format}")

                output_files.append(output_path)

            pdf_document.close()

            return {
                "output_files": output_files,
                "page_count": page_count,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error al convertir el PDF: {str(e)}")
            raise ConversionFailedError(f"Error al convertir el PDF: {str(e)}") from e

    async def validate(self, file_path: str) -> bool:
        """Valida el archivo PDF

        Args:
            file_path: Ruta del archivo PDF

        Returns:
            bool: Si es válido
        """
        try:
            # Comprobar si el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"El archivo PDF no existe: {file_path}")
                return False

            # Comprobar la extensión del archivo
            if not file_path.lower().endswith(".pdf"):
                logger.error(f"No es un archivo PDF: {file_path}")
                return False

            # Comprobar el tamaño del archivo
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error("El archivo PDF está vacío")
                return False

            # Intentar abrir el PDF para validarlo
            pdf_document = fitz.open(file_path)
            page_count = pdf_document.page_count
            pdf_document.close()

            if page_count == 0:
                logger.error("El archivo PDF no tiene páginas")
                return False

            logger.info(f"Validación de PDF correcta, {page_count} páginas")
            return True

        except Exception as e:
            logger.error(f"Error al validar el archivo PDF: {str(e)}")
            return False

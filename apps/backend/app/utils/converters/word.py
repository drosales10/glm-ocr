"""
Convertidor de documentos Word
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Dict, Any

from app.utils.converters.base import BaseConverter
from app.utils.converters.exceptions import ConversionFailedError, ConversionTimeoutError
from app.utils.config import settings
from app.utils.logger import logger


class WordConverter(BaseConverter):
    """Convertidor de documentos Word a PDF"""

    name = "word_converter"

    supported_extensions = {".doc", ".docx"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Elegir el comando de LibreOffice según el entorno
        self.libreoffice_cmd = (
            "soffice" if settings.environment == "development" else "libreoffice"
        )

    async def convert(
        self,
        file_path: str,
        output_dir: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Convierte un documento Word a PDF

        Args:
            file_path: Ruta del documento Word
            output_dir: Directorio de salida
            **kwargs: Otros parámetros

        Returns:
            Dict: Resultado de la conversión (incluye la ruta del archivo PDF)
        """
        self.ensure_output_dir(output_dir)

        try:
            # Crear un directorio temporal para la conversión
            temp_dir = tempfile.mkdtemp(prefix="word_convert_")

            try:
                logger.info(f"Iniciando conversión de documento Word a PDF: {file_path}")

                # Usar LibreOffice para la conversión
                cmd = [
                    self.libreoffice_cmd,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", temp_dir,
                    file_path
                ]

                logger.info(f"Ejecutando comando: {' '.join(cmd)}")

                # Ejecutar el comando de conversión
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,  # tiempo de espera de 2 minutos
                    check=True
                )

                logger.info(f"Salida de LibreOffice: {result.stdout}")
                if result.stderr:
                    logger.warning(f"Advertencia de LibreOffice: {result.stderr}")

                # Buscar el archivo PDF generado
                word_filename = os.path.basename(file_path)
                pdf_filename = os.path.splitext(word_filename)[0] + ".pdf"
                pdf_path = os.path.join(temp_dir, pdf_filename)

                if not os.path.exists(pdf_path):
                    # Intentar encontrar cualquier PDF generado
                    pdf_files = [f for f in os.listdir(temp_dir) if f.endswith('.pdf')]
                    if pdf_files:
                        pdf_path = os.path.join(temp_dir, pdf_files[0])
                    else:
                        raise FileNotFoundError(f"LibreOffice no generó el archivo PDF: {file_path}")

                # Mover el PDF al directorio de salida final
                final_pdf_path = os.path.join(output_dir, os.path.basename(pdf_path))
                shutil.move(pdf_path, final_pdf_path)

                logger.info(f"Documento Word convertido correctamente, PDF guardado en: {final_pdf_path}")

                # Devolver el resultado de la conversión
                metadata = self.get_metadata(file_path)
                metadata.update({
                    "converted_from": "word_document",
                    "pdf_path": final_pdf_path,
                    "original_format": os.path.splitext(word_filename)[1],
                })

                return {
                    "output_files": [final_pdf_path],
                    "page_count": 0,  # Tras Word→PDF, el convertidor PDF determina el número de páginas
                    "metadata": metadata,
                    "pdf_path": final_pdf_path,  # También se devuelve la ruta del PDF para uso posterior
                }

            finally:
                # Limpiar el directorio temporal
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Error al limpiar el directorio temporal: {str(e)}")

        except subprocess.TimeoutExpired as e:
            logger.error("Tiempo de espera agotado al convertir el documento Word")
            raise ConversionTimeoutError(
                "Tiempo de espera agotado al convertir el documento Word; compruebe si el archivo es demasiado grande o si LibreOffice funciona correctamente"
            ) from e
        except subprocess.CalledProcessError as e:
            logger.error(f"Error de conversión de LibreOffice: {e.stderr}")
            raise ConversionFailedError(f"Error al convertir el documento Word: {e.stderr}") from e
        except Exception as e:
            logger.error(f"Excepción al convertir el documento Word: {str(e)}")
            raise ConversionFailedError(f"Excepción al convertir el documento Word: {str(e)}") from e

    async def validate(self, file_path: str) -> bool:
        """Valida el documento Word y el entorno de LibreOffice

        Args:
            file_path: Ruta del documento Word

        Returns:
            bool: Si es válido
        """
        try:
            # Comprobar si el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"El documento Word no existe: {file_path}")
                return False

            # Comprobar la extensión del archivo
            if not self.can_handle(file_path):
                logger.error(f"No es un documento Word: {file_path}")
                return False

            # Comprobar el tamaño del archivo
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error("El documento Word está vacío")
                return False

            # Comprobar si LibreOffice está disponible
            try:
                result = subprocess.run(
                    [self.libreoffice_cmd, "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"Validación de documento Word correcta, LibreOffice disponible")
                    return True
                else:
                    logger.error("LibreOffice no está instalado o no está disponible; no se puede convertir el documento Word")
                    return False
            except FileNotFoundError:
                logger.error("No se encontró LibreOffice; no se puede convertir el documento Word")
                return False
            except Exception as e:
                logger.error(f"Error al comprobar LibreOffice: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"Error al validar el documento Word: {str(e)}")
            return False

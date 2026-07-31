"""
Servicio unificado de conversión de archivos - detecta el tipo y convierte automáticamente
"""

from __future__ import annotations

import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.utils.converters.base import BaseConverter
from app.utils.converters.exceptions import UnsupportedFormatError, ConversionFailedError
from app.utils.logger import logger


class FileConverterService:
    """Servicio de conversión de archivos - interfaz unificada"""

    def __init__(self, default_dpi: int = 200, default_format: str = "png"):
        """Inicializa el servicio de conversión

        Args:
            default_dpi: DPI predeterminado
            default_format: Formato de salida predeterminado
        """
        self.default_dpi = default_dpi
        self.default_format = default_format

    async def convert(
        self,
        file_path: str,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Convierte un archivo a imagen (detecta el tipo automáticamente)

        Esta es la única interfaz pública; detecta el tipo de archivo y elige el convertidor adecuado

        Args:
            file_path: Ruta del archivo de entrada (admite PDF, imágenes, documentos Word)
            output_dir: Directorio de salida (si es None, se crea automáticamente)
            **kwargs: Parámetros de conversión
                - dpi: Configuración de DPI (solo válida para PDF)
                - format: Formato de salida (png, jpg, etc.)
                - Otros parámetros específicos del convertidor

        Returns:
            Dict[str, Any]: Resultado de la conversión, incluye:
                - output_files: List[str] - Lista de rutas de archivos de imagen de salida
                - page_count: int - Número de páginas/imágenes
                - metadata: Dict - Información de metadatos

        Raises:
            UnsupportedFormatError: Formato de archivo no admitido
            ConversionFailedError: Conversión fallida

        Examples:
            >>> service = FileConverterService()
            >>> # Convertir PDF
            >>> result = await service.convert("document.pdf")
            >>> images = result["output_files"]
            >>> metadata = result["metadata"]
            >>> # Convertir imagen
            >>> result = await service.convert("photo.jpg")
            >>> # Convertir documento Word
            >>> result = await service.convert("report.docx")
            >>> # Especificar directorio de salida y DPI
            >>> result = await service.convert("doc.pdf", output_dir="/tmp/output", dpi=300)
        """
        # Validar que el archivo exista
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"El archivo no existe: {file_path}")

        # Determinar el directorio de salida
        if output_dir is None:
            # Crear automáticamente el directorio de salida
            output_dir = os.path.join(
                os.path.dirname(file_path),
                f"converted_{Path(file_path).stem}"
            )

        # Obtener el convertidor (importación diferida para evitar ciclos)
        from app.utils.converters import ConverterFactory
        converter = ConverterFactory.get_converter(file_path)

        logger.info(f"Iniciando conversión del archivo: {file_path}")
        logger.info(f"Usando convertidor: {converter.name}")
        logger.info(f"Directorio de salida: {output_dir}")

        # Tratamiento especial de documentos Word (requiere conversión en dos pasos)
        if converter.name == "word_converter":
            return await self._convert_word_document(
                file_path, output_dir, **kwargs
            )

        # Conversión directa (PDF o imagen)
        # Extraer los parámetros dpi y format; usar valores predeterminados
        dpi = kwargs.pop("dpi", self.default_dpi)
        format = kwargs.pop("format", self.default_format)

        result = await converter.convert(
            file_path,
            output_dir,
            dpi=dpi,
            format=format,
            **kwargs  # kwargs ya no incluye dpi ni format
        )

        output_files = result["output_files"]
        page_count = result["page_count"]
        metadata = result["metadata"]

        logger.info(f"Conversión completada, se generaron {len(output_files)} archivos")

        return {
            "output_files": output_files,
            "page_count": page_count,
            "metadata": metadata,
        }

    async def _convert_word_document(
        self,
        file_path: str,
        output_dir: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Procesa un documento Word (primero a PDF, luego a imagen)

        Args:
            file_path: Ruta del documento Word
            output_dir: Directorio de salida
            **kwargs: Parámetros de conversión

        Returns:
            Dict[str, Any]: Resultado de la conversión, incluye:
                - output_files: List[str] - Lista de rutas de archivos de imagen de salida
                - page_count: int - Número de páginas/imágenes
                - metadata: Dict - Información de metadatos
        """
        from app.utils.converters import WordConverter, PDFConverter

        # Extraer los parámetros dpi y format; usar valores predeterminados
        dpi = kwargs.pop("dpi", self.default_dpi)
        format = kwargs.pop("format", self.default_format)

        # Step 1: Word -> PDF
        word_converter = WordConverter()
        word_result = await word_converter.convert(file_path, output_dir)
        pdf_path = word_result["pdf_path"]

        # Step 2: PDF -> Images
        pdf_converter = PDFConverter()
        pdf_result = await pdf_converter.convert(
            pdf_path, output_dir, dpi=dpi, format=format
        )

        # Fusionar metadatos
        pdf_result["metadata"]["source_file"] = file_path
        pdf_result["metadata"]["converted_from"] = "word_document"
        pdf_result["metadata"]["word_metadata"] = word_result["metadata"]

        # Eliminar el archivo PDF temporal
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(f"Archivo PDF temporal eliminado: {pdf_path}")
        except Exception as e:
            logger.warning(f"Error al eliminar el archivo PDF temporal: {str(e)}")

        return {
            "output_files": pdf_result["output_files"],
            "page_count": pdf_result["page_count"],
            "metadata": pdf_result["metadata"],
        }

    async def validate(self, file_path: str) -> bool:
        """Valida si el archivo se puede convertir

        Args:
            file_path: Ruta del archivo

        Returns:
            bool: Si se puede convertir
        """
        try:
            from app.utils.converters import ConverterFactory
            converter = ConverterFactory.get_converter(file_path)
            return await converter.validate(file_path)
        except Exception:
            return False

    @staticmethod
    def get_supported_formats() -> List[str]:
        """Obtiene todos los formatos de archivo admitidos

        Returns:
            List[str]: Lista de extensiones de archivo admitidas
        """
        from app.utils.converters import ConverterFactory
        return ConverterFactory.get_supported_formats()

    @staticmethod
    def is_supported(file_path: str) -> bool:
        """Comprueba si el formato de archivo está admitido

        Args:
            file_path: Ruta del archivo

        Returns:
            bool: Si está admitido
        """
        try:
            from app.utils.converters import ConverterFactory
            ConverterFactory.get_converter(file_path)
            return True
        except UnsupportedFormatError:
            return False


# Crear la instancia predeterminada
default_converter = FileConverterService()


# Función de conveniencia
async def convert_file(
    file_path: str,
    output_dir: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Convierte un archivo a imagen (función de conveniencia)

    Args:
        file_path: Ruta del archivo de entrada
        output_dir: Directorio de salida (opcional)
        **kwargs: Parámetros de conversión

    Returns:
        Dict[str, Any]: Resultado de la conversión, incluye:
            - output_files: List[str] - Lista de rutas de archivos de imagen de salida
            - page_count: int - Número de páginas/imágenes
            - metadata: Dict - Información de metadatos

    Examples:
        >>> from app.utils.converters import convert_file
        >>> result = await convert_file("document.pdf")
        >>> images = result["output_files"]
        >>> metadata = result["metadata"]
        >>> result = await convert_file("photo.jpg", output_dir="/tmp/output")
    """
    return await default_converter.convert(file_path, output_dir, **kwargs)

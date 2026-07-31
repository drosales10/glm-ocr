"""
Fábrica y registro de convertidores
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Type

from app.utils.converters.base import BaseConverter
from app.utils.converters.pdf import PDFConverter
from app.utils.converters.image import ImageConverter
from app.utils.converters.word import WordConverter
from app.utils.converters.converter import FileConverterService, default_converter, convert_file
from app.utils.converters.exceptions import UnsupportedFormatError
from app.utils.logger import logger


class ConverterFactory:
    """Fábrica de convertidores"""

    # Registro de convertidores
    _converters: Dict[str, Type[BaseConverter]] = {}

    @classmethod
    def register(cls, converter_class: Type[BaseConverter]) -> None:
        """Registra un convertidor

        Args:
            converter_class: Clase del convertidor
        """
        converter = converter_class()
        for ext in converter.supported_extensions:
            cls._converters[ext] = converter_class
        logger.info(f"Convertidor registrado: {converter.name}, extensiones admitidas: {converter.supported_extensions}")

    @classmethod
    def get_converter(cls, file_path: str) -> BaseConverter:
        """Obtiene el convertidor adecuado según la ruta del archivo

        Args:
            file_path: Ruta del archivo

        Returns:
            BaseConverter: Instancia del convertidor

        Raises:
            UnsupportedFormatError: Formato de archivo no admitido
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext not in cls._converters:
            supported_formats = list(cls._converters.keys())
            raise UnsupportedFormatError(
                f"Formato de archivo no admitido: {ext}. Formatos admitidos: {supported_formats}"
            )

        converter_class = cls._converters[ext]
        return converter_class()

    @classmethod
    def get_converter_by_name(cls, name: str) -> Optional[BaseConverter]:
        """Obtiene el convertidor por nombre

        Args:
            name: Nombre del convertidor

        Returns:
            Optional[BaseConverter]: Instancia del convertidor; None si no existe
        """
        for converter_class in cls._converters.values():
            converter = converter_class()
            if converter.name == name:
                return converter
        return None

    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Obtiene todos los formatos de archivo admitidos

        Returns:
            List[str]: Lista de extensiones de archivo admitidas
        """
        return list(cls._converters.keys())

    @classmethod
    def list_converters(cls) -> List[str]:
        """Lista los nombres de todos los convertidores registrados

        Returns:
            List[str]: Lista de nombres de convertidores
        """
        names = set()
        for converter_class in cls._converters.values():
            converter = converter_class()
            names.add(converter.name)
        return list(names)


# Registrar todos los convertidores
def register_default_converters():
    """Registra los convertidores predeterminados"""
    ConverterFactory.register(PDFConverter)
    ConverterFactory.register(ImageConverter)
    ConverterFactory.register(WordConverter)


# Registrar automáticamente los convertidores predeterminados
register_default_converters()


# Exportaciones
__all__ = [
    # Fábrica y clases base
    "ConverterFactory",
    "BaseConverter",

    # Convertidores concretos
    "PDFConverter",
    "ImageConverter",
    "WordConverter",

    # Servicio unificado (uso recomendado)
    "FileConverterService",
    "default_converter",
    "convert_file",

    # Excepciones
    "UnsupportedFormatError",
    "ConversionFailedError",
    "ConversionTimeoutError",
    "ConverterValidationError",
]

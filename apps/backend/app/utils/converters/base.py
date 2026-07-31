"""
Clase base de convertidores
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.utils.logger import logger


class BaseConverter(ABC):
    """Clase base de convertidores"""

    # Nombre del convertidor
    name: str = "base"

    # Extensiones de archivo admitidas
    supported_extensions: set[str] = set()

    def __init__(self, **kwargs):
        """Inicializa el convertidor

        Args:
            **kwargs: Configuración específica del convertidor
        """
        self.config = kwargs

    @abstractmethod
    async def convert(
        self, file_path: str, output_dir: str, **kwargs
    ) -> Dict[str, Any]:
        """Convierte el archivo

        Args:
            file_path: Ruta del archivo de entrada
            output_dir: Directorio de salida
            **kwargs: Parámetros de conversión (p. ej. dpi, format)

        Returns:
            Dict: {
                "output_files": List[str],  # Lista de archivos de salida
                "page_count": int,           # Número de páginas/imágenes
                "metadata": Dict             # Metadatos
            }

        Raises:
            ConversionFailedError: Conversión fallida
            ConversionTimeoutError: Tiempo de espera de conversión agotado
        """
        pass

    @abstractmethod
    async def validate(self, file_path: str) -> bool:
        """Valida si el archivo puede ser procesado por este convertidor

        Args:
            file_path: Ruta del archivo

        Returns:
            bool: Si se puede procesar el archivo

        Raises:
            ConverterValidationError: Validación fallida
        """
        pass

    def can_handle(self, file_path: str) -> bool:
        """Comprueba si el convertidor puede procesar el archivo

        Args:
            file_path: Ruta del archivo

        Returns:
            bool: Si se puede procesar
        """
        extension = Path(file_path).suffix.lower()
        return extension in self.supported_extensions

    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """Obtiene los metadatos del archivo

        Args:
            file_path: Ruta del archivo

        Returns:
            Dict: Diccionario de metadatos
        """
        return {
            "source_file": file_path,
            "converter": self.name,
            "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        }

    def ensure_output_dir(self, output_dir: str) -> None:
        """Asegura que el directorio de salida exista

        Args:
            output_dir: Ruta del directorio de salida
        """
        os.makedirs(output_dir, exist_ok=True)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(extensions={self.supported_extensions})>"

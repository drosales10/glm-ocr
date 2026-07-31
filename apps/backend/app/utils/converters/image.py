"""
Convertidor de imágenes
"""

from __future__ import annotations

import os
from typing import Dict, Any

from PIL import Image

from app.utils.converters.base import BaseConverter
from app.utils.converters.exceptions import ConversionFailedError
from app.utils.logger import logger


class ImageConverter(BaseConverter):
    """Convertidor de formato de imagen (convierte unificadamente a PNG)"""

    name = "image_converter"

    supported_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}

    async def convert(
        self,
        file_path: str,
        output_dir: str,
        format: str = "png",
        **kwargs
    ) -> Dict[str, Any]:
        """Convierte la imagen al formato especificado (PNG por defecto)

        Args:
            file_path: Ruta del archivo de imagen
            output_dir: Directorio de salida
            format: Formato de salida (png por defecto)
            **kwargs: Otros parámetros

        Returns:
            Dict: Resultado de la conversión
        """
        self.ensure_output_dir(output_dir)

        try:
            # Abrir el archivo de imagen
            with Image.open(file_path) as img:
                width, height = img.size
                original_format = img.format.lower() if img.format else "unknown"

                logger.info(f"Dimensiones de la imagen: {width}x{height}, formato original: {original_format}")

                # Obtener información de DPI
                dpi_info = getattr(img, "info", {}).get("dpi", (None, None))

                page_size = {
                    "width": width,
                    "height": height,
                    "dpi": dpi_info,
                }

                # Guardar metadatos de la imagen
                metadata = self.get_metadata(file_path)
                metadata.update({
                    "width": width,
                    "height": height,
                    "format": format,  # Formato de salida
                    "original_format": original_format,  # Formato original
                    "dpi": dpi_info,
                    "mode": img.mode,
                    "pages": 1,
                    "page_size": page_size,
                })

                # Construir la ruta del archivo de salida
                output_filename = f"page_0001.{format}"
                output_path = os.path.join(output_dir, output_filename)

                # Convertir la imagen a modo RGB (si es necesario) y guardar en el formato especificado
                if format == "png":
                    if img.mode in ("RGBA", "P"):
                        # Si es RGBA o modo paleta, convertir a RGB
                        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "RGBA":
                            rgb_img.paste(img, mask=img.split()[3])  # Usar el canal alpha como máscara
                        else:
                            rgb_img.paste(img)
                        rgb_img.save(output_path, "PNG")
                    else:
                        img.save(output_path, "PNG")
                elif format == "jpg":
                    if img.mode in ("RGBA", "P"):
                        # JPEG no admite transparencia; hace falta convertir
                        rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "RGBA":
                            rgb_img.paste(img, mask=img.split()[3])
                        else:
                            rgb_img.paste(img)
                        rgb_img.save(output_path, "JPEG", quality=95)
                    else:
                        img.save(output_path, "JPEG", quality=95)
                else:
                    raise ValueError(f"Formato de salida no admitido: {format}")

                logger.info(f"Imagen guardada en: {output_path}")

                return {
                    "output_files": [output_path],
                    "page_count": 1,
                    "metadata": metadata,
                }

        except Exception as e:
            logger.error(f"Error al convertir la imagen: {str(e)}")
            raise ConversionFailedError(f"Error al convertir la imagen: {str(e)}") from e

    async def validate(self, file_path: str) -> bool:
        """Valida el archivo de imagen

        Args:
            file_path: Ruta del archivo de imagen

        Returns:
            bool: Si es válido
        """
        try:
            # Comprobar si el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"El archivo de imagen no existe: {file_path}")
                return False

            # Comprobar la extensión del archivo
            if not self.can_handle(file_path):
                logger.error(f"Formato de imagen no admitido: {file_path}")
                return False

            # Comprobar el tamaño del archivo
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error("El archivo de imagen está vacío")
                return False

            # Intentar abrir la imagen para validarla
            with Image.open(file_path) as img:
                width, height = img.size
                logger.info(f"Validación de imagen correcta, dimensiones: {width}x{height}")
                return True

        except Exception as e:
            logger.error(f"Error al validar el archivo de imagen: {str(e)}")
            return False

import base64
from pathlib import Path
import os
from typing import List
from PIL import Image


def encode_image(image_path: str) -> str:
    """Codifica un archivo de imagen como cadena base64.

    Args:
        image_path: Ruta del archivo de imagen

    Returns:
        Cadena de imagen codificada en Base64

    Raises:
        ImageEncodingError: Si falla la codificación de la imagen
    """
    try:
        path = Path(image_path)
        if not path.exists():
            raise Exception(f"Image file not found: {image_path}")

        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return f"<|base64|>{encoded_string}"
    except Exception as e:
        raise Exception(f"Failed to encode image {image_path}: {str(e)}")


def crop_image_by_bbox_to_path(
    source_image_path: str,
    bbox: List[int],
    output_path: str,
) -> str:
    """
    Recorta la imagen según el bbox a la ruta especificada

    Args:
        source_image_path: Ruta de la imagen de origen
        bbox: Cuadro delimitador [x1, y1, x2, y2]
        output_path: Ruta completa del archivo de salida

    Returns:
        Ruta de la imagen recortada (igual que output_path de entrada)
    """
    # Asegura que el directorio de salida exista
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Abrir la imagen de origen
    with Image.open(source_image_path) as img:
        # Formato bbox: [x1, y1, x2, y2]
        # crop de PIL usa: (left, upper, right, lower)
        x1, y1, x2, y2 = bbox

        # Recortar la imagen
        cropped_img = img.crop((x1, y1, x2, y2))

        # Guardar la imagen recortada
        cropped_img.save(output_path)

        return output_path

def vlm_bbox_convert(layout_box: List, page_width: int, page_height: int):
    normalized_box = [
        round(int(layout_box[0] * page_width / 1000)),  # x1
        round(int(layout_box[1] * page_height / 1000)),  # y1
        round(int(layout_box[2] * page_width / 1000)),  # x2
        round(int(layout_box[3] * page_height / 1000)),  # y2
    ]
    return normalized_box

import json
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import httpx
import base64
from app.utils.config import settings
from app.utils.logger import logger
class ServiceRequestError(Exception):
    """Error de solicitud al servicio"""

    pass


class ServiceResponseError(Exception):
    """Error de respuesta del servicio"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")
class LayoutAndOCRClient:
    """Cliente del servicio de análisis de layout y reconocimiento OCR.

    Formato de la solicitud:
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,{image1_data}"}},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,{image2_data}"}},
                        {"type": "text", "text": "<|PIPELINE_DOCUMENT_RECOGNITION|>"}
                    ]
                }
            ]
        }

    Formato de la respuesta:
        [
            [
                {
                    "index": 0,
                    "label": "text",
                    "bbox_2d": [100, 200, 800, 350],
                    "content": "Este es el contenido del primer párrafo..."
                },
                {
                    "index": 1,
                    "label": "table",
                    "bbox_2d": [150, 400, 850, 700],
                    "content": "<td></td>..."  # Las tablas se generan en formato HTML
                },
                {
                    "index": 2,
                    "label": "formula",
                    "bbox_2d": [200, 750, 600, 850],
                    "content": "\\[\n5 2 \\times 4\n\\]"  # Las fórmulas se generan en formato LaTeX
                },
                {
                    "index": 3,
                    "label": "image",
                    "bbox_2d": [210, 400, 5500, 630],
                    "content": None  # El campo content de la imagen es None
                }
            ],
            # Resultado del reconocimiento de la segunda imagen...
        ]
    """

    # Prompt predeterminado de layout y OCR
    DEFAULT_PROMPT = "<|PIPELINE_DOCUMENT_RECOGNITION|>"

    def __init__(self, service_url: Optional[str] = None, timeout: float = 600.0):
        """Inicializa el cliente LayoutAndOCR.

        Args:
            service_url: URL del servicio. Si es None, se carga desde la configuración.
            timeout: Tiempo de espera de la solicitud (segundos). Por defecto 10 min
                para documentos grandes en despliegue local.
        """
        self.service_url = service_url or getattr(settings, "layout_ocr_url", None)
        if not self.service_url:
            # Configuración predeterminada
            self.service_url = "http://localhost:5002/glmocr/parse"

        self.timeout = timeout
        self.async_headers = {"Content-Type": "application/json"}

    def _encode_image_to_base64(self, image_path: str) -> str:
        """Codifica el archivo de imagen en formato base64.

        Args:
            image_path: Ruta del archivo de imagen

        Returns:
            Cadena URL de imagen codificada en base64
        """

        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Obtener la extensión del archivo para determinar el tipo MIME
        ext = Path(image_path).suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
        }.get(ext, "image/png")

        return f"data:{mime_type};base64,{image_data}"

    def _create_multi_image_payload(
        self,
        image_paths: List[str]
    ) -> Dict[str, Any]:
        """Crea la carga útil de la solicitud para reconocimiento de varias imágenes.

        Args:
            image_paths: Lista de rutas de archivos de imagen

        Returns:
            Diccionario de la carga útil de la solicitud
        """
        if not image_paths:
            raise ValueError("Se requiere al menos una imagen")

        # Añadir todas las imágenes
        image_base64_list = []
        for image_path in image_paths:
            image_base64 = self._encode_image_to_base64(image_path)
            image_base64_list.append(image_base64)

        return {"images": image_base64_list}

    def _create_single_image_payload(
        self,
        image_path: str
    ) -> Dict[str, Any]:
        """Crea la carga útil de la solicitud para reconocimiento de una sola imagen.

        Args:
            image_path: Ruta del archivo de imagen

        Returns:
            Diccionario de la carga útil de la solicitud
        """
        return self._create_multi_image_payload([image_path])

    async def process_images(
        self,
        image_paths: Union[str, List[str]],
        prompt: Optional[str] = None,
        custom_url: Optional[str] = None,
    ) -> List[List[Dict[str, Any]]]:
        """Procesa una o varias imágenes y devuelve resultados de layout y OCR.

        Args:
            image_paths: Ruta de una imagen o lista de rutas de imágenes
            prompt: Prompt personalizado
            custom_url: URL personalizada del servicio; sustituye la URL de inicialización

        Returns:
            Lista de resultados de reconocimiento; cada elemento corresponde a una imagen:
            [
                [
                    {
                        "index": 0,
                        "label": "text",
                        "bbox_2d": [100, 200, 800, 350],
                        "content": "contenido de texto"
                    },
                    ...
                ],
                # Resultado de la segunda imagen...
            ]

        Raises:
            ServiceRequestError: Si la solicitud falla
            ServiceResponseError: Si el servicio devuelve una respuesta de error
        """
        url = custom_url if custom_url is not None else self.service_url
        # Normalizar a una lista
        if isinstance(image_paths, str):
            image_paths = [image_paths]

        logger.info(
            f"Processing {len(image_paths)} images with layout and OCR,url is:{url}"
        )

        # Crear la carga útil de la solicitud
        payload = self._create_multi_image_payload(image_paths)

        try:
            async with httpx.AsyncClient(
                headers=self.async_headers, timeout=self.timeout, verify=False
            ) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()

                    # Extraer el contenido
                    if "json_result" in result and len(result["json_result"]) > 0:
                        content = result["json_result"]

                        # Parsear el resultado JSON
                        try:
                            # Comprobar el tipo de content; si ya es una lista, usarlo directamente
                            if isinstance(content, list):
                                all_results = content
                            else:
                                all_results = json.loads(content)
                                
                            # Validar el formato de la respuesta
                            if not isinstance(all_results, list):
                                raise ValueError("Formato de respuesta incorrecto: se esperaba una lista")

                            # Validar el resultado de cada imagen
                            for img_idx, img_result in enumerate(all_results):
                                if not isinstance(img_result, list):
                                    logger.warning(
                                        f"Formato de resultado incorrecto para la imagen {img_idx}, se esperaba una lista"
                                    )
                                    continue

                                # Validar el formato de cada bloque
                                for block in img_result:
                                    if not isinstance(block, dict):
                                        continue
                                    # Asegurar que existan los campos obligatorios
                                    if "index" not in block:
                                        block["index"] = 0
                                    if "label" not in block:
                                        block["label"] = "text"
                                    if "bbox_2d" not in block:
                                        block["bbox_2d"] = [0, 0, 0, 0]
                                    # El campo content puede ser None (p. ej. imágenes)

                            total_blocks = sum(len(img) for img in all_results)
                            logger.info(
                                f"Successfully processed {len(image_paths)} images, "
                                f"found {total_blocks} blocks total"
                            )

                            return all_results

                        except json.JSONDecodeError as e:
                            error_msg = f"Failed to parse response JSON: {str(e)}"
                            logger.error(f"Response content: {content[:500]}...")
                            raise ServiceRequestError(error_msg)
                    else:
                        error_msg = "Response missing 'choices' field"
                        logger.error(f"Response: {result}")
                        raise ServiceResponseError(response.status_code, error_msg)

                else:
                    error_msg = f"Service returned status code {response.status_code}"
                    try:
                        error_detail = response.json()
                        if isinstance(error_detail, dict):
                            error_detail = error_detail.get("error", {}).get(
                                "message", ""
                            )
                        elif isinstance(error_detail, str):
                            error_detail = error_detail
                        if error_detail:
                            error_msg += f": {error_detail}"
                    except Exception:
                        pass
                    logger.error(f"Service error: {error_msg}")
                    raise ServiceResponseError(response.status_code, error_msg)

        except httpx.RequestError as e:
            error_msg = f"Failed to make request to service: {str(e)}"
            logger.error(error_msg)
            raise ServiceRequestError(error_msg)
        except (KeyError, ValueError) as e:
            error_msg = f"Failed to parse service response: {str(e)}"
            logger.error(error_msg)
            raise ServiceRequestError(error_msg)

    async def process_single_image(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        custom_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Procesa una sola imagen y devuelve resultados de layout y OCR.

        Args:
            image_path: Ruta del archivo de imagen
            prompt: Prompt personalizado
            custom_url: URL personalizada del servicio

        Returns:
            Lista de resultados de reconocimiento de una sola imagen
        """
        results = await self.process_images(image_path, prompt, custom_url)
        return results[0] if results else []

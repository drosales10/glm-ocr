from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile

from app.utils.config import settings
from app.utils.logger import logger


class FileUploadHandler:
    """Procesador de carga de archivos; solo valida y guarda"""

    DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".gif",
        ".tiff",
        ".tif",
        ".webp",
    }

    DOCUMENT_MIME_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    def __init__(self) -> None:
        pass

    def valid(self, file: UploadFile) -> bool:
        """Valida si el archivo es PDF, Word o un tipo de imagen común"""
        filename = (file.filename or "").strip()
        suffix = Path(filename).suffix.lower()
        content_type = (file.content_type or "").lower()

        if suffix in self.DOCUMENT_EXTENSIONS or suffix in self.IMAGE_EXTENSIONS:
            return True

        if content_type in self.DOCUMENT_MIME_TYPES or content_type.startswith("image/"):
            return True

        return False

    async def save_to_path(
        self, file: UploadFile, filename: str | None = None, upload_dir: str | Path | None = None
    ) -> str:
        """Tras validar, guarda el archivo subido en el directorio indicado y devuelve la ruta"""
        if not self.valid(file):
            raise HTTPException(status_code=400, detail="Solo se admiten archivos PDF, Word o imágenes comunes")

        safe_name = Path(filename or file.filename or "upload").name
        base_dir = Path(upload_dir) if upload_dir else Path(settings.OUTPUT_DIR)
        dest_path = base_dir / safe_name
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        await file.seek(0)
        async with aiofiles.open(dest_path, "wb") as target:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await target.write(chunk)

        logger.info("Archivo guardado en: %s", dest_path)
        return str(dest_path)


# Instancia global del procesador de carga de archivos
file_upload_handler = FileUploadHandler()
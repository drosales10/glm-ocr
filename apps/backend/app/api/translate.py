"""
Traducción de la transcripción OCR.
"""
import asyncio

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.translator import (
    TranslationModelUnavailable,
    UnsupportedLanguage,
    list_languages,
    translate_markdown,
)
from app.schemas.response import ApiResponse
from app.utils.logger import logger


router = APIRouter(prefix="/translate", tags=["translate"])


class LanguageData(BaseModel):
    code: str
    name: str


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Markdown de la transcripción")
    source_lang: str = Field(..., min_length=2, max_length=16)
    target_lang: str = Field(..., min_length=2, max_length=16)


class TranslateResult(BaseModel):
    translated: str
    source_lang: str
    target_lang: str


@router.get("/languages", response_model=ApiResponse[list[LanguageData]])
async def get_languages():
    """Idiomas de origen y destino disponibles para NLLB."""
    data = [LanguageData(**item) for item in list_languages()]
    return ApiResponse(success=True, data=data)


@router.post("", response_model=ApiResponse[TranslateResult])
async def translate(body: TranslateRequest):
    """
    Traduce el Markdown del OCR.

    Conserva imágenes, bloques de código y fórmulas. Si origen y destino
    coinciden, devuelve el texto original.
    """
    if not body.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay texto para traducir",
        )

    source = body.source_lang.strip().lower()
    target = body.target_lang.strip().lower()

    try:
        translated = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda text=body.text, source_lang=source, target_lang=target: translate_markdown(
                text, source_lang, target_lang
            ),
        )
    except UnsupportedLanguage as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TranslationModelUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Translation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo traducir la transcripción",
        ) from exc

    return ApiResponse(
        success=True,
        data=TranslateResult(
            translated=translated,
            source_lang=source,
            target_lang=target,
        ),
        message="Traducción completada",
    )

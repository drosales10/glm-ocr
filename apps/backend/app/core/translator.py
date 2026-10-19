"""
Traducción local del Markdown de OCR con NLLB-200.

Los pesos se leen de la caché de VoiceStudio (`local_files_only`).
Imágenes, código, fórmulas y HTML de figuras no se envían al modelo.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from app.utils.config import settings
from app.utils.logger import logger

MODEL_ID = "facebook/nllb-200-distilled-600M"
CHUNK_LIMIT = 400

TranslateBatch = Callable[[list[str]], list[str]]


class UnsupportedLanguage(ValueError):
    """El idioma pedido no está en la lista expuesta por la API."""


class TranslationModelUnavailable(RuntimeError):
    """Los pesos de NLLB no están en la caché local."""


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    flores: str


LANGUAGES: tuple[Language, ...] = (
    Language("es", "Español", "spa_Latn"),
    Language("en", "Inglés", "eng_Latn"),
    Language("fr", "Francés", "fra_Latn"),
    Language("de", "Alemán", "deu_Latn"),
    Language("it", "Italiano", "ita_Latn"),
    Language("pt", "Portugués", "por_Latn"),
    Language("ru", "Ruso", "rus_Cyrl"),
    Language("zh", "Chino", "zho_Hans"),
    Language("ja", "Japonés", "jpn_Jpan"),
    Language("ko", "Coreano", "kor_Hang"),
    Language("ar", "Árabe", "arb_Arab"),
    Language("hi", "Hindi", "hin_Deva"),
    Language("nl", "Neerlandés", "nld_Latn"),
    Language("pl", "Polaco", "pol_Latn"),
    Language("tr", "Turco", "tur_Latn"),
    Language("vi", "Vietnamita", "vie_Latn"),
    Language("id", "Indonesio", "ind_Latn"),
    Language("uk", "Ucraniano", "ukr_Cyrl"),
    Language("sv", "Sueco", "swe_Latn"),
    Language("th", "Tailandés", "tha_Thai"),
)

LANGUAGES_BY_CODE = {lang.code: lang for lang in LANGUAGES}

SegmentKind = Literal["keep", "translate"]


@dataclass(frozen=True)
class Segment:
    kind: SegmentKind
    text: str


# Orden: bloques largos antes que las piezas que contienen.
_PROTECTED = re.compile(
    r"```[\s\S]*?```"
    r"|\$\$[\s\S]*?\$\$"
    r"|<figure\b[^>]*>[\s\S]*?</figure>"
    r"|<div\b[^>]*>\s*(?:<img\b[^>]*/?>\s*)+</div>"
    r"|<img\b[^>]*/?>"
    r"|!\[[^\]]*\]\([^)\n]*\)"
    r"|`[^`\n]+`"
    r"|\$(?!\$)(?:\\.|[^$\n])+?\$",
    re.IGNORECASE,
)

_BLANK = re.compile(r"\n[ \t]*\n")
_PREFIX = re.compile(
    r"^(?P<prefix>#{1,6}[ \t]+|\s*[-*+][ \t]+|\s*\d+[.)][ \t]+|\s*>[ \t]+)"
)
_RULE = re.compile(r"(?:\s*[-*_]){3,}\s*")
_SENTENCE = re.compile(r".+?(?:[.!?。！？](?=\s)|$)", re.DOTALL)

_model = None
_tokenizer = None
_device = "cpu"
_infer_lock = threading.Lock()


def list_languages() -> list[dict[str, str]]:
    return [{"code": lang.code, "name": lang.name} for lang in LANGUAGES]


def model_cache_ready(cache_dir: str | None = None) -> bool:
    root = Path(cache_dir or settings.TRANSLATE_CACHE_DIR)
    repo = root / "models--facebook--nllb-200-distilled-600M"
    return any(repo.glob("snapshots/*/config.json"))


def split_markdown(text: str) -> list[Segment]:
    """Parte el Markdown en fragmentos que se conservan o se traducen."""
    if text == "":
        return []

    segments: list[Segment] = []
    cursor = 0
    for match in _PROTECTED.finditer(text):
        if match.start() > cursor:
            segments.extend(_split_prose(text[cursor:match.start()]))
        segments.append(Segment("keep", match.group(0)))
        cursor = match.end()
    if cursor < len(text):
        segments.extend(_split_prose(text[cursor:]))
    return segments


def split_for_model(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Trocea un párrafo largo sin perder caracteres."""
    if len(text) <= limit:
        return [text]

    sentences = _SENTENCE.findall(text)
    if not sentences or "".join(sentences) != text:
        return _hard_slices(text, limit)

    chunks: list[str] = []
    buf = ""
    for sentence in sentences:
        if buf and len(buf) + len(sentence) > limit:
            chunks.extend(_flush_long(buf, limit))
            buf = sentence
        else:
            buf += sentence
    if buf:
        chunks.extend(_flush_long(buf, limit))
    return chunks


def apply_translations(
    text: str,
    translate_batch: TranslateBatch,
    *,
    chunk_limit: int = CHUNK_LIMIT,
) -> str:
    """Traduce solo los fragmentos de texto y rearma el Markdown original."""
    segments = split_markdown(text)
    flat: list[str] = []
    owners: list[tuple[int, int]] = []
    for index, segment in enumerate(segments):
        if segment.kind != "translate" or not segment.text.strip():
            continue
        chunks = split_for_model(segment.text, chunk_limit)
        owners.append((index, len(chunks)))
        flat.extend(chunks)

    if not flat:
        return text

    translated = translate_batch(flat)
    if len(translated) != len(flat):
        raise RuntimeError("El traductor devolvió un número distinto de fragmentos")

    cursor = 0
    replaced: dict[int, str] = {}
    for index, count in owners:
        replaced[index] = "".join(translated[cursor : cursor + count])
        cursor += count

    return "".join(replaced.get(index, segment.text) for index, segment in enumerate(segments))


def translate_markdown(text: str, source_lang: str, target_lang: str) -> str:
    source = _require_lang(source_lang)
    target = _require_lang(target_lang)
    if source == target or not text.strip():
        return text

    with _infer_lock:
        def _batch(texts: list[str]) -> list[str]:
            return _translate_texts(texts, source, target)

        return apply_translations(text, _batch)


def _require_lang(code: str) -> str:
    normalized = (code or "").strip().lower()
    if normalized not in LANGUAGES_BY_CODE:
        raise UnsupportedLanguage("Elige un idioma de origen y destino válidos")
    return normalized


def _split_prose(text: str) -> list[Segment]:
    if text == "":
        return []
    segments: list[Segment] = []
    for part in re.split(r"(\n[ \t]*\n)", text):
        if part == "":
            continue
        if _BLANK.fullmatch(part) or not part.strip():
            segments.append(Segment("keep", part))
            continue
        segments.extend(_peel(part))
    return segments


def _peel(part: str) -> list[Segment]:
    match = re.match(r"^(\s*)(.*?)(\s*)$", part, re.DOTALL)
    if match is None:
        return [Segment("translate", part)]
    lead, body, trail = match.group(1), match.group(2), match.group(3)
    segments: list[Segment] = []
    if lead:
        segments.append(Segment("keep", lead))
    if body:
        segments.extend(_classify_body(body))
    if trail:
        segments.append(Segment("keep", trail))
    return segments


def _classify_body(body: str) -> list[Segment]:
    if _RULE.fullmatch(body):
        return [Segment("keep", body)]

    lines = body.split("\n")
    nonempty = [line for line in lines if line.strip()]
    if nonempty and all(_PREFIX.match(line) for line in nonempty):
        segments: list[Segment] = []
        for index, line in enumerate(lines):
            prefix_match = _PREFIX.match(line)
            content = line[prefix_match.end() :] if prefix_match else line
            if prefix_match and content.strip():
                segments.append(Segment("keep", prefix_match.group("prefix")))
                segments.append(Segment("translate", content))
            else:
                segments.append(Segment("keep", line))
            if index < len(lines) - 1:
                segments.append(Segment("keep", "\n"))
        return segments

    return [Segment("translate", body)]


def _flush_long(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    return _hard_slices(text, limit)


def _hard_slices(text: str, limit: int) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _translate_texts(texts: list[str], source: str, target: str) -> list[str]:
    model, tokenizer, device = _load_model()
    flores_src = LANGUAGES_BY_CODE[source].flores
    flores_tgt = LANGUAGES_BY_CODE[target].flores
    tokenizer.src_lang = flores_src
    bos_id = tokenizer.convert_tokens_to_ids(flores_tgt)
    unk_id = getattr(tokenizer, "unk_token_id", None)
    if bos_id is None or bos_id == unk_id:
        raise UnsupportedLanguage("El modelo no reconoce el idioma de destino")

    import torch

    batch_size = max(1, int(settings.TRANSLATE_BATCH_SIZE))
    max_length = int(settings.TRANSLATE_MAX_LENGTH)
    outputs: list[str] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        encoded = tokenizer(
            chunk,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                forced_bos_token_id=bos_id,
                max_length=max_length,
            )
        outputs.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
    return outputs


def _load_model():
    global _model, _tokenizer, _device
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer, _device

    cache = str(Path(settings.TRANSLATE_CACHE_DIR))
    if not model_cache_ready(cache):
        raise TranslationModelUnavailable(
            "El modelo de traducción no está instalado. "
            f"Se esperaba {MODEL_ID} en {cache}."
        )

    os.environ["HF_HUB_CACHE"] = cache
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    logger.info("Cargando %s desde %s", MODEL_ID, cache)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID,
        cache_dir=cache,
        local_files_only=True,
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_ID,
        cache_dir=cache,
        local_files_only=True,
    )
    device = _resolve_device(torch)
    model.to(device)
    model.eval()
    _model = model
    _tokenizer = tokenizer
    _device = device
    logger.info("Modelo de traducción listo en %s", device)
    return _model, _tokenizer, _device


def _resolve_device(torch_module) -> str:
    requested = (settings.TRANSLATE_DEVICE or "cpu").strip().lower()
    if requested.startswith("cuda"):
        if torch_module.cuda.is_available():
            return "cuda" if requested == "cuda" else requested
        logger.warning(
            "TRANSLATE_DEVICE=%s pero CUDA no está disponible; se usa CPU",
            requested,
        )
    return "cpu"

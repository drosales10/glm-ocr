"""
Paso de fusión de resultados
"""

from typing import Dict, Any, List, Optional, Callable, Tuple
from pathlib import Path
import json
import os
import re
from difflib import SequenceMatcher

from app.core.flows.base import ProcessingContext
from app.utils.logger import logger


class MergeResultsStepInput:
    ocr_result_path: str

    def __init__(self, ocr_result_path: str) -> None:
        self.ocr_result_path = ocr_result_path


_EMPTY_FENCE_RE = re.compile(
    r"```(?:markdown|md|text)?\s*\n\s*```",
    re.IGNORECASE,
)
_FENCED_BLOCK_RE = re.compile(
    r"```(?:markdown|md|text)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_FENCE_LINE_RE = re.compile(r"^\s*```(?:markdown|md|text)?\s*$", re.IGNORECASE)
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _plain_heading(text: str) -> str:
    return _norm_text(text).lstrip("# ").strip()


def _is_near_duplicate(a: str, b: str, threshold: float = 0.92) -> bool:
    """True si a y b son el mismo párrafo (o uno truncado / con typo leve)."""
    na, nb = _norm_text(a), _norm_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    pa, pb = _plain_heading(a), _plain_heading(b)
    if pa and pa == pb:
        return True

    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 40 and longer.startswith(shorter):
        return True
    if len(shorter) >= 40 and shorter in longer and len(shorter) / len(longer) >= 0.85:
        return True

    if min(len(na), len(nb)) < 24:
        return False
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def _prefer_paragraph(a: str, b: str) -> str:
    """Entre dos casi-iguales, conserva el más completo; si son typos, el primero."""
    a_s, b_s = (a or "").strip(), (b or "").strip()
    na, nb = _norm_text(a_s), _norm_text(b_s)
    # Uno truncado del otro → quedarse con el largo
    if len(nb) > len(na) * 1.15 and len(na) >= 40 and nb.startswith(na):
        return b_s
    if len(na) > len(nb) * 1.15 and len(nb) >= 40 and na.startswith(nb):
        return a_s
    # Typos / repetición casi igual → conservar el primero
    return a_s


def _unwrap_fences(text: str) -> str:
    """Quita fences ```…``` del OCR; el contenido interno suele ser repetición."""
    if not text:
        return ""

    cleaned = _EMPTY_FENCE_RE.sub("\n", text)

    def _replace_fence(match: re.Match) -> str:
        inner = (match.group(1) or "").strip()
        if not inner:
            return "\n"
        # Conservar interior solo temporalmente; la deduplicación lo limpia
        return "\n\n" + inner + "\n\n"

    cleaned = _FENCED_BLOCK_RE.sub(_replace_fence, cleaned)
    lines = [
        ln
        for ln in cleaned.replace("\r\n", "\n").split("\n")
        if not _FENCE_LINE_RE.match(ln)
    ]
    return "\n".join(lines)


def _collapse_exact_repeats(text: str, min_unit_len: int = 24, min_repeats: int = 2) -> str:
    """Si todo el texto es unit*N (N>=2), deja una sola copia."""
    s = text.strip()
    n = len(s)
    if n < min_unit_len * min_repeats:
        return text

    max_unit = n // min_repeats
    # Preferir unidades más largas (párrafo completo)
    for unit_len in range(max_unit, min_unit_len - 1, -1):
        if n % unit_len != 0:
            continue
        unit = s[:unit_len]
        repeats = n // unit_len
        if repeats >= min_repeats and unit * repeats == s:
            return unit.strip()

    # Repetición adyacente aunque sobren espacios al final
    pattern = re.compile(
        r"(.{" + str(min_unit_len) + r"," + str(max_unit) + r"}?)\1{"
        + str(min_repeats - 1)
        + r",}",
        re.DOTALL,
    )
    match = pattern.search(s)
    if match and match.start() == 0:
        return match.group(1).strip()
    return text


def _dedupe_paragraphs(text: str) -> str:
    """Elimina párrafos consecutivos duplicados / casi duplicados."""
    parts = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    kept: List[str] = []
    for part in parts:
        chunk = part.strip()
        if not chunk:
            continue
        # También deduplicar líneas idénticas dentro del párrafo
        lines = [ln.rstrip() for ln in chunk.split("\n")]
        line_kept: List[str] = []
        prev_line: Optional[str] = None
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                if line_kept and line_kept[-1] != "":
                    line_kept.append("")
                continue
            norm = _norm_text(stripped)
            plain = _plain_heading(stripped)
            prev_plain = _plain_heading(prev_line or "")
            if prev_line is not None and (
                norm == _norm_text(prev_line) or (plain and plain == prev_plain)
            ):
                continue
            line_kept.append(ln)
            prev_line = stripped
        chunk = "\n".join(line_kept).strip()
        if not chunk:
            continue

        if kept and _is_near_duplicate(kept[-1], chunk):
            kept[-1] = _prefer_paragraph(kept[-1], chunk)
            continue
        kept.append(chunk)

    return "\n\n".join(kept)


def _collapse_repeated_paragraph_run(text: str) -> str:
    """
    Detecta secuencias de párrafos que se repiten enteras, p.ej.:
    [A,B,C, A,B,C, A,B,C] → [A,B,C]
    """
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    n = len(paras)
    if n < 2:
        return text

    for unit in range(1, n // 2 + 1):
        if n % unit != 0:
            continue
        repeats = n // unit
        if repeats < 2:
            continue
        ok = True
        for r in range(1, repeats):
            for i in range(unit):
                if not _is_near_duplicate(paras[i], paras[r * unit + i]):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return "\n\n".join(paras[:unit])

    # Prefijo repetido aunque no divida exacto (p.ej. 3 párrafos x2 + ruido)
    for unit in range(1, n // 2 + 1):
        if n < unit * 2:
            continue
        if all(_is_near_duplicate(paras[i], paras[unit + i]) for i in range(unit)):
            # Cuántas veces se repite el bloque
            times = 1
            while (times + 1) * unit <= n and all(
                _is_near_duplicate(paras[i], paras[times * unit + i]) for i in range(unit)
            ):
                times += 1
            if times >= 2:
                rest = paras[times * unit :]
                # Si el resto es casi-duplicado truncado del inicio, descartarlo
                rest = [
                    p
                    for p in rest
                    if not any(_is_near_duplicate(p, paras[i]) for i in range(unit))
                ]
                return "\n\n".join(paras[:unit] + rest)

    return text


def clean_ocr_text(text: str) -> str:
    """Quita fences y párrafos/bloques duplicados que inventa el modelo local."""
    if not text:
        return ""

    cleaned = _unwrap_fences(text)
    cleaned = _collapse_exact_repeats(cleaned)
    cleaned = _dedupe_paragraphs(cleaned)
    cleaned = _collapse_repeated_paragraph_run(cleaned)
    cleaned = _collapse_exact_repeats(_norm_join_for_collapse(cleaned))
    # Reaplicar dedupe de párrafos por si el collapse dejó residuos
    cleaned = _dedupe_paragraphs(cleaned)
    cleaned = _MULTI_BLANK_RE.sub("\n\n", cleaned).strip()
    return cleaned


def _norm_join_for_collapse(text: str) -> str:
    """Normaliza saltos para detectar unit*N con espacios inconsistentes."""
    # Conservar párrafos; solo colapsar blanks extremos
    return _MULTI_BLANK_RE.sub("\n\n", text.strip())


def _blocks_near_duplicate(a: str, b: str) -> bool:
    return _is_near_duplicate(a, b)


async def merge_results(
    context: ProcessingContext,
    input: MergeResultsStepInput,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Fusiona los resultados OCR

    Args:
        context: Contexto de procesamiento
        input: MergeResultsStepInput，incluye ocr_result_path
        progress_callback: Función de callback de progreso

    Returns:
        Dict[str, Any]: Resultado fusionado
    """
    task_id = context.task_id
    output_format = context.output_format
    output_dir = context.get_output_dir()
    result_path = input.ocr_result_path
    logger.info(f"[{task_id}] Starting result merge")

    try:
        if progress_callback:
            await progress_callback(0.0, "Initializing merge")

        ocr_results = {}
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                result_data = json.load(f)
                ocr_results.update(result_data)
        except Exception as e:
            logger.error(
                f"[{task_id}] Failed to read OCR result from {result_path}: {e}"
            )

        md_output_path, json_output_path = await _merge_to_markdown(
            context, ocr_results, output_dir, progress_callback
        )

        if progress_callback:
            await progress_callback(100.0, "Merge completed")

        result = {
            "md_output_path": md_output_path,
            "json_output_path": json_output_path,
            "output_files": [md_output_path, json_output_path],
            "metadata": {
                "format": output_format,
                "total_pages": len(ocr_results.get("pages", [])),
            },
        }

        logger.info(
            f"[{task_id}] Result merge completed: md_output_path:{md_output_path},json_output_path:{json_output_path}"
        )

        return result

    except Exception as e:
        logger.error(f"[{task_id}] Result merge failed: {e}")
        raise


async def _merge_to_markdown(
    context: ProcessingContext,
    ocr_results: Dict[str, Any],
    output_dir: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Tuple[str, str]:
    """Fusiona en formato Markdown"""
    pages = ocr_results.get("pages", [])

    result: Dict[str, Any] = {}
    result["metadata"] = context.metadata
    merge_res_layout = []
    total_pages = len(pages)
    page_idx = 0

    for page_idx, page in enumerate(pages):
        layout = page.get("layout", {}).get("blocks", [])
        for block in layout:
            text = block.get("content", "") or ""
            layout_type = block.get("layout_type", "")
            if layout_type == "image":
                img_name = block.get("image_path")
                if img_name and not os.path.isabs(img_name):
                    img_name = os.path.abspath(img_name)
                text = (
                    f'<div style="text-align: center;">'
                    f'<img src="/api/v1/tasks/file?path={img_name}" alt="Image"/></div>\n'
                )
            else:
                text = clean_ocr_text(text)
                if not text:
                    continue

            merge_res_layout.append(
                {
                    "block_content": text,
                    "bbox": block.get("layout_box"),
                    "block_id": block.get("index"),
                    "page_index": block.get("page_index"),
                }
            )

    if progress_callback:
        await progress_callback(100.0, f"Merging page {page_idx + 1}/{total_pages}")

    # Deduplicar bloques enteros idénticos / casi idénticos consecutivos
    compact_layout = []
    compact_md = []
    prev_text: Optional[str] = None
    for item in merge_res_layout:
        content = (item.get("block_content") or "").strip()
        if prev_text is not None and _blocks_near_duplicate(prev_text, content):
            # Sustituir por la versión más completa
            better = _prefer_paragraph(prev_text, content)
            if compact_layout and better != compact_layout[-1]["block_content"]:
                compact_layout[-1] = {**item, "block_content": better}
                compact_md[-1] = better
            prev_text = better
            continue
        compact_layout.append(item)
        compact_md.append(content)
        prev_text = content

    result["full_markdown"] = "\n\n".join(compact_md).strip() + ("\n" if compact_md else "")
    result["layout"] = compact_layout

    md_output_path = str(Path(output_dir) / "result.md")
    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write(result["full_markdown"])
    json_output_path = str(Path(output_dir) / "merged.json")
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return md_output_path, json_output_path

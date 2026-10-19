"""Per-request OCR quality/speed profiles.

Applied to PageLoader at request time so the UI can choose without restarting
the server. Layout model weights stay loaded; only generation/image params change.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

# Canonical profile ids used by UI / backend / server
PROFILE_BALANCED = "balanced"
PROFILE_FAST = "fast"
PROFILE_MATH = "math"
DEFAULT_PROFILE = PROFILE_BALANCED

OCR_PROFILES: Dict[str, Dict[str, Any]] = {
    PROFILE_FAST: {
        "label": "Rapido",
        "description": "Paginas normales; menor calidad en formulas densas.",
        "max_tokens": 1024,
        "image_format": "JPEG",
        "pdf_dpi": 150,
    },
    PROFILE_BALANCED: {
        "label": "Equilibrado",
        "description": "Buen equilibrio velocidad/calidad (recomendado).",
        "max_tokens": 2048,
        "image_format": "JPEG",
        "pdf_dpi": 200,
    },
    PROFILE_MATH: {
        "label": "Math",
        "description": "Papers con integrales/formulas; mas lento.",
        "max_tokens": 4096,
        "image_format": "PNG",
        "pdf_dpi": 300,
    },
}

_PAGE_LOADER_KEYS = ("max_tokens", "image_format", "pdf_dpi")


def normalize_profile(profile: Optional[str]) -> str:
    if not profile:
        return DEFAULT_PROFILE
    key = str(profile).strip().lower()
    if key in OCR_PROFILES:
        return key
    aliases = {
        "rapido": PROFILE_FAST,
        "rápido": PROFILE_FAST,
        "quick": PROFILE_FAST,
        "speed": PROFILE_FAST,
        "default": PROFILE_BALANCED,
        "normal": PROFILE_BALANCED,
        "quality": PROFILE_MATH,
        "formula": PROFILE_MATH,
        "formulas": PROFILE_MATH,
    }
    return aliases.get(key, DEFAULT_PROFILE)


def list_profiles() -> list[dict]:
    return [
        {"id": pid, "label": meta["label"], "description": meta["description"]}
        for pid, meta in OCR_PROFILES.items()
    ]


@contextmanager
def apply_profile(page_loader: Any, profile: Optional[str]) -> Iterator[str]:
    """Temporarily override PageLoader knobs for one parse request."""
    profile_id = normalize_profile(profile)
    overrides = {
        k: OCR_PROFILES[profile_id][k]
        for k in _PAGE_LOADER_KEYS
        if k in OCR_PROFILES[profile_id]
    }
    previous = {k: getattr(page_loader, k) for k in overrides}
    try:
        for key, value in overrides.items():
            setattr(page_loader, key, value)
        yield profile_id
    finally:
        for key, value in previous.items():
            setattr(page_loader, key, value)

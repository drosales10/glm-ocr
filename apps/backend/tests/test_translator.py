"""Troceado del Markdown y contrato de la API de traducción."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.translate import router
from app.core.translator import (
    TranslationModelUnavailable,
    UnsupportedLanguage,
    apply_translations,
    split_for_model,
    split_markdown,
    translate_markdown,
)

SAMPLE = """# Annual summit

Forging the future.

<div style="text-align: center;"><img src="https://example.com/a.png" alt="Image" width="3%" /></div>

```python
print("keep")
```

$$
E = mc^2
$$

Use `code` and $x+1$ inline.

- First item
- Second item
"""


def _join(text: str) -> str:
    return "".join(segment.text for segment in split_markdown(text))


def test_split_roundtrip_keeps_every_character():
    assert _join(SAMPLE) == SAMPLE


def test_protected_blocks_are_not_translated():
    protected = [
        '<div style="text-align: center;"><img src="https://example.com/a.png" alt="Image" width="3%" /></div>',
        '```python\nprint("keep")\n```',
        "$$\nE = mc^2\n$$",
        "`code`",
        "$x+1$",
    ]

    def fake(texts: list[str]) -> list[str]:
        return [f"«{item}»" for item in texts]

    translated = apply_translations(SAMPLE, fake)
    for block in protected:
        assert block in translated
        assert f"«{block}»" not in translated

    assert "«Annual summit»" in translated
    assert "«Forging the future.»" in translated
    assert "«First item»" in translated
    assert "«Second item»" in translated
    assert "«Use» `code` «and» $x+1$ «inline.»" in translated
    assert translated.startswith("# «Annual summit»")


def test_same_language_returns_original_without_model():
    assert translate_markdown(SAMPLE, "en", "en") == SAMPLE
    assert translate_markdown("   ", "es", "en") == "   "


def test_unknown_language_is_rejected():
    try:
        translate_markdown("hola", "en", "xx")
    except UnsupportedLanguage:
        return
    raise AssertionError("se esperaba UnsupportedLanguage")


def test_long_text_chunks_rejoin():
    text = ("Sentence number one. " * 40).strip()
    chunks = split_for_model(text, limit=80)
    assert len(chunks) > 1
    assert "".join(chunks) == text
    assert all(len(chunk) <= 80 or " " not in chunk for chunk in chunks)


def test_translate_endpoint_uses_batch_without_loading_model(monkeypatch):
    monkeypatch.setattr(
        "app.api.translate.translate_markdown",
        lambda text, source, target: f"{source}->{target}:{text}",
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    languages = client.get("/api/v1/translate/languages")
    assert languages.status_code == 200
    codes = [item["code"] for item in languages.json()["data"]]
    assert codes[0] == "es"
    assert "en" in codes

    response = client.post(
        "/api/v1/translate",
        json={"text": "Hello", "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["translated"] == "en->es:Hello"
    assert body["data"]["source_lang"] == "en"
    assert body["data"]["target_lang"] == "es"


def test_translate_endpoint_reports_missing_model(monkeypatch):
    def _missing(text, source, target):
        raise TranslationModelUnavailable("modelo ausente")

    monkeypatch.setattr("app.api.translate.translate_markdown", _missing)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post(
        "/api/v1/translate",
        json={"text": "Hello", "source_lang": "en", "target_lang": "es"},
    )
    assert response.status_code == 503
    assert "modelo ausente" in response.json()["detail"]

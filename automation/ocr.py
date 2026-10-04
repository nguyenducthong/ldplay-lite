from __future__ import annotations

from pathlib import Path


def read_text(image_path: str | Path, *, language: str = "eng") -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Cài tùy chọn automation: pip install -r requirements-automation.txt") from exc
    with Image.open(image_path) as image:
        return pytesseract.image_to_string(image, lang=language).strip()

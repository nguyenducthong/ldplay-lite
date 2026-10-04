from __future__ import annotations

from pathlib import Path


def find_image(image_path: str | Path, template_path: str | Path, threshold: float = 0.85):
    """Return the template center and confidence, or None when no match is found."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Cài tùy chọn automation: pip install -r requirements-automation.txt") from exc
    image = cv2.imread(str(image_path))
    template = cv2.imread(str(template_path))
    if image is None or template is None:
        raise ValueError("Không thể đọc ảnh nguồn hoặc ảnh mẫu.")
    result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, location = cv2.minMaxLoc(result)
    if confidence < threshold:
        return None
    height, width = template.shape[:2]
    return location[0] + width // 2, location[1] + height // 2, float(confidence)

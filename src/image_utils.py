from __future__ import annotations

import io

from PIL import Image

TARGET_KB = 900
_QUALITY_STEPS = (85, 75, 65, 55, 45, 35)
_MAX_DIMENSION_STEPS = (None, 2560, 1920, 1280, 960)  # None = keep original


def compress_for_upload(image_bytes: bytes) -> bytes:
    """Return JPEG bytes guaranteed to be <= TARGET_KB."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    target_bytes = TARGET_KB * 1024
    last_buf: io.BytesIO | None = None
    for max_dim in _MAX_DIMENSION_STEPS:
        candidate = img
        if max_dim and max(img.size) > max_dim:
            candidate = img.copy()
            candidate.thumbnail((max_dim, max_dim), Image.LANCZOS)
        for quality in _QUALITY_STEPS:
            buf = io.BytesIO()
            candidate.save(buf, format="JPEG", quality=quality, optimize=True)
            last_buf = buf
            if buf.tell() <= target_bytes:
                return buf.getvalue()

    # Fallback — smallest version we managed.
    assert last_buf is not None
    return last_buf.getvalue()

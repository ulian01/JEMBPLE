"""Shared image helpers used by the vision-model call sites (scene / OCR / VQA)."""
from __future__ import annotations

import base64

import cv2


def encode_jpeg(frame_bgr, max_edge: int, quality: int = 85) -> str:
    """Downscale ``frame_bgr`` so its long edge is <= ``max_edge`` and return it
    as a base64-encoded JPEG string. ``quality`` is the JPEG quality (0-100)."""
    h, w = frame_bgr.shape[:2]
    scale = min(1.0, max_edge / max(h, w))
    if scale < 1.0:
        frame_bgr = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to JPEG-encode frame")
    return base64.standard_b64encode(buf.tobytes()).decode()

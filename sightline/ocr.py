"""Text reading (OCR) with selectable backends, best-first.

Tesseract is fast and offline but weak on real-world photos (signs, labels,
curved/angled text, uneven light). For a blind-assist reader accuracy matters
far more than a few hundred ms, so by default we use the most accurate backend
available:

* **claude**  — a vision model reads the text. By far the most accurate on
  natural scenes; needs network + ANTHROPIC_API_KEY. (Same off-device tradeoff
  as the scene describer.)
* **easyocr** — strong offline deep-learning OCR; no API needed, heavier install.
* **tesseract** — fast, light, fully offline fallback, with upscaling + denoise +
  Otsu + multi-PSM passes so it's as good as Tesseract gets.

``backend: auto`` picks claude → easyocr → tesseract by what's installed/keyed.
"""
from __future__ import annotations

import os
import re

import cv2
import numpy as np

from .imaging import encode_jpeg

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import anthropic
except Exception:
    anthropic = None

# tesseract lang code -> easyocr code
_EASYOCR_LANG = {"eng": "en", "deu": "de", "nld": "nl", "fra": "fr", "spa": "es"}

_OCR_SYSTEM = (
    "You are a precise OCR engine for a blind user's reading aid. Transcribe ALL "
    "legible text in the image exactly as written, preserving reading order and "
    "line breaks. Output only the transcribed text — no commentary, no quotes, no "
    "markdown. If there is no legible text, output exactly: NO_TEXT"
)


def _clean(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if len(ln) >= 1]
    return "\n".join(lines).strip()


def _alnum(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "")


class OcrReader:
    def __init__(self, ocr_cfg: dict):
        self.cfg = ocr_cfg
        self.lang = ocr_cfg.get("lang", "eng")
        self.model = ocr_cfg.get("model", "claude-opus-4-8")
        self._easyreader = None
        self._client = None
        self.backend = self._select(ocr_cfg.get("backend", "auto"))

    # -- backend selection -----------------------------------------------
    def _select(self, requested: str) -> str:
        have_claude = anthropic is not None and bool(os.environ.get("ANTHROPIC_API_KEY"))
        have_easy = self._easyocr_available()
        have_tess = pytesseract is not None
        if requested != "auto":
            return requested
        if have_claude:
            return "claude"
        if have_easy:
            return "easyocr"
        if have_tess:
            return "tesseract"
        return "tesseract"  # will surface a helpful error on first read

    @staticmethod
    def _easyocr_available() -> bool:
        try:
            import easyocr  # noqa: F401
            return True
        except Exception:
            return False

    # -- public API -------------------------------------------------------
    def read(self, frame_bgr: np.ndarray) -> str:
        if self.backend == "claude":
            return self._read_claude(frame_bgr)
        if self.backend == "easyocr":
            return self._read_easyocr(frame_bgr)
        return self._read_tesseract(frame_bgr)

    # -- claude (vision) --------------------------------------------------
    def _read_claude(self, frame_bgr: np.ndarray) -> str:
        if anthropic is None:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic")
        if self._client is None:
            self._client = anthropic.Anthropic()
        # upload at decent resolution so small text stays legible
        img_b64 = encode_jpeg(frame_bgr, max_edge=1600, quality=90)
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            thinking={"type": "disabled"},
            system=_OCR_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": "Transcribe the text in this image."},
                ],
            }],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if text.strip() == "NO_TEXT":
            return ""
        return _clean(text)

    # -- easyocr ----------------------------------------------------------
    def _read_easyocr(self, frame_bgr: np.ndarray) -> str:
        if self._easyreader is None:
            import easyocr
            code = _EASYOCR_LANG.get(self.lang, "en")
            self._easyreader = easyocr.Reader([code], gpu=False)
        results = self._easyreader.readtext(frame_bgr)
        lines = [txt for (_box, txt, conf) in results if conf >= 0.3]
        return _clean("\n".join(lines))

    # -- tesseract (improved) --------------------------------------------
    def _read_tesseract(self, frame_bgr: np.ndarray) -> str:
        if pytesseract is None:
            raise RuntimeError(
                "No OCR backend available. Install one of:\n"
                "  pip install anthropic        # best, set ANTHROPIC_API_KEY\n"
                "  pip install easyocr          # offline deep-learning OCR\n"
                "  sudo apt install tesseract-ocr && pip install pytesseract"
            )
        img = _prep_for_tesseract(frame_bgr)
        best = ""
        # try several page-segmentation modes; keep the richest result
        for psm in (6, 11, 3, 4):
            try:
                txt = pytesseract.image_to_string(
                    img, lang=self.lang, config=f"--oem 1 --psm {psm}")
            except Exception:
                continue
            if len(_alnum(txt)) > len(_alnum(best)):
                best = txt
        return _clean(best)


def _prep_for_tesseract(frame_bgr: np.ndarray) -> np.ndarray:
    """Upscale + denoise + binarise — Tesseract wants big, clean, high-contrast text."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    # Tesseract likes ~300 DPI; webcam text is tiny, so upscale small frames.
    scale = max(1.0, 1100.0 / max(h, w))
    if scale > 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 5, 60, 60)          # denoise, keep edges
    # Otsu global threshold works well on signs/labels; fall back handled by PSM sweep
    _t, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # ensure dark text on light background (Tesseract's expectation)
    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)
    return binary

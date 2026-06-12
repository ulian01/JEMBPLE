#!/usr/bin/env python3
"""Quick OCR check on a single image — verify accuracy without the camera loop.

    export ANTHROPIC_API_KEY=sk-ant-...        # for the claude backend
    python tools/ocr_test.py /path/to/photo.jpg
    python tools/ocr_test.py /path/to/photo.jpg --backend tesseract

Defaults to the snapshot saved by tools/camera_check.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sightline import config
from sightline.ocr import OcrReader


def main() -> None:
    args = [a for a in sys.argv[1:]]
    backend = None
    if "--backend" in args:
        i = args.index("--backend")
        backend = args[i + 1]
        del args[i:i + 2]
    img_path = args[0] if args else "/tmp/camera_check_0.jpg"

    frame = cv2.imread(img_path)
    if frame is None:
        print(f"Could not read image: {img_path}")
        return

    cfg = config.load()["ocr"]
    if backend:
        cfg = {**cfg, "backend": backend}
    reader = OcrReader(cfg)
    print(f"image: {img_path}  ({frame.shape[1]}x{frame.shape[0]})")
    print(f"backend: {reader.backend}\n--- text ---")
    print(reader.read(frame) or "(no text detected)")


if __name__ == "__main__":
    main()

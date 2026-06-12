#!/usr/bin/env python3
"""Camera sanity check — find a source that returns a real (non-black) image.

Probes webcam indices (or a source you pass), applies the same MJPG + warm-up
the suite uses, reports average brightness, and saves a snapshot you can open to
confirm. Use it when a demo shows a black window.

    python tools/camera_check.py            # probe indices 0 and 1
    python tools/camera_check.py 2           # probe a specific index
    python tools/camera_check.py /path/clip.mp4
"""
from __future__ import annotations

import sys
import time

import cv2


def probe(source) -> None:
    val = int(source) if str(source).isdigit() else source
    cap = cv2.VideoCapture(val)
    if not cap.isOpened():
        print(f"source {source!r}: could NOT open (busy? wrong index?)")
        return
    if isinstance(val, int):
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    frame = None
    for _ in range(40):                      # warm up, keep the last frame
        ok, f = cap.read()
        if ok and f is not None:
            frame = f
        time.sleep(0.02)
    cap.release()
    if frame is None:
        print(f"source {source!r}: opened but read() returned nothing")
        return
    bright = float(frame.mean())
    verdict = "LIVE IMAGE ✅" if bright > 8 else "BLACK / no image ❌"
    out = f"/tmp/camera_check_{str(source).replace('/', '_')}.jpg"
    cv2.imwrite(out, frame)
    print(f"source {source!r}: {frame.shape[1]}x{frame.shape[0]} "
          f"brightness={bright:.1f} -> {verdict}   (saved {out})")
    if bright > 8 and isinstance(val, int):
        print(f"  ▶ use it:  camera.source: {val}   (in config.laptop.yaml)")


def main() -> None:
    sources = sys.argv[1:] or ["0", "1"]
    print("Probing camera source(s)… (close any running demo first)\n")
    for s in sources:
        probe(s)


if __name__ == "__main__":
    main()

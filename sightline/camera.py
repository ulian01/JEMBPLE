"""Camera abstraction.

Prefers Picamera2 (the native libcamera stack on Raspberry Pi OS) and falls
back to an OpenCV ``VideoCapture`` so the same code runs on a dev laptop with a
USB webcam. Frames are always returned as BGR ``numpy`` arrays, matching what
OpenCV / TFLite pre-processing expect.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from picamera2 import Picamera2
    from libcamera import Transform
    _HAVE_PICAMERA2 = True
except Exception:  # ImportError on non-Pi, or libcamera missing
    _HAVE_PICAMERA2 = False

import cv2

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _resolve_source(source, prefer_picamera: bool):
    """Return ('picamera'|'webcam'|'video'|'image', value).

    ``source`` may be "auto", "picamera", an int / numeric string (webcam index),
    or a path to a video or still image — so the suite runs off a laptop webcam
    or a recorded clip, not just the Pi Camera.
    """
    if source in (None, "auto"):
        return ("picamera", None) if prefer_picamera else ("webcam", 0)
    if source == "picamera":
        return ("picamera", None)
    if isinstance(source, int):
        return ("webcam", source)
    s = str(source)
    if s.isdigit():
        return ("webcam", int(s))
    p = Path(s)
    if p.suffix.lower() in _IMAGE_EXTS:
        return ("image", str(p))
    return ("video", s)


class Camera:
    """Unified camera that yields BGR frames.

    Usage::

        with Camera(cfg["camera"]) as cam:
            frame = cam.read()
    """

    def __init__(self, cam_cfg: dict):
        self.cfg = cam_cfg
        self.width = int(cam_cfg.get("width", 640))
        self.height = int(cam_cfg.get("height", 480))
        self._picam: Optional["Picamera2"] = None
        self._cv: Optional[cv2.VideoCapture] = None
        self._still: Optional[np.ndarray] = None
        self.kind, self.value = _resolve_source(cam_cfg.get("source", "auto"), _HAVE_PICAMERA2)
        self.backend = "picamera2" if self.kind == "picamera" else "opencv"

    def start(self) -> "Camera":
        if self.kind == "picamera":
            self._picam = Picamera2()
            transform = Transform(
                hflip=bool(self.cfg.get("hflip", False)),
                vflip=bool(self.cfg.get("vflip", False)),
            )
            config = self._picam.create_preview_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                transform=transform,
            )
            self._picam.configure(config)
            self._picam.start()
            time.sleep(0.5)  # let auto-exposure/white-balance settle
        elif self.kind == "image":
            img = cv2.imread(self.value)
            if img is None:
                raise RuntimeError(f"Could not read image source: {self.value}")
            self._still = img
        else:  # webcam | video
            self._cv = cv2.VideoCapture(self.value)
            if self.kind == "webcam":
                # Many UVC webcams (e.g. the Microdia integrated cam) return
                # all-black frames in the default YUYV mode — MJPG fixes it.
                self._cv.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                self._cv.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cv.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                # keep only the newest frame so read() never returns a stale one
                self._cv.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not self._cv.isOpened():
                raise RuntimeError(f"Could not open camera/video source: {self.value!r}")
            # Warm up: discard the first frames (black while exposure ramps).
            if self.kind in ("webcam", "video"):
                for _ in range(10):
                    self._cv.read()
                    time.sleep(0.03)
        return self

    def read(self) -> np.ndarray:
        """Grab one frame as a BGR uint8 array, applying configured rotation."""
        if self._picam is not None:
            rgb = self._picam.capture_array()        # RGB888
            frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif self._still is not None:
            frame = self._still.copy()               # same still on every read
        elif self._cv is not None:
            ok, frame = self._cv.read()
            if not ok and self.kind == "video":
                # loop the clip so demos keep running off a recorded file
                self._cv.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cv.read()
            if not ok:
                raise RuntimeError("Camera frame grab failed")
        else:
            raise RuntimeError("Camera not started; call start() or use as a context manager")

        rot = int(self.cfg.get("rotation", 0)) % 360
        if rot == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rot == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rot == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return frame

    def close(self) -> None:
        if self._picam is not None:
            self._picam.stop()
            self._picam.close()
            self._picam = None
        if self._cv is not None:
            self._cv.release()
            self._cv = None

    def __enter__(self) -> "Camera":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

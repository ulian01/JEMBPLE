"""Object detection backend.

Default backend is TensorFlow Lite running an SSD-MobileNet-V2 COCO model on the
Pi 5 CPU (a few FPS, plenty for a walking-pace assistant). The Hailo-8L path is
stubbed for users who add the Raspberry Pi AI Kit — it slots in behind the same
``Detector.detect()`` interface so no demo code changes.

``detect()`` returns a list of ``announcer.Detection`` with normalised boxes.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .announcer import Detection
from . import config

# tflite_runtime is the slim wheel for the Pi; fall back to full TF if present.
try:
    from tflite_runtime.interpreter import Interpreter
except Exception:
    try:
        from tensorflow.lite.python.interpreter import Interpreter
    except Exception:
        Interpreter = None


def load_labels(path: str | Path) -> list[str]:
    p = config.resolve_path(str(path))
    if not p.is_file():
        return []
    with open(p) as fh:
        return [line.strip() for line in fh if line.strip()]


class TFLiteDetector:
    def __init__(self, det_cfg: dict):
        if Interpreter is None:
            raise RuntimeError(
                "No TFLite runtime found. Install with: pip install tflite-runtime"
            )
        model_path = config.resolve_path(det_cfg["model"])
        if not model_path.is_file():
            raise FileNotFoundError(
                f"Model not found at {model_path}. See models/README.md for the download command."
            )
        self.threshold = float(det_cfg.get("threshold", 0.5))
        self.labels = load_labels(det_cfg.get("labels", ""))
        allow = det_cfg.get("announce_classes") or []
        self.allow = set(allow)

        self.interp = Interpreter(model_path=str(model_path))
        self.interp.allocate_tensors()
        self.inp = self.interp.get_input_details()[0]
        self.out = self.interp.get_output_details()
        _, self.in_h, self.in_w, _ = self.inp["shape"]
        self.is_float = self.inp["dtype"] == np.float32

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.in_w, self.in_h))
        data = np.expand_dims(resized, 0)
        if self.is_float:
            data = (np.float32(data) - 127.5) / 127.5
        else:
            data = data.astype(self.inp["dtype"])
        self.interp.set_tensor(self.inp["index"], data)
        self.interp.invoke()

        # Standard TFLite SSD output order: boxes, classes, scores, count.
        boxes = self.interp.get_tensor(self.out[0]["index"])[0]
        classes = self.interp.get_tensor(self.out[1]["index"])[0]
        scores = self.interp.get_tensor(self.out[2]["index"])[0]

        results: list[Detection] = []
        for box, cls, score in zip(boxes, classes, scores):
            if score < self.threshold:
                continue
            idx = int(cls)
            label = self.labels[idx] if idx < len(self.labels) else str(idx)
            if self.allow and label not in self.allow:
                continue
            y1, x1, y2, x2 = box  # SSD emits (ymin, xmin, ymax, xmax)
            results.append(
                Detection(
                    label=label,
                    confidence=float(score),
                    box=(float(x1), float(y1), float(x2), float(y2)),
                )
            )
        return results


class UltralyticsDetector:
    """YOLO backend — the easy path on an x86 laptop.

    ``ultralytics`` is pip-installable and auto-downloads its weights
    (``yolov8n.pt``) on first use, so there's no TFLite/model wrangling. Runs
    fine on a laptop CPU. Same ``detect()`` contract as the TFLite backend.
    """

    def __init__(self, det_cfg: dict):
        try:
            from ultralytics import YOLO
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "ultralytics not installed. Run: pip install ultralytics"
            ) from e
        self.threshold = float(det_cfg.get("threshold", 0.5))
        allow = det_cfg.get("announce_classes") or []
        self.allow = set(allow)
        # model weights download automatically the first time if not cached
        self.model = YOLO(det_cfg.get("ultralytics_model", "yolov8n.pt"))

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        res = self.model(frame_bgr, verbose=False, conf=self.threshold)[0]
        names = res.names
        out: list[Detection] = []
        for b in res.boxes:
            label = names[int(b.cls)]
            if self.allow and label not in self.allow:
                continue
            x1, y1, x2, y2 = b.xyxyn[0].tolist()  # already normalised 0..1
            out.append(
                Detection(label=label, confidence=float(b.conf),
                          box=(x1, y1, x2, y2))
            )
        return out


def _tflite_model_present(det_cfg: dict) -> bool:
    return Interpreter is not None and config.resolve_path(det_cfg["model"]).is_file()


def _ultralytics_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False


def build(det_cfg: dict):
    backend = det_cfg.get("backend", "auto")
    if backend == "auto":
        # Prefer the local TFLite model (Pi default); otherwise YOLO (laptop).
        if _tflite_model_present(det_cfg):
            backend = "tflite"
        elif _ultralytics_available():
            backend = "ultralytics"
        else:
            raise RuntimeError(
                "No object-detection backend available. Either download the TFLite "
                "model (see models/README.md) or `pip install ultralytics`."
            )
    if backend == "tflite":
        return TFLiteDetector(det_cfg)
    if backend == "ultralytics":
        return UltralyticsDetector(det_cfg)
    if backend == "hailo":
        raise NotImplementedError(
            "Hailo backend stub — install hailo-all and wire the HailoRT pipeline here, "
            "returning announcer.Detection objects with the same interface as TFLiteDetector."
        )
    raise ValueError(f"Unknown object_detection.backend: {backend!r}")

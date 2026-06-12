"""Object detection backend.

Default backend is TensorFlow Lite running an SSD-MobileNet-V2 COCO model on the
Pi 5 CPU (a few FPS, plenty for a walking-pace assistant). The Hailo-8L path is
stubbed for users who add the Raspberry Pi AI Kit — it slots in behind the same
``Detector.detect()`` interface so no demo code changes.

``detect()`` returns a list of ``announcer.Detection`` with normalised boxes.
"""
from __future__ import annotations

import threading
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


def _norm_label(name) -> str:
    """Normalise a model's class name to lowercase words.

    Different vocabularies spell the same thing differently (COCO ``person``,
    Open Images ``Person``; ``potted_plant`` vs ``potted plant``). Normalising
    here means one obstacle list, one set of phrasing rules, and one
    ``announce_classes`` filter work across every backend and model.
    """
    return str(name).strip().lower().replace("_", " ")


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
        self.allow = {_norm_label(a) for a in allow}

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
            raw = self.labels[idx] if idx < len(self.labels) else str(idx)
            label = _norm_label(raw)
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
    """YOLO backend — the rich, easy path on an x86 laptop (also runs on a Pi).

    ``ultralytics`` is pip-installable and auto-downloads its weights on first
    use, so there's no TFLite/model wrangling. The model is selectable, which is
    how you trade the 80 COCO classes for a much larger vocabulary:

    * ``ultralytics_model: yolov8n.pt`` — the default, 80 COCO classes.
    * ``ultralytics_model: yolov8s-oiv7.pt`` — Open Images V7, ~600 classes
      (furniture, appliances, food, tools, animals, and much more).
    * ``open_vocab: [mug, backpack, ...]`` — open vocabulary via YOLO-World: it
      detects whatever class names you list, so you can add any object by name.

    ``imgsz`` sets the inference resolution: smaller is faster (e.g. 416 is
    roughly 2-3x faster than 640 on a CPU) at some cost to small-object recall.
    Same ``detect()`` contract as the TFLite backend.
    """

    def __init__(self, det_cfg: dict):
        try:
            from ultralytics import YOLO
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "ultralytics not installed. Run: pip install ultralytics"
            ) from e
        self.threshold = float(det_cfg.get("threshold", 0.5))
        self.imgsz = int(det_cfg.get("imgsz", 0)) or None   # 0 => model default
        allow = det_cfg.get("announce_classes") or []
        self.allow = {_norm_label(a) for a in allow}

        open_vocab = [str(c).strip() for c in (det_cfg.get("open_vocab") or [])
                      if str(c).strip()]
        if open_vocab:
            # Open vocabulary: load a YOLO-World model and tell it the exact set
            # of class names to look for. Needs the extra `clip` dependency,
            # which ultralytics installs on first use.
            from ultralytics import YOLOWorld
            self.model = YOLOWorld(det_cfg.get("world_model", "yolov8s-world.pt"))
            self.model.set_classes(open_vocab)
        else:
            # Fixed-vocabulary model; weights download automatically if not cached.
            self.model = YOLO(det_cfg.get("ultralytics_model", "yolov8n.pt"))

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        kwargs = {"verbose": False, "conf": self.threshold}
        if self.imgsz:
            kwargs["imgsz"] = self.imgsz
        res = self.model(frame_bgr, **kwargs)[0]
        names = res.names
        out: list[Detection] = []
        for b in res.boxes:
            label = _norm_label(names[int(b.cls)])
            if self.allow and label not in self.allow:
                continue
            x1, y1, x2, y2 = b.xyxyn[0].tolist()  # already normalised 0..1
            out.append(
                Detection(label=label, confidence=float(b.conf),
                          box=(x1, y1, x2, y2))
            )
        return out


class ThreadedDetector:
    """Run any detector on a background thread so the camera loop never blocks.

    ``detect(frame)`` hands the frame to the worker as the next one to process
    and immediately returns the most recently completed results (an empty list
    until the first detection finishes). Results therefore lag by up to one
    detection cycle, which is the right trade for a smooth real-time loop:
    inference that takes 100-250 ms no longer stalls the camera, the audio cues,
    or the preview. The worker always processes the newest frame handed to it and
    drops anything older, so it never falls behind.

    Wraps anything with a ``detect(frame) -> list[Detection]`` method, so it sits
    transparently in front of the TFLite or Ultralytics backends.
    """

    def __init__(self, base):
        self.base = base
        self._lock = threading.Lock()
        self._frame = None
        self._results: list[Detection] = []
        self._new = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        with self._lock:
            self._frame = frame_bgr
        self._new.set()
        with self._lock:
            return list(self._results)

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._new.wait(timeout=0.1):
                continue
            self._new.clear()
            with self._lock:
                frame = self._frame
                self._frame = None
            if frame is None:
                continue
            try:
                results = self.base.detect(frame)
            except Exception:
                results = []
            with self._lock:
                self._results = results

    def close(self) -> None:
        self._stop.set()
        self._new.set()
        self._thread.join(timeout=1.0)


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
        det = TFLiteDetector(det_cfg)
    elif backend == "ultralytics":
        det = UltralyticsDetector(det_cfg)
    elif backend == "hailo":
        raise NotImplementedError(
            "Hailo backend stub: install hailo-all and wire the HailoRT pipeline "
            "here, returning announcer.Detection objects with the same interface "
            "as TFLiteDetector."
        )
    else:
        raise ValueError(f"Unknown object_detection.backend: {backend!r}")
    # Optionally move inference off the camera loop (worth it for heavier models).
    if det_cfg.get("threaded"):
        det = ThreadedDetector(det)
    return det

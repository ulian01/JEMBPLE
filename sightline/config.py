"""Central configuration loading.

Reads ``config.yaml`` from the project root (or ``$SIGHTLINE_CONFIG``) and
overlays it on top of sane defaults, so every value has a fallback and the
demos run even with no config file present.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a hard dep, but degrade gracefully
    yaml = None

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "camera": {
        "source": "auto",       # auto | picamera | <webcam index e.g. 0> | /path/to/video|image
        "width": 640,
        "height": 480,
        "fps": 15,
        "rotation": 0,          # 0/90/180/270 — depends on how the strap sits
        "hflip": False,
        "vflip": False,
    },
    "display": {
        "preview": False,       # on a laptop, show an annotated window (you can see it)
        "window": "Sightline",
    },
    "speech": {
        "engine": "auto",        # auto | piper | espeak
        "piper_model": "",       # path to a .onnx Piper voice; empty => espeak
        "rate_wpm": 190,         # espeak speaking rate (higher = faster)
        "piper_length_scale": 0.9,      # piper speed: LOWER = faster (1.0 = normal)
        "piper_sentence_silence": 0.05, # piper pause (s) after each sentence; lower = snappier
        "period_pause": "normal",       # normal | comma (full stop pauses like a comma) | none
        "audio_device": "default",  # ALSA device for aplay (USB speaker, BT, HAT)
        "volume": 1.0,
    },
    "audio_cues": {
        "enabled": True,
        "sample_rate": 22050,
        "max_distance_m": 4.0,   # objects past this don't trigger proximity tones
    },
    "announcer": {
        "repeat_suppress_s": 6.0,   # don't re-announce the same label this often
        "min_confidence": 0.55,
    },
    "object_detection": {
        "backend": "auto",          # auto | tflite | ultralytics | hailo
        "model": "models/ssd_mobilenet_v2_coco_quant.tflite",  # used by tflite backend
        "labels": "models/coco_labels.txt",
        # ultralytics (YOLO) model. yolov8n.pt = 80 COCO classes; swap in
        # yolov8s-oiv7.pt for ~600 Open Images classes (a lot more objects).
        "ultralytics_model": "yolov8n.pt",   # auto-downloads on first run (x86 laptops)
        "open_vocab": [],           # non-empty => YOLO-World detects these named classes
        "world_model": "yolov8s-world.pt",   # the open-vocabulary model (needs `clip`)
        "imgsz": 0,                 # inference size; 0 = model default. lower = faster
        "threaded": False,          # run detection on a background thread (smoother)
        "threshold": 0.5,
        "announce_classes": [],     # empty => announce everything above threshold
    },
    "faces": {
        "known_dir": "known_faces",
        "tolerance": 0.6,           # lower = stricter match
        "model": "hog",             # hog (CPU, fast) | cnn (accurate, slow)
    },
    "ocr": {
        "backend": "auto",          # auto | claude | easyocr | tesseract
        "model": "claude-opus-4-8", # for the claude backend (haiku/sonnet = faster/cheaper)
        "lang": "eng",
        "min_chars": 2,
    },
    "scene": {
        "model": "claude-opus-4-8",
        "style": "succinct",        # succinct (terse fragments, cheap) | full (sentences)
        "max_tokens": 400,
        "max_image_edge": 1024,     # downscale before upload to save tokens/bandwidth
    },
    "buttons": {
        "enabled": False,           # set True when GPIO buttons are wired
        "mode_pin": 17,             # cycle modes
        "action_pin": 27,           # trigger one-shot (OCR / scene)
    },
    "voice": {
        "enabled": True,            # listen for "<wakeword> <command>"
        "model": "",                # path to a Vosk model dir; empty => voice off (buttons only)
        "wakeword": "sight",
        "samplerate": 16000,
        "device": None,             # input device index/name; None = default mic
    },
    "app": {
        "detect_interval": 2,       # run object detection every Nth frame (perf)
        "beeps": False,             # distance proximity beeps — off until "SIGHT distance"
        "beep_volume": 0.25,        # low + quiet so it sits under speech
        "announce_objects": False,  # also speak newly-seen objects (can be chatty)
        "read_chunk_chars": 240,    # long-read page size — "SIGHT next" advances
        "headless": False,          # no preview window (auto-on when no display)
    },
    "bluetooth": {
        "enabled": False,           # poll and auto-reconnect a Bluetooth headset
        "mac": "",                  # device address, e.g. AA:BB:CC:DD:EE:FF (pair once first)
        "poll_interval": 15.0,      # seconds between reconnect attempts
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Return the merged configuration dict."""
    cfg_path = Path(path or os.environ.get("SIGHTLINE_CONFIG", _PROJECT_ROOT / "config.yaml"))
    user_cfg: dict[str, Any] = {}
    if cfg_path.is_file() and yaml is not None:
        with open(cfg_path) as fh:
            user_cfg = yaml.safe_load(fh) or {}
    return _deep_merge(DEFAULTS, user_cfg)


def resolve_path(rel: str) -> Path:
    """Resolve a config-relative path against the project root."""
    p = Path(rel)
    return p if p.is_absolute() else _PROJECT_ROOT / p

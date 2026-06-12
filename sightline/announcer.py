"""Announcement throttling & phrasing.

A naive "speak every detection every frame" floods the user and makes the device
unusable. The Announcer:

* suppresses repeats of the same label within a time window,
* turns a bounding box into a human phrase ("a person, to your left, close"),
* lets safety-critical callers bypass the throttle.

Direction comes from the box centre's horizontal position; rough distance is
inferred from box height (a taller box ≈ nearer), which is crude but works
without a depth sensor. Swap in a real depth source by passing ``distance_m``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

# Classes worth warning about as obstacles: things a walking user could collide
# with. Single source of truth, used by the proximity beeps in app.py and
# demos/05. Names are lowercase to match the normalised detector labels, and the
# list spans both vocabularies (COCO's 80 classes and the larger Open Images
# set), so entries that a given model never emits simply never fire.
OBSTACLE_CLASSES = frozenset({
    # people and animals
    "person", "man", "woman", "boy", "girl", "dog", "cat", "horse",
    # seating and furniture
    "chair", "stool", "bench", "couch", "sofa bed", "bed", "loveseat",
    "table", "desk", "dining table", "coffee table", "kitchen & dining room table",
    "cabinetry", "wardrobe", "cupboard", "bookcase", "nightstand", "drawer",
    "shelf", "filing cabinet",
    # appliances and large fixtures
    "tv", "television", "refrigerator", "oven", "washing machine",
    "dishwasher", "wood-burning stove",
    # openings and level changes
    "door", "stairs",
    # plants
    "potted plant", "houseplant", "tree", "plant",
    # vehicles and street furniture
    "bicycle", "car", "motorcycle", "bus", "truck", "train", "van",
    "fire hydrant", "street light", "traffic light", "parking meter",
    "stop sign", "pole",
})


@dataclass
class Detection:
    label: str
    confidence: float
    # normalised box in [0,1]: (x1, y1, x2, y2)
    box: tuple[float, float, float, float]

    @property
    def cx(self) -> float:
        return (self.box[0] + self.box[2]) / 2

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]


def horizontal_phrase(cx: float) -> str:
    if cx < 0.33:
        return "to your left"
    if cx > 0.66:
        return "to your right"
    return "ahead"


def pan_from_cx(cx: float) -> float:
    """Map centre-x in [0,1] to a stereo pan in [-1,1]."""
    return (cx - 0.5) * 2


def distance_phrase(box_height: float) -> str:
    # taller box => closer. Tuned for a chest/arm mounted camera.
    if box_height > 0.6:
        return "very close"
    if box_height > 0.35:
        return "close"
    if box_height > 0.18:
        return "nearby"
    return "in the distance"


def estimate_distance_m(box_height: float, max_distance: float = 4.0) -> float:
    """Very rough monocular distance proxy from normalised box height."""
    h = max(0.02, min(box_height, 1.0))
    # inverse-ish: a full-frame object ~0.5 m, a tiny one ~max_distance
    return float(min(max_distance, 0.5 / h))


class Announcer:
    def __init__(self, cfg: dict):
        self.suppress_s = float(cfg.get("repeat_suppress_s", 6.0))
        self.min_conf = float(cfg.get("min_confidence", 0.55))
        self._last_said: dict[str, float] = {}

    def should_announce(self, label: str, confidence: float, *, force: bool = False) -> bool:
        if not force and confidence < self.min_conf:
            return False
        now = time.monotonic()
        last = self._last_said.get(label, 0.0)
        if not force and (now - last) < self.suppress_s:
            return False
        self._last_said[label] = now
        return True

    def phrase(self, det: Detection, *, with_distance: bool = True) -> str:
        parts = [_article(det.label)]
        parts.append(horizontal_phrase(det.cx))
        if with_distance:
            parts.append(distance_phrase(det.height))
        return ", ".join(parts)


def _article(label: str) -> str:
    label = label.replace("_", " ")
    if label and label[0].lower() in "aeiou":
        return f"an {label}"
    return f"a {label}"

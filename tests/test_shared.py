"""Tests for the consolidated shared helpers (plan 004)."""
from __future__ import annotations

import base64

import numpy as np
import pytest

from sightline.announcer import OBSTACLE_CLASSES

cv2 = pytest.importorskip("cv2")
from sightline.imaging import encode_jpeg  # noqa: E402  (after importorskip)


def test_obstacle_classes():
    # A frozenset of lowercase names spanning the COCO and Open Images
    # vocabularies. Assert the invariants and the must-have core rather than an
    # exact list, so adding an obstacle class does not break the test.
    assert isinstance(OBSTACLE_CLASSES, frozenset)
    assert all(c == c.lower() for c in OBSTACLE_CLASSES)
    core = {"person", "chair", "table", "car", "bicycle", "dog",
            "door", "stairs", "couch", "tv"}
    assert core <= set(OBSTACLE_CLASSES)
    assert len(OBSTACLE_CLASSES) >= 25


def test_encode_jpeg_returns_base64_jpeg():
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    s = encode_jpeg(frame, max_edge=64)
    assert isinstance(s, str) and s
    raw = base64.standard_b64decode(s)
    assert raw[:2] == b"\xff\xd8"   # JPEG start-of-image marker


def test_encode_jpeg_downscales_to_max_edge():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)   # long edge 200
    raw = base64.standard_b64decode(encode_jpeg(frame, max_edge=50))
    decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert max(decoded.shape[:2]) <= 50


def test_encode_jpeg_quality_param_affects_size():
    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)
    assert len(encode_jpeg(frame, 64, quality=95)) > len(encode_jpeg(frame, 64, quality=10))

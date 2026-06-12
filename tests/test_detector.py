"""Tests for label normalisation and the threaded detector wrapper.

These use a fake base detector, so no model download, camera, or ultralytics
install is needed.
"""
from __future__ import annotations

import time

import pytest

from sightline.announcer import Detection
from sightline.detector import ThreadedDetector, _norm_label


@pytest.mark.parametrize("raw,expected", [
    ("Person", "person"),
    ("FIRE HYDRANT", "fire hydrant"),
    ("potted_plant", "potted plant"),
    ("  Sofa_Bed  ", "sofa bed"),
    ("Dining Table", "dining table"),
])
def test_norm_label(raw, expected):
    assert _norm_label(raw) == expected


class FakeDetector:
    """Records calls and returns a canned detection, optionally slowly."""
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        return [Detection("person", 0.9, (0.0, 0.0, 0.5, 0.5))]


def test_threaded_detector_returns_empty_before_first_result():
    td = ThreadedDetector(FakeDetector())
    assert td.detect("frame") == []   # nothing processed yet
    td.close()


def test_threaded_detector_eventually_returns_results():
    base = FakeDetector()
    td = ThreadedDetector(base)
    res = []
    deadline = time.time() + 2.0
    while time.time() < deadline:
        res = td.detect("frame")
        if res:
            break
        time.sleep(0.01)
    assert res and res[0].label == "person"
    assert base.calls >= 1
    td.close()


def test_threaded_detector_detect_is_non_blocking():
    # base.detect takes 0.3s; detect() must not wait for it.
    td = ThreadedDetector(FakeDetector(delay=0.3))
    start = time.time()
    for _ in range(5):
        td.detect("frame")
    assert time.time() - start < 0.2   # five calls well under one 0.3s inference
    td.close()


def test_threaded_detector_close_stops_thread():
    td = ThreadedDetector(FakeDetector())
    td.detect("frame")
    td.close()
    assert not td._thread.is_alive()


def test_threaded_detector_survives_base_exception():
    class Boom:
        def detect(self, frame):
            raise RuntimeError("boom")
    td = ThreadedDetector(Boom())
    # Should not raise; results stay empty.
    for _ in range(5):
        assert td.detect("frame") == []
        time.sleep(0.02)
    td.close()

from __future__ import annotations

import pytest

from sightline.announcer import (
    Announcer,
    Detection,
    _article,
    distance_phrase,
    estimate_distance_m,
    horizontal_phrase,
    pan_from_cx,
)


@pytest.mark.parametrize("cx,expected", [
    (0.0, "to your left"),
    (0.2, "to your left"),
    (0.33, "ahead"),     # boundary: not < 0.33
    (0.5, "ahead"),
    (0.66, "ahead"),     # boundary: not > 0.66
    (0.9, "to your right"),
    (1.0, "to your right"),
])
def test_horizontal_phrase(cx, expected):
    assert horizontal_phrase(cx) == expected


@pytest.mark.parametrize("cx,expected", [(0.0, -1.0), (0.5, 0.0), (1.0, 1.0)])
def test_pan_from_cx(cx, expected):
    assert pan_from_cx(cx) == pytest.approx(expected)


@pytest.mark.parametrize("h,expected", [
    (0.7, "very close"),
    (0.6, "close"),       # boundary: not > 0.6
    (0.5, "close"),
    (0.2, "nearby"),
    (0.18, "in the distance"),  # boundary: not > 0.18
    (0.05, "in the distance"),
])
def test_distance_phrase(h, expected):
    assert distance_phrase(h) == expected


@pytest.mark.parametrize("h,expected", [
    (0.5, 1.0),     # 0.5 / 0.5
    (1.0, 0.5),     # 0.5 / 1.0
    (0.01, 4.0),    # clamped to 0.02 -> 0.5/0.02 = 25, capped at max 4.0
])
def test_estimate_distance_m(h, expected):
    assert estimate_distance_m(h, 4.0) == pytest.approx(expected)


def test_estimate_distance_m_respects_max():
    assert estimate_distance_m(0.02, 2.0) == pytest.approx(2.0)


@pytest.mark.parametrize("label,expected", [
    ("chair", "a chair"),
    ("apple", "an apple"),
    ("potted_plant", "a potted plant"),
    ("orange", "an orange"),
])
def test_article(label, expected):
    assert _article(label) == expected


def test_detection_geometry():
    d = Detection("chair", 0.9, (0.2, 0.1, 0.6, 0.9))
    assert d.cx == pytest.approx(0.4)
    assert d.height == pytest.approx(0.8)


def test_phrase_with_and_without_distance():
    d = Detection("chair", 0.9, (0.0, 0.0, 0.4, 0.5))  # cx=0.2 left, height=0.5 close
    assert Announcer({}).phrase(d) == "a chair, to your left, close"
    assert Announcer({}).phrase(d, with_distance=False) == "a chair, to your left"


def test_should_announce_confidence_floor():
    a = Announcer({"min_confidence": 0.55, "repeat_suppress_s": 100.0})
    assert a.should_announce("person", 0.4) is False     # below floor
    assert a.should_announce("person", 0.9) is True       # above floor, first time


def test_should_announce_repeat_suppression():
    a = Announcer({"min_confidence": 0.0, "repeat_suppress_s": 100.0})
    assert a.should_announce("dog", 1.0) is True
    assert a.should_announce("dog", 1.0) is False          # within suppress window
    assert a.should_announce("cat", 1.0) is True           # different label, allowed


def test_should_announce_force_bypasses_both_gates():
    a = Announcer({"min_confidence": 0.55, "repeat_suppress_s": 100.0})
    assert a.should_announce("car", 0.1, force=True) is True   # ignores floor
    assert a.should_announce("car", 0.1, force=True) is True   # ignores suppress

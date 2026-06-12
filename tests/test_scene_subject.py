"""Tests for the focused-subject describe path (SIGHT describe <subject>).

The anthropic client is faked, so no network or key is needed. We capture the
request the describer would send and assert the subject changes the system
prompt, the user text, and the token budget.
"""
from __future__ import annotations

import pytest

pytest.importorskip("cv2")
import numpy as np

from sightline import scene
from sightline.scene import SceneDescriber, _SUBJECT_SYSTEM, _SUCCINCT_SYSTEM


class _FakeStream:
    def __init__(self, captured, text="a blue usb cable, coiled."):
        self._captured = captured
        self.text_stream = [text]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeMessages:
    def __init__(self, captured):
        self._captured = captured

    def stream(self, **kwargs):
        self._captured.update(kwargs)
        return _FakeStream(self._captured)


class _FakeClient:
    def __init__(self, captured):
        self.messages = _FakeMessages(captured)


def _describer(monkeypatch, captured):
    # Avoid constructing the real anthropic client.
    monkeypatch.setattr(SceneDescriber, "__init__",
                        lambda self, cfg: None)
    d = SceneDescriber({})
    d.model = "claude-haiku-4-5"
    d.style = "succinct"
    d.max_edge = 512
    d.max_tokens = 160
    d.client = _FakeClient(captured)
    return d


def _frame():
    return np.zeros((48, 64, 3), dtype=np.uint8)


def test_describe_without_subject_uses_scene_prompt(monkeypatch):
    captured = {}
    d = _describer(monkeypatch, captured)
    out = d.describe(_frame())
    assert out                                   # returns the streamed text
    assert captured["system"] == _SUCCINCT_SYSTEM
    assert captured["max_tokens"] == 160
    user_text = captured["messages"][0]["content"][1]["text"]
    assert "in front of me" in user_text.lower()


def test_describe_with_subject_uses_subject_prompt(monkeypatch):
    captured = {}
    d = _describer(monkeypatch, captured)
    out = d.describe(_frame(), subject="usb cable")
    assert out
    assert captured["system"] == _SUBJECT_SYSTEM
    assert captured["max_tokens"] >= 300         # more room for detail
    user_text = captured["messages"][0]["content"][1]["text"]
    assert "usb cable" in user_text.lower()


def test_subject_is_whitespace_tolerant(monkeypatch):
    captured = {}
    d = _describer(monkeypatch, captured)
    d.describe(_frame(), subject="   ")           # blank -> treated as no subject
    assert captured["system"] == _SUCCINCT_SYSTEM

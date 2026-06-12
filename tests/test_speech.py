"""Thread-safety tests for sightline.speech.Speaker (plan 003).

No real audio is produced: the renderer is replaced with a fake that uses a
FakeProc, so we test the locking contract, not espeak/piper/aplay.
"""
from __future__ import annotations

import threading
import time

import pytest

from sightline.speech import Speaker


class FakeProc:
    """Minimal stand-in for subprocess.Popen for the speech process handle."""
    def __init__(self):
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self._alive = False

    def wait(self):
        while self._alive:
            time.sleep(0.005)


def _make_speaker():
    spk = Speaker({"audio_device": "default", "volume": 1.0, "rate_wpm": 190})
    spk.engine = "espeak"   # deterministic; renderer is replaced below
    return spk


def test_renders_are_serialized(monkeypatch):
    """Two concurrent _speak() calls must not overlap (one voice at a time)."""
    spk = _make_speaker()
    active = {"n": 0, "max": 0}
    guard = threading.Lock()

    def fake_render(text):
        with guard:
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
        time.sleep(0.05)
        with guard:
            active["n"] -= 1

    monkeypatch.setattr(spk, "_speak_espeak", fake_render)

    threads = [threading.Thread(target=spk._speak, args=(f"line {i}",))
               for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    assert active["max"] == 1   # never two renders at once
    spk.close()


def test_interrupt_terminates_live_proc(monkeypatch):
    """interrupt() must terminate the process a render is currently blocked on."""
    spk = _make_speaker()

    def fake_render(text):
        proc = FakeProc()
        spk._set_proc(proc)
        proc.wait()             # blocks until terminate() flips _alive

    monkeypatch.setattr(spk, "_speak_espeak", fake_render)

    t = threading.Thread(target=spk._speak, args=("hello",))
    t.start()
    time.sleep(0.05)            # let the render start and set _proc
    assert spk.is_busy() is True
    spk.interrupt()             # from this (main) thread
    t.join(timeout=1.0)
    assert not t.is_alive()     # render returned because proc was terminated
    spk.close()


def test_is_busy_false_when_idle():
    spk = _make_speaker()
    assert spk.is_busy() is False
    spk.close()

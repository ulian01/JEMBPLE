"""Regression test for the headless-boot crash fix (plan 002).

Before the fix, main.main() called termios.tcgetattr() unconditionally and
crashed when stdin was not a TTY (e.g. under systemd). These tests verify the
branch selection without launching real cameras, detectors, or audio.
"""
from __future__ import annotations

import types

import main as main_mod


class _StubSpeaker:
    def say_blocking(self, text):  # noqa: D401 - test stub
        pass


class _StubController:
    """Stands in for main.Controller: records lifecycle, does no real work."""
    instances = []

    def __init__(self, cfg):
        self.speaker = _StubSpeaker()
        self.selected = None
        self.closed = False
        _StubController.instances.append(self)

    def select_mode(self, idx):
        self.selected = idx

    def close(self):
        self.closed = True


def _install_stubs(monkeypatch, *, isatty: bool):
    _StubController.instances = []
    monkeypatch.setattr(main_mod, "config",
                        types.SimpleNamespace(load=lambda: {}))
    monkeypatch.setattr(main_mod, "Controller", _StubController)
    monkeypatch.setattr(main_mod, "_maybe_setup_gpio", lambda ctrl, cfg: None)
    # Replace sys.stdin with a stub exposing isatty(); avoids touching the real
    # terminal/file descriptor during the test.
    monkeypatch.setattr(main_mod.sys, "stdin",
                        types.SimpleNamespace(isatty=lambda: isatty))


def test_headless_branch_when_no_tty(monkeypatch):
    _install_stubs(monkeypatch, isatty=False)
    called = []
    monkeypatch.setattr(main_mod, "_run_keyboard",
                        lambda ctrl: called.append("keyboard"))
    monkeypatch.setattr(main_mod, "_run_headless",
                        lambda ctrl: called.append("headless"))

    main_mod.main()

    assert called == ["headless"]                 # did NOT touch termios
    assert _StubController.instances[0].closed     # finally ran ctrl.close()
    assert _StubController.instances[0].selected == 0


def test_keyboard_branch_when_tty(monkeypatch):
    _install_stubs(monkeypatch, isatty=True)
    called = []
    monkeypatch.setattr(main_mod, "_run_keyboard",
                        lambda ctrl: called.append("keyboard"))
    monkeypatch.setattr(main_mod, "_run_headless",
                        lambda ctrl: called.append("headless"))

    main_mod.main()

    assert called == ["keyboard"]
    assert _StubController.instances[0].closed

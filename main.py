#!/usr/bin/env python3
"""Sightline mode controller — the on-body launcher.

A blind user can't read a screen, so the device is driven by two buttons (or two
keys on a keyboard for development):

* **MODE** — cycle through capabilities; the new mode is spoken aloud.
* **ACTION** — for on-demand modes (Text reader, Scene describer) triggers a
  single capture; ignored by the always-on modes.

Each capability runs as its own subprocess so a crash in one never takes the
whole device down, and so this controller stays tiny. Continuous modes start
automatically when selected; on-demand modes wait for ACTION.

Run:
    python3 main.py                 # keyboard: 'm' = mode, 'a' = action, 'q' = quit
With GPIO buttons wired and buttons.enabled=true in config.yaml, the physical
buttons do the same thing.
"""
from __future__ import annotations

import select
import signal
import subprocess
import sys
import termios
import threading
import tty
from pathlib import Path

from sightline import config
from sightline.speech import Speaker

ROOT = Path(__file__).resolve().parent
DEMOS = ROOT / "demos"

# (spoken name, script, on_demand?)
MODES = [
    ("Object detection", DEMOS / "01_object_detector.py", False),
    ("Face recognition", DEMOS / "02_face_recognizer.py", False),
    ("Obstacle alerts", DEMOS / "05_obstacle_alert.py", False),
    ("Text reader", DEMOS / "03_text_reader.py", True),
    ("Scene describer", DEMOS / "04_scene_describer.py", True),
]


class Controller:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.speaker = Speaker(cfg["speech"])
        self.idx = -1
        self.child: subprocess.Popen | None = None

    def _stop_child(self) -> None:
        if self.child and self.child.poll() is None:
            self.child.terminate()
            try:
                self.child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.child.kill()
        self.child = None

    def select_mode(self, idx: int) -> None:
        self._stop_child()
        self.idx = idx % len(MODES)
        name, script, on_demand = MODES[self.idx]
        self.speaker.say_blocking(name)
        # On-demand modes read from stdin to trigger; give them a pipe so ACTION
        # can poke them. Continuous modes just run.
        self.child = subprocess.Popen(
            [sys.executable, str(script)],
            stdin=subprocess.PIPE if on_demand else subprocess.DEVNULL,
        )

    def next_mode(self) -> None:
        self.select_mode(self.idx + 1)

    def action(self) -> None:
        if self.idx < 0:
            return
        _, _, on_demand = MODES[self.idx]
        if on_demand and self.child and self.child.stdin:
            try:
                self.child.stdin.write(b"\n")
                self.child.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass

    def close(self) -> None:
        self._stop_child()
        self.speaker.say_blocking("Goodbye.")
        self.speaker.close()


def _maybe_setup_gpio(ctrl: Controller, cfg: dict):
    """Wire physical buttons if configured and gpiozero is available."""
    if not cfg["buttons"].get("enabled"):
        return None
    try:
        from gpiozero import Button
    except Exception:
        print("gpiozero not available; buttons disabled.")
        return None
    mode_btn = Button(cfg["buttons"]["mode_pin"], bounce_time=0.1)
    action_btn = Button(cfg["buttons"]["action_pin"], bounce_time=0.1)
    mode_btn.when_pressed = ctrl.next_mode
    action_btn.when_pressed = ctrl.action
    return mode_btn, action_btn


def _run_keyboard(ctrl: "Controller") -> None:
    """Interactive raw-keyboard control (development / when a TTY is present)."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            if select.select([sys.stdin], [], [], 0.2)[0]:
                ch = sys.stdin.read(1).lower()
                if ch == "m":
                    ctrl.next_mode()
                elif ch == "a":
                    ctrl.action()
                elif ch == "q":
                    break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _run_headless(ctrl: "Controller") -> None:
    """No TTY (e.g. under systemd at boot): the GPIO button callbacks drive the
    modes on gpiozero's own thread, so the main thread only needs to stay alive
    and shut down cleanly on SIGTERM (systemd stop) or Ctrl-C."""
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        stop.wait()
    except KeyboardInterrupt:
        pass


def main() -> None:
    cfg = config.load()
    ctrl = Controller(cfg)
    _maybe_setup_gpio(ctrl, cfg)

    ctrl.speaker.say_blocking(
        "Sightline ready. Press mode to begin, action to capture."
    )
    ctrl.select_mode(0)

    try:
        if sys.stdin.isatty():
            _run_keyboard(ctrl)
        else:
            print("No TTY; running headless — GPIO buttons drive modes. "
                  "Send SIGTERM or Ctrl-C to stop.")
            _run_headless(ctrl)
    finally:
        ctrl.close()


if __name__ == "__main__":
    main()

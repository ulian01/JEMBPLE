# Plan 002: Stop `main.py` from crash-looping on headless / systemd boot

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: this repository is **not** under version control,
> so there is no commit SHA. Before editing, open `main.py` and confirm the
> quoted `main()` excerpt still matches the live code. On any mismatch, treat it
> as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-test-baseline.md (for the test harness only)
- **Category**: bug
- **Planned at**: no VCS (not a git repo) — snapshot 2026-06-12

## Why this matters

`main.py` is the device's documented autostart entry point — `systemd/sightline.service`
runs `ExecStart=/usr/bin/python3 .../main.py` as a `Type=simple` service with
`Restart=on-failure`. But `main()` unconditionally calls
`termios.tcgetattr(sys.stdin.fileno())` to set up raw keyboard input. Under
systemd there is **no TTY** on stdin, so that call raises
`termios.error: (25, 'Inappropriate ioctl for device')` (confirmed empirically)
the moment the service starts. The process dies, `Restart=on-failure` relaunches
it, and it dies again — an infinite crash loop. The GPIO buttons are wired one
line earlier (`_maybe_setup_gpio`) but the controller never reaches a state
where they can drive it.

In short: the on-strap, button-driven deployment — the whole point of the
device — does not boot today. The fix is to run the raw-keyboard loop only when
stdin is an interactive terminal, and otherwise idle so the GPIO callback thread
drives the device, shutting down cleanly on `SIGTERM` (how systemd stops a
service) or `Ctrl-C`.

## Current state

`main.py` imports (top of file, lines 22-27):

```python
import select
import subprocess
import sys
import termios
import tty
from pathlib import Path
```

The relevant function, `main.py:109-138`:

```python
def main() -> None:
    cfg = config.load()
    ctrl = Controller(cfg)
    _maybe_setup_gpio(ctrl, cfg)

    ctrl.speaker.say_blocking(
        "Sightline ready. Press mode to begin, action to capture."
    )
    ctrl.select_mode(0)

    # Keyboard control for development / accessibility testing.
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
        ctrl.close()
```

Context the executor needs:
- `Controller` (`main.py:45-90`) is built earlier; `ctrl.close()` stops the
  child subprocess, says "Goodbye", and closes the speaker. It must run on exit.
- `_maybe_setup_gpio(ctrl, cfg)` (`main.py:93-106`) wires `gpiozero` Button
  callbacks (`ctrl.next_mode`, `ctrl.action`) when `buttons.enabled` is true.
  `gpiozero` runs those callbacks on its **own background thread**, so once
  buttons are wired the main thread only needs to stay alive — it does not need
  to read stdin at all.
- `signal.signal(...)` must be called from the main thread; `main()` runs on the
  main thread, so this is safe.

**Conventions to match**: module-level imports grouped as above; functions use
`from __future__ import annotations` (already at top of file) and type hints.

## Commands you will need

| Purpose        | Command                                                        | Expected on success |
|----------------|----------------------------------------------------------------|---------------------|
| Syntax check   | `.venv/bin/python -c "import ast; ast.parse(open('main.py').read()); print('ok')"` | prints `ok`, exit 0 |
| Non-TTY repro  | `.venv/bin/python -c "import termios,os; fd=os.open('/dev/null',os.O_RDONLY); termios.tcgetattr(fd)"` | (before fix context) raises `termios.error` — proves the crash |
| Run tests      | `.venv/bin/python -m pytest -q tests/test_main_headless.py`    | all pass, exit 0 |
| Full suite     | `.venv/bin/python -m pytest -q`                                | all pass, exit 0 |

If `.venv/bin/python` is missing, substitute `python3` and note it.

## Scope

**In scope**:
- `main.py` (modify `main()`; add two helper functions; add imports)
- `tests/test_main_headless.py` (create)

**Out of scope** (do NOT touch):
- `Controller` and `_maybe_setup_gpio` — their behavior is correct; only the
  loop-selection in `main()` is wrong.
- `systemd/sightline.service` — the unit file is fine once `main.py` no longer
  crashes; do not change it.
- `app.py` — the production voice app has its own loop and is unaffected.

## Git workflow

Not a git repository. Do not init/commit/push. Just edit the files.

## Steps

### Step 1: Add the `signal` and `threading` imports

In `main.py`, the import block currently reads (lines 22-27):

```python
import select
import subprocess
import sys
import termios
import tty
from pathlib import Path
```

Change it to (keep alphabetical-ish grouping consistent with the file):

```python
import select
import signal
import subprocess
import sys
import termios
import threading
import tty
from pathlib import Path
```

**Verify**: `.venv/bin/python -c "import ast; ast.parse(open('main.py').read()); print('ok')"` → `ok`.

### Step 2: Extract the keyboard loop and add a headless loop

Replace the entire body of `main()` (lines 109-138, the block quoted in
"Current state") with the following three definitions. The two helpers go
**immediately above** `main()`; `main()` keeps its existing setup lines and
swaps the loop for a branch:

```python
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
```

Note the type hints use the string form `"Controller"` because `Controller` is
defined above these functions in the file — keep it as a string to avoid any
forward-reference concern.

**Verify**: `.venv/bin/python -c "import ast; ast.parse(open('main.py').read()); print('ok')"` → `ok`.

### Step 3: Add a regression test

Create `tests/test_main_headless.py`. It imports the `main` module, replaces the
heavy collaborators with stubs, and asserts the **loop-selection** branch:
non-TTY → headless, TTY → keyboard. It also asserts `ctrl.close()` always runs
(the `finally`). This reuses `tests/conftest.py` from plan 001 for the import
path.

```python
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
```

Importing `main` pulls in `from sightline.speech import Speaker` (which only uses
stdlib + `shutil`), so the import is light and needs no API key or hardware. If
the import nonetheless fails, that is a STOP condition (see below).

**Verify**: `.venv/bin/python -m pytest -q tests/test_main_headless.py` → 2
passed, exit 0.

### Step 4: Run the full suite

**Verify**: `.venv/bin/python -m pytest -q` → all tests pass (the plan-001 tests
plus the 2 new ones), exit 0.

## Test plan

- New file `tests/test_main_headless.py` with two cases: non-TTY stdin selects
  `_run_headless` (the previously-crashing path) and TTY stdin selects
  `_run_keyboard`; both assert `ctrl.close()` ran via `finally`.
- Structural pattern: follows the monkeypatch style this plan introduces; uses
  `tests/conftest.py` from plan 001 for `sys.path`.
- The test deliberately stubs `_run_keyboard`/`_run_headless` so `main()` returns
  immediately — it verifies *branch selection*, which is the bug, without
  blocking on `stop.wait()` or reading a real terminal.

## Done criteria

ALL must hold:

- [ ] `main.py` parses (`ast.parse`) and `main()` calls `termios.tcgetattr`
      **only** inside `_run_keyboard`, which is reached **only** when
      `sys.stdin.isatty()` is true.
      Check: `grep -n "termios.tcgetattr" main.py` shows exactly one occurrence,
      inside `_run_keyboard`.
- [ ] `grep -n "isatty" main.py` shows the guard in `main()`.
- [ ] `.venv/bin/python -m pytest -q` exits 0; `tests/test_main_headless.py`
      has 2 passing tests.
- [ ] Only `main.py` and `tests/test_main_headless.py` were modified/created.
- [ ] `plans/README.md` status row for plan 002 updated to DONE.

## STOP conditions

Stop and report back (do not improvise) if:

- The `main()` excerpt in "Current state" does not match the live `main.py`.
- `import main` fails inside the test (e.g. it now imports a heavy module like
  `cv2`/`anthropic` at top level) — report what it tried to import; do not add
  workarounds that mask the real import.
- Plan 001 has not run, so `tests/conftest.py` does not exist: create the
  minimal `tests/conftest.py` shown in plan 001 (step 2) and `tests/__init__.py`,
  then continue — but note in your report that you bootstrapped the harness.
- `tty.setcbreak` / `termios` are not importable on the platform (non-POSIX):
  report — this device targets Linux only.

## Maintenance notes

- The headless path relies on `_maybe_setup_gpio` having wired the buttons; if
  `buttons.enabled` is false, a headless run will idle with no way to change
  modes (it will still play the initial mode 0). That is expected — document it
  if a future "headless-with-no-buttons" use case appears.
- A reviewer should confirm `signal.signal` is only ever called from `main()`
  (main thread) — moving `_run_headless` onto a worker thread would break it.
- Clean shutdown on systemd stop now depends on the `SIGTERM` handler; if a
  future change adds its own `SIGTERM` handler, reconcile the two so
  `ctrl.close()` still runs.
- Related, deferred: `app.py` (the voice app) also requires a cv2 GUI window and
  has no headless mode — that is direction finding **A** (headless/no-UI mode),
  not part of this plan.

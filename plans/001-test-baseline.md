# Plan 001: Establish a pytest baseline covering the pure-logic core

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: this repository is **not** under version control,
> so there is no commit SHA. Before editing, open each file named in
> "Current state" and confirm the quoted excerpts still match the live code. On
> any mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: no VCS (not a git repo) — snapshot 2026-06-12

## Why this matters

Sightline is an assistive device with a safety-critical channel (obstacle
alerts), yet it has **zero automated tests** — the only `test`-named file,
`tools/ocr_test.py`, is a manual one-shot script. Every other plan in this set
(`002` headless-boot fix, `003` Speaker thread-safety, `004` de-duplication)
is a change to live code with no net under it. This plan creates that net:
a `pytest` harness plus deterministic unit tests for the pure, hardware-free
logic. After it lands, any future change can be checked with one command, and
the regression tests in plans 002–004 have somewhere to live.

The targets here were chosen because they import with **only `numpy` + `PyYAML`**
(both core deps) — no `cv2`, `anthropic`, `vosk`, or camera hardware — so the
suite runs anywhere, fast.

## Current state

There is no `tests/` directory, no `pytest.ini`/`pyproject.toml`, and `pytest`
is not installed in `.venv`. The functions under test today:

- `sightline/announcer.py` — pure phrasing/throttle helpers, stdlib-only imports:
  - `horizontal_phrase(cx)` (lines 36-41): `cx<0.33 → "to your left"`,
    `cx>0.66 → "to your right"`, else `"ahead"`.
  - `pan_from_cx(cx)` (44-46): `return (cx - 0.5) * 2`.
  - `distance_phrase(h)` (49-57): `>0.6 "very close"`, `>0.35 "close"`,
    `>0.18 "nearby"`, else `"in the distance"`.
  - `estimate_distance_m(h, max_distance=4.0)` (60-64):
    `h = max(0.02, min(h, 1.0)); return min(max_distance, 0.5/h)`.
  - `_article(label)` (91-95): vowel-initial → `"an X"` else `"a X"`; `_`→space.
  - `Detection` dataclass (20-33) with `.cx == (box[0]+box[2])/2` and
    `.height == box[3]-box[1]`.
  - `Announcer.should_announce(label, confidence, *, force=False)` (73-81):
    below `min_confidence` and not `force` → False; within `repeat_suppress_s`
    of the last announce of that label and not `force` → False; otherwise True
    and records `time.monotonic()`.
  - `Announcer.phrase(det, *, with_distance=True)` (83-88):
    `", ".join([_article(label), horizontal_phrase(cx), distance_phrase(height)])`
    (drops the distance part when `with_distance=False`).
- `sightline/config.py` — stdlib + optional yaml:
  - `_deep_merge(base, override)` (100-107): recursive dict merge; a non-dict
    override value replaces whatever is in `base`.
  - `load(path=None)` (110-117): reads the YAML at `path` (or
    `$SIGHTLINE_CONFIG`, or the project `config.yaml`) and deep-merges it over
    `DEFAULTS`. A missing file yields `DEFAULTS` unchanged.
  - `resolve_path(rel)` (120-123): absolute path passes through; a relative one
    is joined onto the project root.
- `sightline/audio_cues.py` — needs `numpy` only (`sounddevice` import is
  wrapped in try/except):
  - `AudioCues._tone(freq, dur, pan, volume)` (45-60): returns an `(N, 2)`
    `float32` stereo buffer, `N = int(sr*dur)`; channel gains are
    `left = mono*sqrt((1-pan)/2)`, `right = mono*sqrt((1+pan)/2)`; a 10 ms
    attack/release envelope ramps both ends to 0; `volume` scales amplitude.

**Conventions to match** (this repo's style): every module starts with
`from __future__ import annotations`, uses type hints and short docstrings.
Tests do not exist yet, so there is no in-repo test exemplar — follow the
explicit structure in this plan.

## Commands you will need

| Purpose      | Command                                             | Expected on success |
|--------------|-----------------------------------------------------|---------------------|
| Interpreter  | `.venv/bin/python -V`                               | `Python 3.13.x` (any 3.x is fine) |
| Install pytest | `.venv/bin/python -m pip install pytest`          | exit 0 |
| Syntax check | `.venv/bin/python -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" tests/*.py` | exit 0 |
| Run tests    | `.venv/bin/python -m pytest -q`                     | all pass, exit 0 |

If `.venv/bin/python` does not exist, substitute `python3` in every command and
record that in your report. Do not create or rebuild the venv.

## Scope

**In scope** (create these files; modify nothing else):
- `pyproject.toml` (create — pytest config only)
- `tests/__init__.py` (create — empty)
- `tests/conftest.py` (create)
- `tests/test_announcer.py` (create)
- `tests/test_config.py` (create)
- `tests/test_audio_cues.py` (create)

**Out of scope** (do NOT touch):
- Any file under `sightline/`, `demos/`, `tools/`, or the app entry points
  (`app.py`, `main.py`). This plan only *adds tests* — it must not change
  behavior. If a test reveals a bug, record it in your report; do not fix it
  here.
- `requirements.txt` (dependency pinning is a separate finding).

## Git workflow

This repo is not a git repository. Do not run `git init`, commit, or push.
Just create the files.

## Steps

### Step 1: Install pytest and create the pytest config

Run `.venv/bin/python -m pip install pytest`.

Create `pyproject.toml` with exactly:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

**Verify**: `.venv/bin/python -m pytest --version` → prints a `pytest 8.x`
(or any) version line, exit 0.

### Step 2: Create the test package scaffolding

Create `tests/__init__.py` as an empty file.

Create `tests/conftest.py` so tests can import the `sightline` package from the
repo root regardless of where pytest is invoked:

```python
"""Pytest bootstrap: put the project root on sys.path so `import sightline`
works without installing the package."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

**Verify**: `.venv/bin/python -m pytest -q` → collects 0 tests, exit 0 (no
errors). Output ends with `no tests ran` — that is expected at this step.

### Step 3: Test `sightline/announcer.py`

Create `tests/test_announcer.py`:

```python
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
```

**Verify**: `.venv/bin/python -m pytest -q tests/test_announcer.py` → all tests
pass, exit 0. If any assertion fails, the *test* expectation is wrong (re-read
the excerpts in "Current state") — do **not** change `announcer.py`.

### Step 4: Test `sightline/config.py`

Create `tests/test_config.py`:

```python
from __future__ import annotations

from sightline import config
from sightline.config import _deep_merge


def test_deep_merge_nested():
    out = _deep_merge({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}})
    assert out == {"a": {"x": 1, "y": 3}}


def test_deep_merge_scalar_replaces_dict():
    out = _deep_merge({"a": {"x": 1}}, {"a": 5})
    assert out == {"a": 5}


def test_deep_merge_adds_new_key():
    out = _deep_merge({"a": 1}, {"b": 2})
    assert out == {"a": 1, "b": 2}


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    _deep_merge(base, {"a": {"x": 9}})
    assert base == {"a": {"x": 1}}


def test_load_missing_file_returns_defaults():
    cfg = config.load("/nonexistent/path/does-not-exist.yaml")
    assert cfg["camera"]["width"] == 640        # built-in default
    assert cfg["speech"]["volume"] == 1.0


def test_load_overlays_user_yaml(tmp_path):
    p = tmp_path / "user.yaml"
    p.write_text("camera:\n  width: 1280\n")
    cfg = config.load(p)
    assert cfg["camera"]["width"] == 1280       # overridden
    assert cfg["camera"]["height"] == 480       # default preserved
    assert cfg["speech"]["volume"] == 1.0       # untouched branch preserved


def test_resolve_path_absolute_passthrough():
    from pathlib import Path
    assert config.resolve_path("/abs/x") == Path("/abs/x")


def test_resolve_path_relative_joins_root():
    p = config.resolve_path("models/x.tflite")
    assert p.is_absolute()
    assert p.as_posix().endswith("models/x.tflite")
```

**Verify**: `.venv/bin/python -m pytest -q tests/test_config.py` → all pass.

### Step 5: Test `sightline/audio_cues.py`

Create `tests/test_audio_cues.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from sightline.audio_cues import AudioCues


def _cues():
    # backend="aplay" avoids touching sounddevice; _tone never plays audio.
    return AudioCues(
        {"enabled": True, "sample_rate": 22050, "max_distance_m": 4.0},
        device="default", backend="aplay",
    )


def test_tone_shape_and_dtype():
    buf = _cues()._tone(440.0, 0.1, 0.0, 0.5)
    assert buf.shape == (int(22050 * 0.1), 2)
    assert buf.dtype == np.float32


def test_tone_amplitude_bounded_by_volume():
    buf = _cues()._tone(440.0, 0.1, 0.0, 0.5)
    assert np.max(np.abs(buf)) <= 0.5 + 1e-6


def test_tone_pan_full_left_silences_right():
    buf = _cues()._tone(440.0, 0.1, -1.0, 0.5)
    left, right = buf[:, 0], buf[:, 1]
    assert np.allclose(right, 0.0, atol=1e-6)
    assert np.max(np.abs(left)) > 0.1


def test_tone_pan_full_right_silences_left():
    buf = _cues()._tone(440.0, 0.1, 1.0, 0.5)
    left, right = buf[:, 0], buf[:, 1]
    assert np.allclose(left, 0.0, atol=1e-6)
    assert np.max(np.abs(right)) > 0.1


def test_tone_centre_pan_balances_channels():
    buf = _cues()._tone(440.0, 0.1, 0.0, 0.5)
    rms_left = float(np.sqrt(np.mean(buf[:, 0] ** 2)))
    rms_right = float(np.sqrt(np.mean(buf[:, 1] ** 2)))
    assert rms_left == pytest.approx(rms_right, rel=1e-5)
```

**Verify**: `.venv/bin/python -m pytest -q tests/test_audio_cues.py` → all pass.

### Step 6: Run the whole suite

**Verify**: `.venv/bin/python -m pytest -q` → all tests across the three files
pass, exit 0. Note the total count (expect ~30+ passing tests).

## Test plan

This plan *is* the test plan. New files:
`tests/test_announcer.py`, `tests/test_config.py`, `tests/test_audio_cues.py`,
covering: phrasing/pan/distance math incl. all classification boundaries; the
announce confidence-floor, repeat-suppression, and `force` bypass; config deep
merge (nested, scalar-replaces-dict, new key, no-mutation) and YAML overlay; and
the stereo tone buffer's shape, dtype, amplitude bound, and L/R/centre pan
balance. No existing test serves as a pattern (there were none) — these become
the pattern for plans 002–004.

## Done criteria

ALL must hold:

- [ ] `.venv/bin/python -m pytest -q` exits 0 with every test passing
- [ ] `pyproject.toml`, `tests/__init__.py`, `tests/conftest.py`, and the three
      `tests/test_*.py` files exist
- [ ] No file under `sightline/`, `demos/`, `tools/`, `app.py`, or `main.py`
      was modified (these tests are additive only)
- [ ] `plans/README.md` status row for plan 001 updated to DONE

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" does not match the excerpts
  (the source has drifted since this plan was written).
- A test fails because the **source** behaves differently than the excerpts
  describe — that means either drift or a latent bug. Report it; do **not**
  edit `sightline/` to make a test pass.
- `.venv/bin/python` is missing AND `python3` lacks `numpy` or `PyYAML`
  (the suite cannot import its targets).
- `pip install pytest` fails (e.g. no network) — report; do not vendor pytest.

## Maintenance notes

- Plans 002, 003, and 004 add their own `tests/test_*.py` files reusing the
  `tests/conftest.py` created here — do not delete it.
- Deliberately *not* covered yet (next wave, heavier imports): `app.chunk_text`
  (pulls in `cv2` via `app.py`'s imports), `listen` synonym dispatch (needs a
  constructed `VoiceCommands`, which imports `vosk`), and `ocr._clean`/`_alnum`.
  Add these once a `cv2`-tolerant test lane exists.
- A reviewer should confirm the expected values in the parametrized cases match
  the source logic, since these tests now *define* the contract for that logic.

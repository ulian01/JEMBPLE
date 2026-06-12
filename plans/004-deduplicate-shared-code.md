# Plan 004: Consolidate three duplicated helpers into single sources of truth

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: this repository is **not** under version control,
> so there is no commit SHA. Before editing, open each file named below and
> confirm the quoted excerpts still match the live code. On any mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (one intentional, documented behavior change — see step 3)
- **Depends on**: plans/001-test-baseline.md (test harness)
- **Category**: tech-debt
- **Planned at**: no VCS (not a git repo) — snapshot 2026-06-12

## Why this matters

Three pieces of logic are copy-pasted and have already **drifted**, which is how
copies turn into bugs:

1. **`_encode_jpeg`** exists twice with *different JPEG quality* — `scene.py`
   (q=85) and `ocr.py` (q=90) — and `vision.py` imports the private `scene`
   copy. One downscale-and-encode helper should serve all three.
2. **The obstacle class set** is defined twice with *different membership*:
   `app.py`'s `OBSTACLES` has `tv`/`refrigerator`; `demos/05`'s
   `DEFAULT_OBSTACLES` has `fire hydrant`. They should be one shared set, so the
   safety-relevant "things to warn about" list can't silently diverge again.
3. **Bounding-box drawing** is implemented twice in `viz.py` — the module
   function `draw_detections` and an inline copy inside `Preview.update`.

Consolidating removes ~40 lines, kills the drift, and means future tweaks
(e.g. a new obstacle class, a different overlay color) happen in one place.
Changes 1 and 3 are behavior-preserving. Change 2 unifies to the **union** of
the two sets — a small, deliberate, documented behavior change (see step 3).

## Current state

### (1) `_encode_jpeg` duplication

`sightline/scene.py:93-101` (note `quality=85`):

```python
def _encode_jpeg(frame_bgr, max_edge: int) -> str:
    h, w = frame_bgr.shape[:2]
    scale = min(1.0, max_edge / max(h, w))
    if scale < 1.0:
        frame_bgr = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("Failed to JPEG-encode frame")
    return base64.standard_b64encode(buf.tobytes()).decode()
```

`scene.py` top imports include `import base64` and `import cv2`; after the move,
`scene.py` no longer references either directly (verify in step 2).

`scene.py:67` uses it: `img_b64 = _encode_jpeg(frame_bgr, self.max_edge)`.

`sightline/ocr.py:157-165` (note `quality=90`):

```python
def _encode_jpeg(frame_bgr: np.ndarray, max_edge: int) -> str:
    h, w = frame_bgr.shape[:2]
    scale = min(1.0, max_edge / max(h, w))
    if scale < 1.0:
        frame_bgr = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError("Failed to JPEG-encode frame")
    return base64.standard_b64encode(buf.tobytes()).decode()
```

`ocr.py` top imports `import base64` (used only by this function) and `import cv2`
(also used by `_prep_for_tesseract`, so cv2 stays). `ocr.py:104` uses it:
`img_b64 = _encode_jpeg(frame_bgr, max_edge=1600)`.

`sightline/vision.py:9`: `from .scene import _encode_jpeg`, used at
`vision.py:50`: `b64 = _encode_jpeg(frame_bgr, self.max_edge)` (so today vision
inherits scene's q=85).

### (2) obstacle set duplication

`app.py:42-46`:

```python
OBSTACLES = {
    "person", "chair", "bicycle", "car", "motorcycle", "bus", "truck", "dog",
    "potted plant", "couch", "dining table", "bench", "tv", "refrigerator",
}
WARN_HEIGHT = 0.30
```

`app.py:374` uses it inside `proximity_beep`:
`obstacles = [d for d in self._detections if d.label in OBSTACLES]`.
`app.py:38` already imports from announcer:
`from sightline.announcer import pan_from_cx, estimate_distance_m, horizontal_phrase`.

`demos/05_obstacle_alert.py:36-41`:

```python
DEFAULT_OBSTACLES = {
    "person", "chair", "bicycle", "car", "motorcycle", "bus", "truck",
    "dog", "potted plant", "couch", "dining table", "bench", "fire hydrant",
}
WARN_HEIGHT = 0.30   # box taller than this => emit a proximity sweep
SPEAK_HEIGHT = 0.55  # very close => also speak a spoken warning
```

`demos/05:52` uses it:
`obstacles = set(cfg["object_detection"].get("announce_classes") or []) or DEFAULT_OBSTACLES`.
`demos/05:29-31` imports:
`from sightline.announcer import (Announcer, pan_from_cx, estimate_distance_m, horizontal_phrase,)`.

### (3) box drawing duplication

`sightline/viz.py:16-26`, the canonical helper:

```python
def draw_detections(frame, detections, color=(0, 220, 0)) -> None:
    """Draw labeled boxes (objects with .box/.label/optional .confidence) in place."""
    h, w = frame.shape[:2]
    for d in detections or []:
        x1, y1, x2, y2 = d.box
        p1, p2 = (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h))
        cv2.rectangle(frame, p1, p2, color, 2)
        conf = getattr(d, "confidence", None)
        tag = d.label if not conf else f"{d.label} {conf:.2f}"
        cv2.putText(frame, tag, (p1[0], max(15, p1[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
```

`sightline/viz.py:35-57`, `Preview.update`, reimplements the same loop inline:

```python
    def update(self, frame, detections: Optional[Iterable] = None) -> bool:
        """Draw ``detections`` (objects with .box, .label, optional .confidence)
        on ``frame`` and show it. Returns True if the user pressed 'q'."""
        if not self._ok:
            return False
        try:
            img = frame.copy()
            h, w = img.shape[:2]
            for d in detections or []:
                x1, y1, x2, y2 = d.box
                p1 = (int(x1 * w), int(y1 * h))
                p2 = (int(x2 * w), int(y2 * h))
                cv2.rectangle(img, p1, p2, (0, 220, 0), 2)
                conf = getattr(d, "confidence", None)
                tag = d.label if conf is None else f"{d.label} {conf:.2f}"
                cv2.putText(img, tag, (p1[0], max(15, p1[1] - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1, cv2.LINE_AA)
            cv2.imshow(self.window, img)
            return (cv2.waitKey(1) & 0xFF) == ord("q")
        except cv2.error:
            # no GUI backend (headless) — disable and carry on
            self._ok = False
            return False
```

**Conventions to match**: every module begins `from __future__ import annotations`;
type hints throughout; short module docstrings.

## Commands you will need

| Purpose       | Command                                                                 | Expected |
|---------------|-------------------------------------------------------------------------|----------|
| Compile check | `.venv/bin/python -m py_compile app.py demos/05_obstacle_alert.py sightline/*.py` | exit 0 |
| Import smoke  | `.venv/bin/python -c "import sys;sys.path.insert(0,'.'); import sightline.imaging, sightline.scene, sightline.ocr, sightline.vision, sightline.viz, sightline.announcer; print('ok')"` | prints `ok` |
| Run tests     | `.venv/bin/python -m pytest -q`                                         | all pass |

If `.venv/bin/python` is missing, substitute `python3` and note it. The import
smoke works without `ANTHROPIC_API_KEY` because the `anthropic` import in
`scene.py`/`ocr.py`/`vision.py` is wrapped in try/except.

## Scope

**In scope**:
- `sightline/imaging.py` (create)
- `sightline/scene.py`, `sightline/ocr.py`, `sightline/vision.py` (use shared encoder)
- `sightline/announcer.py` (add `OBSTACLE_CLASSES`)
- `app.py`, `demos/05_obstacle_alert.py` (use shared obstacle set)
- `sightline/viz.py` (make `Preview.update` call `draw_detections`)
- `tests/test_shared.py` (create)

**Out of scope** (do NOT touch):
- The **prompt strings / models / token caps** in `scene.py`, `ocr.py`,
  `vision.py` — only the JPEG-encode call site changes.
- `WARN_HEIGHT` / `SPEAK_HEIGHT` constants — they stay where they are.
- Face-loading duplication (`faces.py` vs `demos/02`) and the
  "unknown person"/"unfamiliar person" label inconsistency — that is a separate
  finding with behavior nuance; do NOT fold it in here.
- `tests/test_announcer.py` from plan 001 — add new assertions in
  `tests/test_shared.py`, don't edit the existing file.

## Git workflow

Not a git repository. Do not init/commit/push. Just edit the files.

## Steps

### Step 1: Create the shared image helper

Create `sightline/imaging.py`:

```python
"""Shared image helpers used by the vision-model call sites (scene / OCR / VQA)."""
from __future__ import annotations

import base64

import cv2


def encode_jpeg(frame_bgr, max_edge: int, quality: int = 85) -> str:
    """Downscale ``frame_bgr`` so its long edge is <= ``max_edge`` and return it
    as a base64-encoded JPEG string. ``quality`` is the JPEG quality (0-100)."""
    h, w = frame_bgr.shape[:2]
    scale = min(1.0, max_edge / max(h, w))
    if scale < 1.0:
        frame_bgr = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to JPEG-encode frame")
    return base64.standard_b64encode(buf.tobytes()).decode()
```

**Verify**: `.venv/bin/python -c "import sys;sys.path.insert(0,'.'); from sightline.imaging import encode_jpeg; print('ok')"` → `ok`.

### Step 2: Point scene / ocr / vision at the shared encoder

**`sightline/scene.py`**:
- Delete the `_encode_jpeg` function (lines 93-101, quoted above).
- Remove the now-unused `import base64` and `import cv2` from the top of the file
  (confirm with `grep -n "base64\|cv2" sightline/scene.py` returns nothing after
  the edit; if either is still referenced somewhere you didn't expect, STOP).
- Add near the other relative imports (it already has none; add after the
  module docstring's imports): `from .imaging import encode_jpeg`.
- Change the call site (`scene.py:67`) from
  `img_b64 = _encode_jpeg(frame_bgr, self.max_edge)` to
  `img_b64 = encode_jpeg(frame_bgr, self.max_edge)` (default quality 85 — same as
  before).

**`sightline/ocr.py`**:
- Delete the `_encode_jpeg` function (lines 157-165).
- Remove `import base64` (used only by that function; `import cv2` and
  `import numpy as np` STAY — `_prep_for_tesseract` uses them).
- Add `from .imaging import encode_jpeg` with the other imports.
- Change the call site (`ocr.py:104`) from
  `img_b64 = _encode_jpeg(frame_bgr, max_edge=1600)` to
  `img_b64 = encode_jpeg(frame_bgr, max_edge=1600, quality=90)` (preserve q=90).

**`sightline/vision.py`**:
- Change `from .scene import _encode_jpeg` (line 9) to
  `from .imaging import encode_jpeg`.
- Change the call site (`vision.py:50`) from
  `b64 = _encode_jpeg(frame_bgr, self.max_edge)` to
  `b64 = encode_jpeg(frame_bgr, self.max_edge)` (default q=85 — same as the old
  behavior inherited from scene).

**Verify**:
- `grep -rn "_encode_jpeg" sightline/` → **no matches** (the old name is gone).
- Import smoke command (from "Commands you will need") → `ok`.

### Step 3: Add the shared obstacle set and use it

In `sightline/announcer.py`, add this constant near the top (after the imports,
before `Detection` is fine):

```python
# COCO classes worth warning about as obstacles — things a walking user could
# collide with. This is the single source of truth; it is the UNION of the two
# sets that previously lived (and had drifted) in app.py and demos/05.
OBSTACLE_CLASSES = frozenset({
    "person", "chair", "bicycle", "car", "motorcycle", "bus", "truck", "dog",
    "potted plant", "couch", "dining table", "bench", "tv", "refrigerator",
    "fire hydrant",
})
```

**`app.py`**:
- Delete the `OBSTACLES = { ... }` block (lines 42-45). **Keep**
  `WARN_HEIGHT = 0.30` (line 46).
- Add `OBSTACLE_CLASSES` to the existing announcer import (line 38):
  `from sightline.announcer import pan_from_cx, estimate_distance_m, horizontal_phrase, OBSTACLE_CLASSES`.
- In `proximity_beep` change `if d.label in OBSTACLES` to
  `if d.label in OBSTACLE_CLASSES`.

**`demos/05_obstacle_alert.py`**:
- Delete the `DEFAULT_OBSTACLES = { ... }` block (lines 36-39). **Keep**
  `WARN_HEIGHT` and `SPEAK_HEIGHT` (lines 40-41).
- Add `OBSTACLE_CLASSES` to the announcer import (lines 29-31).
- Change line 52 from
  `obstacles = set(cfg["object_detection"].get("announce_classes") or []) or DEFAULT_OBSTACLES`
  to
  `obstacles = set(cfg["object_detection"].get("announce_classes") or []) or OBSTACLE_CLASSES`.

> **Intentional behavior change**: after this, `app.py` also warns on
> `fire hydrant`, and `demos/05` also warns on `tv`/`refrigerator`. This is the
> union and is desirable (one consistent list). If the maintainer specifically
> wanted these lists to differ, that contradicts this plan — STOP and report.

**Verify**:
- `grep -rn "DEFAULT_OBSTACLES" demos/ ` and `grep -n "OBSTACLES" app.py` show
  the old local names are gone and only `OBSTACLE_CLASSES` remains.
- `.venv/bin/python -m py_compile app.py demos/05_obstacle_alert.py` → exit 0.

### Step 4: Make `Preview.update` reuse `draw_detections`

In `sightline/viz.py`, replace the inline drawing loop inside `Preview.update`
with a call to the existing `draw_detections`. The new method body:

```python
    def update(self, frame, detections: Optional[Iterable] = None) -> bool:
        """Draw ``detections`` (objects with .box, .label, optional .confidence)
        on ``frame`` and show it. Returns True if the user pressed 'q'."""
        if not self._ok:
            return False
        try:
            img = frame.copy()
            draw_detections(img, detections)
            cv2.imshow(self.window, img)
            return (cv2.waitKey(1) & 0xFF) == ord("q")
        except cv2.error:
            # no GUI backend (headless) — disable and carry on
            self._ok = False
            return False
```

Note: `draw_detections` uses `tag = d.label if not conf else ...`, so a detection
with `confidence == 0.0` now renders with **no** number instead of `0.00`. This
is a cosmetic overlay-only change and matches what `app.py` already does (it
already uses `draw_detections`). If that is somehow unacceptable, STOP.

**Verify**: import smoke → `ok`; `.venv/bin/python -m py_compile sightline/viz.py` → exit 0.

### Step 5: Add tests

Create `tests/test_shared.py` (reuses plan 001's `conftest.py`):

```python
"""Tests for the consolidated shared helpers (plan 004)."""
from __future__ import annotations

import base64

import numpy as np
import pytest

from sightline.announcer import OBSTACLE_CLASSES

cv2 = pytest.importorskip("cv2")
from sightline.imaging import encode_jpeg  # noqa: E402  (after importorskip)


def test_obstacle_classes_is_the_union():
    expected = {
        "person", "chair", "bicycle", "car", "motorcycle", "bus", "truck", "dog",
        "potted plant", "couch", "dining table", "bench", "tv", "refrigerator",
        "fire hydrant",
    }
    assert set(OBSTACLE_CLASSES) == expected
    assert isinstance(OBSTACLE_CLASSES, frozenset)


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
```

**Verify**: `.venv/bin/python -m pytest -q tests/test_shared.py` → all pass
(or `skipped` only if cv2 is unavailable — but cv2 is a core dep, expect pass).

### Step 6: Run the full suite

**Verify**: `.venv/bin/python -m pytest -q` → all tests pass (plans 001–003 plus
these), exit 0.

## Test plan

- New file `tests/test_shared.py`: `OBSTACLE_CLASSES` equals the documented union
  and is a `frozenset`; `encode_jpeg` returns a base64 JPEG (SOI marker check),
  downscales to `max_edge`, and respects the `quality` parameter (higher quality
  → larger payload). cv2-dependent cases guarded with `importorskip`.
- Pattern: follows plan 001's test style; uses `tests/conftest.py`.

## Done criteria

ALL must hold:

- [ ] `grep -rn "_encode_jpeg" sightline/` → no matches.
- [ ] `grep -rn "DEFAULT_OBSTACLES" demos/` → no matches; `grep -n "OBSTACLES =" app.py` → no matches; both reference `OBSTACLE_CLASSES`.
- [ ] `Preview.update` in `sightline/viz.py` calls `draw_detections` (no inline
      `cv2.rectangle` loop remains in that method).
- [ ] `.venv/bin/python -m py_compile app.py demos/05_obstacle_alert.py sightline/*.py` exits 0.
- [ ] Import smoke command prints `ok`.
- [ ] `.venv/bin/python -m pytest -q` exits 0; `tests/test_shared.py` passes.
- [ ] Only the in-scope files were modified/created.
- [ ] `plans/README.md` status row for plan 004 updated to DONE.

## STOP conditions

Stop and report back (do not improvise) if:

- Any "Current state" excerpt does not match the live file.
- After removing `_encode_jpeg` from `scene.py`, `grep` shows `base64` or `cv2`
  is still referenced there (means scene uses them somewhere this plan didn't
  account for) — remove only the imports that are genuinely unused; if unsure,
  STOP.
- The maintainer's intent is that the two obstacle lists differ on purpose
  (contradicts the union in step 3).
- Any import smoke or `py_compile` fails after an edit and a single obvious fix
  doesn't resolve it.
- Plan 001's `tests/conftest.py` is missing: bootstrap it per plan 001 step 2,
  note it, then continue.

## Maintenance notes

- New obstacle classes go in `announcer.OBSTACLE_CLASSES` only; both `app.py`
  and `demos/05` pick them up automatically.
- All vision-model JPEG encoding now flows through `imaging.encode_jpeg`; change
  default quality/sizing there once, not in three files.
- **Deliberately deferred** (separate finding): `FaceIdentifier._load`
  (`faces.py`) vs `load_known` (`demos/02`) are still duplicated, and unknown
  faces are labeled `"unknown person"` in `faces.py` but `"unfamiliar person"`
  in `demos/02`/README. Unifying demo 2 onto `FaceIdentifier` would also force a
  label decision — handle it as its own change, not here.
- A reviewer should diff the JPEG quality at each call site (scene=85, ocr=90,
  vision=85) to confirm the consolidation preserved them, and confirm the
  obstacle union is the intended set.

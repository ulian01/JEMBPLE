# Plan 003: Make `Speaker` thread-safe (single audio owner, guarded process)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: this repository is **not** under version control,
> so there is no commit SHA. Before editing, open `sightline/speech.py` and
> confirm the quoted excerpts still match the live code. On any mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/001-test-baseline.md (test harness)
- **Category**: bug
- **Planned at**: no VCS (not a git repo) — snapshot 2026-06-12

## Why this matters

`Speaker` renders TTS by spawning a subprocess (`espeak` or `piper | aplay`) and
storing the handle in `self._proc`. Three different threads touch that single
handle with **no synchronization**:

1. the **worker thread** (`_run`) calls `_speak()` for every queued utterance;
2. the **main loop thread** calls `say_blocking()` → `_speak()` directly
   (e.g. `app.py`'s `respond()` and `_speak_chunk()`);
3. the **voice thread** calls `interrupt()` on wake-word barge-in
   (`app.py:_on_wake`).

Two consequences, both observed-in-design:
- If anything was queued via `say()` (e.g. the "Reading." filler in
  `_vision_cmd`, or the streamed scene description) while the main thread is in
  `say_blocking()`, **two render calls run concurrently**, each spawning its own
  audio process and each overwriting `self._proc`. The user hears two voices
  talking over each other, and `interrupt()` can only see/kill the last handle
  written.
- `interrupt()` reads `self._proc` then calls `.terminate()` — a TOCTOU window
  where the worker can replace `self._proc` in between. Barge-in ("SIGHT" to
  stop) — the *safety* affordance — can therefore terminate the wrong process or
  miss the live one.

The fix is small and contained: serialize all rendering through one lock so two
utterances never play at once, and guard every read/write of `self._proc` with a
second lock so `interrupt()`/`is_busy()` always act on the current handle. The
locks are ordered so they cannot deadlock (the render lock is held during the
blocking `wait()`; the proc lock is only ever taken briefly and never *while*
waiting on a process).

## Current state

`sightline/speech.py`. Relevant excerpts:

Constructor tail (`speech.py:54-59`):

```python
        self.engine = self._pick_engine(speech_cfg)
        self._q: "queue.PriorityQueue[_Utterance]" = queue.PriorityQueue()
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
```

`interrupt()` and `say_blocking()` (`speech.py:83-100`):

```python
    def interrupt(self) -> None:
        """Drop queued speech and kill the current utterance."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def say_blocking(self, text: str) -> None:
        """Speak synchronously — handy for one-shot tools (OCR / scene)."""
        self._speak(text.strip())

    def is_busy(self) -> bool:
        """True if speaking or anything is queued (used to mute beeps while talking)."""
        speaking = self._proc is not None and self._proc.poll() is None
        return speaking or not self._q.empty()
```

`_speak()` dispatch (`speech.py:141-150`):

```python
    def _speak(self, text: str) -> None:
        text = self._normalize(text)
        if not text:
            return
        if self.engine == "piper":
            self._speak_piper(text)
        elif self.engine == "espeak":
            self._speak_espeak(text)
        else:
            print(f"[TTS] {text}")
```

The two renderers that assign `self._proc` (`speech.py:152-179`):

```python
    def _speak_espeak(self, text: str) -> None:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        amp = str(int(max(0, min(200, self.volume * 100))))   # espeak amplitude 0-200
        cmd = [binary, "-s", str(self.rate), "-a", amp, text]
        self._proc = subprocess.Popen(cmd)
        self._proc.wait()

    def _speak_piper(self, text: str) -> None:
        # piper synthesises WAV on stdout; aplay renders it to the chosen device.
        # length-scale = speed (lower is faster); sentence-silence = pause on '.'.
        model = self.cfg["piper_model"]
        piper = subprocess.Popen(
            ["piper", "-m", model,
             "--length-scale", str(self.length_scale),
             "--sentence-silence", str(self.sentence_silence),
             "--volume", str(self.volume),
             "-f", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
        aplay = subprocess.Popen(
            ["aplay", "-D", self.device, "-q", "-"],
            stdin=piper.stdout,
        )
        self._proc = aplay
        piper.stdin.write(text.encode())
        piper.stdin.close()
        aplay.wait()
        piper.wait()
```

**Conventions to match**: `from __future__ import annotations` (already at top),
type hints, `threading` is already imported in this module (used for the worker
`Event` and `Thread`). Use `threading.Lock`.

## Commands you will need

| Purpose      | Command                                                | Expected on success |
|--------------|--------------------------------------------------------|---------------------|
| Syntax check | `.venv/bin/python -c "import ast; ast.parse(open('sightline/speech.py').read()); print('ok')"` | prints `ok` |
| Run tests    | `.venv/bin/python -m pytest -q tests/test_speech.py`   | all pass, exit 0 |
| Full suite   | `.venv/bin/python -m pytest -q`                        | all pass, exit 0 |

If `.venv/bin/python` is missing, substitute `python3` and note it.

## Scope

**In scope**:
- `sightline/speech.py` (add two locks; wrap `_speak` body; route `_proc`
  writes through a helper; guard `interrupt`/`is_busy` reads)
- `tests/test_speech.py` (create)

**Out of scope** (do NOT touch):
- The priority-queue design, `_Utterance`, `_pick_engine`, `_normalize`,
  `faster/slower/louder/quieter`, `close()`, and the public method signatures —
  callers (`app.py`, `main.py`, demos) depend on them. This change must be
  behavior-preserving for the single-threaded happy path.
- `app.py` / demos — they keep calling `say`, `say_blocking`, `interrupt`,
  `is_busy` exactly as today.

## Git workflow

Not a git repository. Do not init/commit/push. Just edit the files.

## Steps

### Step 1: Add the two locks in `__init__`

In the constructor tail (`speech.py:54-59`), add the locks alongside the existing
state. Change:

```python
        self._q: "queue.PriorityQueue[_Utterance]" = queue.PriorityQueue()
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
```

to:

```python
        self._q: "queue.PriorityQueue[_Utterance]" = queue.PriorityQueue()
        self._proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()   # guards reads/writes of self._proc
        self._speak_lock = threading.Lock()  # serializes rendering (one voice at a time)
        self._stop = threading.Event()
```

**Verify**: `ast.parse` ok (command above).

### Step 2: Route `self._proc` writes through a guarded helper

Add this helper method (place it right after `say_blocking`, or anywhere in the
class body):

```python
    def _set_proc(self, proc: "subprocess.Popen | None") -> None:
        with self._proc_lock:
            self._proc = proc
```

In `_speak_espeak`, replace `self._proc = subprocess.Popen(cmd)` + `self._proc.wait()`
with a local handle so the blocking `wait()` does **not** hold any lock:

```python
    def _speak_espeak(self, text: str) -> None:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        amp = str(int(max(0, min(200, self.volume * 100))))   # espeak amplitude 0-200
        cmd = [binary, "-s", str(self.rate), "-a", amp, text]
        proc = subprocess.Popen(cmd)
        self._set_proc(proc)
        proc.wait()
```

In `_speak_piper`, replace `self._proc = aplay` with `self._set_proc(aplay)`
(keep everything else identical; `aplay.wait()` / `piper.wait()` stay outside the
lock):

```python
        aplay = subprocess.Popen(
            ["aplay", "-D", self.device, "-q", "-"],
            stdin=piper.stdout,
        )
        self._set_proc(aplay)
        piper.stdin.write(text.encode())
        piper.stdin.close()
        aplay.wait()
        piper.wait()
```

**Verify**: `ast.parse` ok; `grep -n "self._proc =" sightline/speech.py` shows
the assignment **only** inside `_set_proc` (one match).

### Step 3: Serialize rendering in `_speak`

Wrap the engine dispatch in `_speak_lock` so two threads can never render
concurrently. Change `_speak` (`speech.py:141-150`) to:

```python
    def _speak(self, text: str) -> None:
        text = self._normalize(text)
        if not text:
            return
        with self._speak_lock:
            if self.engine == "piper":
                self._speak_piper(text)
            elif self.engine == "espeak":
                self._speak_espeak(text)
            else:
                print(f"[TTS] {text}")
```

Why this is deadlock-free: the render lock is held across the blocking
`proc.wait()`, but `interrupt()` (next step) takes only `_proc_lock` — never
`_speak_lock` — so it can always terminate the live process while a render is
blocked in `wait()`. No code path takes `_proc_lock` and then `_speak_lock`.

**Verify**: `ast.parse` ok.

### Step 4: Guard `_proc` reads in `interrupt()` and `is_busy()`

Change `interrupt()` so it snapshots `self._proc` under the lock, then acts on
the snapshot outside the lock:

```python
    def interrupt(self) -> None:
        """Drop queued speech and kill the current utterance."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        with self._proc_lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
```

Change `is_busy()` to read under the lock:

```python
    def is_busy(self) -> bool:
        """True if speaking or anything is queued (used to mute beeps while talking)."""
        with self._proc_lock:
            proc = self._proc
        speaking = proc is not None and proc.poll() is None
        return speaking or not self._q.empty()
```

**Verify**: `ast.parse` ok; full suite still imports speech cleanly:
`.venv/bin/python -c "import sys;sys.path.insert(0,'.'); from sightline.speech import Speaker; print('ok')"` → `ok`.

### Step 5: Add concurrency tests

Create `tests/test_speech.py`. These tests **never play real audio**: they force
`engine = "espeak"` and monkeypatch the `_speak_espeak` renderer with a fake that
uses a fake process, so the lock behavior is what's exercised. Reuses
`tests/conftest.py` from plan 001.

```python
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
```

**Verify**: `.venv/bin/python -m pytest -q tests/test_speech.py` → 3 passed.

### Step 6: Run the full suite

**Verify**: `.venv/bin/python -m pytest -q` → all tests pass (plans 001/002 plus
these 3), exit 0.

## Test plan

- New file `tests/test_speech.py`, 3 cases: (1) four concurrent `_speak()` calls
  never overlap (`active["max"] == 1`) — proves `_speak_lock` serializes
  rendering; (2) `interrupt()` from another thread terminates the process a
  render is blocked on (`FakeProc.wait()` returns) — proves the `_proc_lock`
  snapshot + barge-in path works; (3) `is_busy()` is False when idle.
- Pattern: the monkeypatch + fake-process style; uses plan 001's `conftest.py`.
- These are timing-tolerant (generous `join` timeouts, small sleeps) but not
  timing-*dependent* for correctness of the lock assertion.

## Done criteria

ALL must hold:

- [ ] `grep -n "self._proc =" sightline/speech.py` → exactly one match, inside
      `_set_proc`.
- [ ] `grep -n "_speak_lock\|_proc_lock" sightline/speech.py` shows both locks
      created in `__init__` and used in `_speak`, `interrupt`, `is_busy`.
- [ ] `.venv/bin/python -m pytest -q` exits 0; `tests/test_speech.py` has 3
      passing tests.
- [ ] Public method signatures (`say`, `say_blocking`, `interrupt`, `is_busy`,
      `faster/slower/louder/quieter`, `close`) are unchanged.
- [ ] Only `sightline/speech.py` and `tests/test_speech.py` modified/created.
- [ ] `plans/README.md` status row for plan 003 updated to DONE.

## STOP conditions

Stop and report back (do not improvise) if:

- The `speech.py` excerpts in "Current state" do not match the live file.
- Adding `_speak_lock` around the dispatch causes a test to hang (suggests a
  lock-ordering problem the plan didn't anticipate) — do not "fix" it by
  removing locks; report the hang.
- You find a fourth thread or call site that writes `self._proc` outside the two
  renderers — report it; the guarantee depends on `_set_proc` being the only
  writer.
- Plan 001's `tests/conftest.py` is missing: bootstrap it per plan 001 step 2,
  note it in your report, then continue.

## Maintenance notes

- The serialization makes `say_blocking()` wait for any in-progress worker
  utterance before starting — this is intended (no overlap) and matches how the
  main loop already blocks during speech. If a future caller needs truly
  fire-and-forget speech, it should use `say()` (queued), not `say_blocking()`.
- A reviewer should confirm no path acquires `_proc_lock` then `_speak_lock`
  (only the reverse-free ordering is safe), and that `proc.wait()` calls remain
  *outside* both locks.
- Follow-up deferred: `close()` currently enqueues a sentinel to unblock the
  worker; it does not interrupt an in-progress render. That is acceptable
  (shutdown speaks "Goodbye" then closes) and is out of scope here.

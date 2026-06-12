"""Text-to-speech output.

A background thread owns a priority queue so the main vision loop never blocks
on audio. Two engines are supported:

* **Piper** (recommended) — small neural TTS that runs comfortably on a Pi 5 and
  sounds far more natural than eSpeak. Set ``speech.piper_model`` to a ``.onnx``
  voice.
* **eSpeak-NG** — always-available fallback; robotic but zero-setup and very low
  latency.

High-priority utterances (e.g. obstacle warnings) flush anything queued so the
user hears the urgent thing first.
"""
from __future__ import annotations

import queue
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from itertools import count

# Sentence-ending punctuation at a word boundary (keeps "3.5" / "a.b" intact).
_SENTENCE_PUNCT = re.compile(r"\s*[.!?]+(\s+|$)")

_counter = count()


@dataclass(order=True)
class _Utterance:
    priority: int
    seq: int = field(compare=True)
    text: str = field(compare=False)


class Speaker:
    PRIORITY_HIGH = 0      # interrupts; for obstacle / safety alerts
    PRIORITY_NORMAL = 10   # routine announcements

    def __init__(self, speech_cfg: dict):
        self.cfg = speech_cfg
        self.device = speech_cfg.get("audio_device", "default")
        self.rate = int(speech_cfg.get("rate_wpm", 190))
        # Piper speed/pacing: length_scale < 1.0 is faster; sentence_silence is
        # the gap (seconds) after each sentence — lower it to stop pausing on '.'.
        self.length_scale = float(speech_cfg.get("piper_length_scale", 0.9))
        self.sentence_silence = float(speech_cfg.get("piper_sentence_silence", 0.05))
        self.volume = float(speech_cfg.get("volume", 1.0))
        # How a full stop should pause: "normal" keeps it a sentence stop (long),
        # "comma" makes '.'/'!'/'?' pause like a comma (short), "none" runs on.
        self.period_pause = str(speech_cfg.get("period_pause", "normal")).lower()
        self.engine = self._pick_engine(speech_cfg)
        self._q: "queue.PriorityQueue[_Utterance]" = queue.PriorityQueue()
        self._proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()   # guards reads/writes of self._proc
        self._speak_lock = threading.Lock()  # serializes rendering (one voice at a time)
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # -- engine selection -------------------------------------------------
    def _pick_engine(self, cfg: dict) -> str:
        requested = cfg.get("engine", "auto")
        have_piper = bool(cfg.get("piper_model")) and shutil.which("piper") is not None
        have_espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if requested == "piper" or (requested == "auto" and have_piper):
            if have_piper:
                return "piper"
        if have_espeak:
            return "espeak"
        # Last resort: print so the demo is still observable on a dev box.
        return "print"

    # -- public API -------------------------------------------------------
    def say(self, text: str, priority: int = PRIORITY_NORMAL) -> None:
        text = (text or "").strip()
        if not text:
            return
        if priority == self.PRIORITY_HIGH:
            self.interrupt()
        self._q.put(_Utterance(priority=priority, seq=next(_counter), text=text))

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

    def say_blocking(self, text: str) -> None:
        """Speak synchronously — handy for one-shot tools (OCR / scene)."""
        self._speak(text.strip())

    def _set_proc(self, proc: "subprocess.Popen | None") -> None:
        with self._proc_lock:
            self._proc = proc

    def is_busy(self) -> bool:
        """True if speaking or anything is queued (used to mute beeps while talking)."""
        with self._proc_lock:
            proc = self._proc
        speaking = proc is not None and proc.poll() is None
        return speaking or not self._q.empty()

    # -- runtime voice adjustments (driven by voice commands) -------------
    def faster(self) -> None:
        self.length_scale = max(0.4, round(self.length_scale * 0.85, 3))
        self.rate = min(400, self.rate + 25)

    def slower(self) -> None:
        self.length_scale = min(1.7, round(self.length_scale * 1.15, 3))
        self.rate = max(90, self.rate - 25)

    def louder(self) -> None:
        self.volume = min(2.0, round(self.volume + 0.2, 2))

    def quieter(self) -> None:
        self.volume = max(0.1, round(self.volume - 0.2, 2))

    def close(self) -> None:
        self._stop.set()
        self._q.put(_Utterance(priority=-1, seq=next(_counter), text=""))

    # -- worker -----------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._q.get()
            if self._stop.is_set():
                break
            if item.text:
                self._speak(item.text)

    def _normalize(self, text: str) -> str:
        """Optionally soften sentence-ending punctuation so '.' doesn't trigger a
        long sentence pause in the TTS prosody."""
        if self.period_pause == "comma":
            text = _SENTENCE_PUNCT.sub(", ", text)
        elif self.period_pause == "none":
            text = _SENTENCE_PUNCT.sub(" ", text)
        else:
            return text
        return text.strip().rstrip(",").strip()

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

    def _speak_espeak(self, text: str) -> None:
        binary = shutil.which("espeak-ng") or shutil.which("espeak")
        amp = str(int(max(0, min(200, self.volume * 100))))   # espeak amplitude 0-200
        cmd = [binary, "-s", str(self.rate), "-a", amp, text]
        proc = subprocess.Popen(cmd)
        self._set_proc(proc)
        proc.wait()

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
        self._set_proc(aplay)
        piper.stdin.write(text.encode())
        piper.stdin.close()
        aplay.wait()
        piper.wait()

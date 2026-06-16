"""Offline voice commands with a wake word.

Uses Vosk (a small, fully-offline streaming speech recogniser) with a constrained
grammar — it only listens for "<wakeword> <command>" phrases, which makes
recognition fast and accurate on a Pi/laptop CPU and avoids the cost and latency
of a large model. Whisper is more accurate on free-form speech, but it's heavy
for always-on listening; a fixed command grammar is the right tool here.

A background thread captures the mic and pushes recognised commands onto a queue
the main loop polls — nothing blocks the GUI.
"""
from __future__ import annotations

import json
import queue
import threading

# Canonical command set; synonyms (raw recognised word -> canonical command).
_SYNONYMS = {
    "read": "text", "reading": "text", "text": "text",
    "describe": "describe", "description": "describe", "scene": "describe",
    "face": "face", "identify": "face",
    "who": "who", "everyone": "who",
    "distance": "distance", "beeps": "distance", "beep": "distance",
    "stop": "stop", "quiet": "stop", "cancel": "stop",
    "repeat": "repeat", "again": "repeat",
    "faster": "faster", "quicker": "faster",
    "slower": "slower",
    "louder": "louder",
    "quieter": "quieter", "softer": "quieter",
    "help": "help", "commands": "help",
    "battery": "battery", "power": "battery",
    "time": "time", "date": "date",
    "spell": "spell",
    "money": "money", "cash": "money", "note": "money", "notes": "money",
    "label": "label", "ingredients": "label", "expiry": "label", "dosage": "label",
    "translate": "translate", "english": "translate",
    "barcode": "barcode", "scan": "barcode",
    "next": "next", "more": "next", "continue": "next",
    "remember": "remember", "enroll": "remember", "enrol": "remember", "save": "remember",
    "expression": "expression", "smiling": "expression", "mood": "expression",
    "looking": "expression", "feeling": "expression",
}


class VoiceCommands:
    def __init__(self, model_path: str, wakeword: str = "sight",
                 commands=None, samplerate: int = 16000, device=None, on_wake=None,
                 is_muted=None):
        try:
            import vosk
            import sounddevice  # noqa: F401  (imported for the clear error if missing)
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Voice commands need vosk + sounddevice. Run: tools/install_voice.sh"
            ) from e
        import sounddevice
        self._vosk = vosk
        self._sd = sounddevice
        vosk.SetLogLevel(-1)

        self.model = vosk.Model(model_path)
        self.samplerate = samplerate
        self.device = device
        self.wakeword = wakeword.lower()
        self.commands = set(commands or {"text", "describe", "face", "stop"})
        self._on_wake = on_wake     # called once, the instant the wake word is heard
        self._is_muted = is_muted   # callback to pause listening (e.g. while TTS plays)

        # Bias recognition to just the phrases we care about.
        words = sorted({self.wakeword} | self.commands | set(_SYNONYMS))
        phrases = [f"{self.wakeword} {w}" for w in words] + [self.wakeword, "[unk]"]
        self._grammar = json.dumps(phrases)

        self._audio_q: "queue.Queue[bytes]" = queue.Queue()
        self._cmd_q: "queue.Queue[str]" = queue.Queue()
        self._phrase_q: "queue.Queue[str]" = queue.Queue()  # free-dictation (names)
        self._capture = threading.Event()                   # in name-capture mode?
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- lifecycle --------------------------------------------------------
    def start(self) -> "VoiceCommands":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        # Join so the RawInputStream closes cleanly before the process exits;
        # otherwise PortAudio can abort during interpreter teardown.
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    # -- main-loop API ----------------------------------------------------
    def poll(self) -> str | None:
        """Return the next recognised command, or None. Never blocks."""
        try:
            return self._cmd_q.get_nowait()
        except queue.Empty:
            return None

    def capture_phrase(self, timeout: float = 6.0) -> str | None:
        """Switch to free-dictation for one utterance and return it (e.g. a name
        for enrolment). Blocks up to ``timeout`` seconds. Returns None on silence."""
        while not self._phrase_q.empty():
            self._phrase_q.get_nowait()
        self._capture.set()
        try:
            return self._phrase_q.get(timeout=timeout)
        except queue.Empty:
            return None
        finally:
            self._capture.clear()

    # -- worker -----------------------------------------------------------
    def _audio_cb(self, indata, frames, time_info, status):
        self._audio_q.put(bytes(indata))

    def _run(self) -> None:
        rec = self._vosk.KaldiRecognizer(self.model, self.samplerate, self._grammar)
        rec_free = self._vosk.KaldiRecognizer(self.model, self.samplerate)  # full vocab
        wake_fired = False     # chime once per utterance, the moment we hear "sight"
        capturing_prev = False
        with self._sd.RawInputStream(samplerate=self.samplerate, blocksize=8000,
                                     dtype="int16", channels=1, device=self.device,
                                     callback=self._audio_cb):
            while not self._stop.is_set():
                try:
                    data = self._audio_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                capturing = self._capture.is_set()
                if capturing != capturing_prev:
                    # reset both recognisers on mode switch so audio doesn't bleed
                    rec = self._vosk.KaldiRecognizer(self.model, self.samplerate, self._grammar)
                    rec_free = self._vosk.KaldiRecognizer(self.model, self.samplerate)
                    wake_fired = False
                    capturing_prev = capturing

                if self._is_muted is not None and self._is_muted():
                    # Drain the queue so audio doesn't lag when unmuted, but
                    # do not process it. This prevents the mic from picking up
                    # the speaker's TTS output and triggering false commands.
                    continue

                if capturing:
                    # free dictation: grab the next whole utterance as a phrase
                    if rec_free.AcceptWaveform(data):
                        text = json.loads(rec_free.Result()).get("text", "").strip()
                        if text:
                            self._phrase_q.put(text)
                    continue

                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get("text", "")
                    self._dispatch(text)
                    wake_fired = False
                elif not wake_fired and self._on_wake is not None:
                    partial = json.loads(rec.PartialResult()).get("partial", "")
                    words = partial.split()
                    if self.wakeword in words and len(words) > 1:
                        wake_fired = True
                        try:
                            self._on_wake()
                        except Exception:
                            pass

    def _dispatch(self, text: str) -> None:
        words = text.lower().split()
        if self.wakeword not in words:
            return
        i = words.index(self.wakeword)
        tail = words[i + 1:]
        if not tail:
            return
        cmd = _SYNONYMS.get(tail[0], tail[0])
        if cmd in self.commands:
            self._cmd_q.put(cmd)

"""Non-speech spatial audio earcons.

Speech is slow and serial; a quick stereo beep conveys *direction* and
*proximity* almost instantly and is the right channel for fast feedback (an
approaching obstacle, "something is to your left"). We encode:

* **Direction** as stereo panning — an object on the left is louder in the left
  ear (requires stereo output; on a mono speaker the pan is inaudible but the
  tone still fires).
* **Proximity** as pitch and repetition rate — closer => higher and faster,
  like a parking sensor.

Playback uses ``sounddevice`` when available (lowest latency) and otherwise
shells out to ``aplay`` with a temporary WAV, so it works on a bare Pi OS image.
"""
from __future__ import annotations

import struct
import subprocess
import tempfile
import wave

import numpy as np

try:
    import sounddevice as sd
    _HAVE_SD = True
except Exception:
    _HAVE_SD = False


class AudioCues:
    def __init__(self, cfg: dict, device: str = "default", backend: str = "auto"):
        self.enabled = bool(cfg.get("enabled", True))
        self.sr = int(cfg.get("sample_rate", 22050))
        self.max_distance = float(cfg.get("max_distance_m", 4.0))
        self.device = device
        # Use sounddevice (low latency) only when nothing else holds PortAudio.
        # When a mic capture stream is open (the voice app), force aplay — mixing
        # transient PortAudio output streams with an open input stream crashes the
        # ALSA backend (free(): invalid pointer).
        backend = backend or cfg.get("backend", "auto")
        self.use_sd = _HAVE_SD and backend in ("auto", "sounddevice")

    def _tone(self, freq: float, dur: float, pan: float, volume: float) -> np.ndarray:
        """Return an (N, 2) float32 stereo buffer.

        ``pan`` in [-1, 1]: -1 full left, 0 centre, +1 full right.
        """
        t = np.linspace(0, dur, int(self.sr * dur), endpoint=False)
        wave_mono = np.sin(2 * np.pi * freq * t)
        # short attack/release envelope to avoid clicks
        env = np.ones_like(wave_mono)
        ramp = max(1, int(0.01 * self.sr))
        env[:ramp] = np.linspace(0, 1, ramp)
        env[-ramp:] = np.linspace(1, 0, ramp)
        wave_mono *= env * volume
        left = wave_mono * np.sqrt((1 - pan) / 2)
        right = wave_mono * np.sqrt((1 + pan) / 2)
        return np.stack([left, right], axis=1).astype(np.float32)

    def ping(self, pan: float = 0.0, distance_m: float | None = None, volume: float = 0.6) -> None:
        """Play one directional ping.

        ``pan`` is the horizontal position of the object (-1 left .. +1 right);
        ``distance_m`` maps to pitch (closer => higher).
        """
        if not self.enabled:
            return
        pan = float(np.clip(pan, -1.0, 1.0))
        if distance_m is None:
            freq = 660.0
        else:
            d = float(np.clip(distance_m, 0.2, self.max_distance))
            # 1200 Hz when very close, 350 Hz at max distance
            ratio = 1 - (d / self.max_distance)
            freq = 350 + ratio * 850
        buf = self._tone(freq, 0.12, pan, volume)
        self._play(buf)

    def obstacle(self, pan: float, distance_m: float, volume: float = 0.25) -> None:
        """A low, quiet proximity beep — bassier and softer than the cue ping.

        Pitch rises a little as things get closer but stays in a low register;
        ``volume`` defaults low so it sits under speech.
        """
        if not self.enabled:
            return
        d = float(np.clip(distance_m, 0.2, self.max_distance))
        ratio = 1 - (d / self.max_distance)
        freq = 130 + ratio * 200          # 130 Hz (far) .. 330 Hz (close), low/bassy
        self._play(self._tone(freq, 0.10, float(np.clip(pan, -1, 1)), volume))

    def chime(self, volume: float = 0.5) -> None:
        """A short rising two-note 'listening' cue for the wake word."""
        if not self.enabled:
            return
        for freq in (784.0, 1175.0):   # G5 -> D6, quick and pleasant
            self._play(self._tone(freq, 0.08, pan=0.0, volume=volume))

    def proximity_sweep(self, pan: float, distance_m: float, volume: float = 0.6) -> None:
        """A faster cadence cue: number of pips grows as distance shrinks."""
        if not self.enabled:
            return
        d = float(np.clip(distance_m, 0.2, self.max_distance))
        pips = 1 + int((1 - d / self.max_distance) * 3)  # 1..4 pips
        for _ in range(pips):
            self.ping(pan=pan, distance_m=d, volume=volume)

    def _play(self, buf: np.ndarray) -> None:
        if self.use_sd:
            try:
                sd.play(buf, self.sr, blocking=True)
                return
            except Exception:
                pass  # fall through to aplay
        self._play_aplay(buf)

    def _play_aplay(self, buf: np.ndarray) -> None:
        pcm = (np.clip(buf, -1, 1) * 32767).astype("<i2")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(self.sr)
                wf.writeframes(pcm.tobytes())
            subprocess.run(["aplay", "-D", self.device, "-q", tmp.name], check=False)

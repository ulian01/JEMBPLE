#!/usr/bin/env python3
"""Sightline — production app (voice-controlled assistive vision).

Always-on. Combines object detection + distance beeps with a wake-word voice
interface. Say the wake word "SIGHT" then a command:

  Reading / world:   text · next · spell · money · label · translate · barcode
  Scene / people:    describe · face · who · remember · expression
  Comfort / control: repeat · faster · slower · louder · quieter · stop
  Status:            help · battery · time · date
  Toggles:           distance        (low proximity beeps; off by default)

Saying "SIGHT" also barges in — it stops whatever it's currently saying.

Run:
    export SIGHTLINE_CONFIG=config.laptop.yaml
    export ANTHROPIC_API_KEY=sk-ant-...
    python app.py
"""
from __future__ import annotations

import datetime
import os
import re
import sys
import time
from pathlib import Path

# Silence OpenCV's bundled-Qt "cannot find font directory" warnings (cosmetic).
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sightline import config
from sightline.camera import Camera
from sightline.speech import Speaker
from sightline.audio_cues import AudioCues
from sightline.announcer import pan_from_cx, estimate_distance_m, horizontal_phrase, OBSTACLE_CLASSES
from sightline.viz import CaptureWindow, draw_detections
from sightline import detector

WARN_HEIGHT = 0.30

# Commands handled by clicking a button (the rest are voice-only).
BUTTON_ACTIONS = {"text", "describe", "face", "distance", "help"}

HELP_TEXT = (
    "Say sight, then a command. Reading: text, next, spell, money, label, "
    "translate, barcode. Scene and people: describe, face, who, remember, "
    "expression. Control: repeat, faster, slower, louder, quieter, stop. "
    "Status: battery, time, date. And distance to toggle proximity beeps."
)


def chunk_text(text: str, n: int) -> list[str]:
    """Split text into <= n-char chunks at sentence/word boundaries for paging."""
    text = " ".join(text.split())
    if len(text) <= n:
        return [text] if text else []
    chunks, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        while len(sent) > n:                 # a single very long run
            chunks.append(sent[:n]); sent = sent[n:]
        if not cur:
            cur = sent
        elif len(cur) + 1 + len(sent) <= n:
            cur += " " + sent
        else:
            chunks.append(cur); cur = sent
    if cur:
        chunks.append(cur)
    return chunks


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.speaker = Speaker(cfg["speech"])
        # aplay backend: the voice mic holds PortAudio capture; concurrent
        # sounddevice output would crash the ALSA backend.
        self.cues = AudioCues(cfg["audio_cues"],
                              device=cfg["speech"]["audio_device"], backend="aplay")
        self.max_d = cfg["audio_cues"]["max_distance_m"]
        self.beeps = bool(cfg["app"].get("beeps", False))
        self.beep_volume = float(cfg["app"].get("beep_volume", 0.25))
        self.detect_interval = max(1, int(cfg["app"]["detect_interval"]))
        self.read_chunk_chars = int(cfg["app"].get("read_chunk_chars", 240))

        self.win = CaptureWindow("Sightline", buttons=[
            ("TEXT", "text", [ord("t")]),
            ("DESCRIBE", "describe", [ord("d")]),
            ("FACE", "face", [ord("f")]),
            ("DISTANCE", "distance", [ord("b")]),
            ("HELP", "help", [ord("h")]),
        ])

        self.det = detector.build(cfg["object_detection"])
        model = cfg["scene"]["model"]
        self.ocr = self._try("OCR", lambda: __import__(
            "sightline.ocr", fromlist=["OcrReader"]).OcrReader(cfg["ocr"]))
        self.describer = self._try("Scene description", lambda: __import__(
            "sightline.scene", fromlist=["SceneDescriber"]).SceneDescriber(cfg["scene"]))
        self.faces = self._try("Face recognition", lambda: __import__(
            "sightline.faces", fromlist=["FaceIdentifier"]).FaceIdentifier(cfg["faces"]))
        self.vision = self._try("Vision assistant", lambda: __import__(
            "sightline.vision", fromlist=["VisionAssistant"]).VisionAssistant(model=model))

        self.voice = self._build_voice(cfg)

        self._frame_idx = 0
        self._detections = []
        self._last_beep = 0.0
        self._last_response = ""
        self._last_ocr = ""
        self._read_chunks: list[str] = []
        self._read_idx = 0
        self._idle_status = "Say: SIGHT help"

    def _try(self, name, factory):
        try:
            obj = factory()
            print(f"{name}: ready")
            return obj
        except Exception as e:
            print(f"{name}: unavailable ({e})")
            return None

    def _on_wake(self):
        self.speaker.interrupt()   # barge-in: stop talking the moment we hear "sight"
        self.cues.chime()

    def _build_voice(self, cfg):
        vcfg = cfg["voice"]
        if not vcfg.get("enabled") or not vcfg.get("model"):
            print("Voice: disabled (no model set) — use the buttons / keys.")
            return None
        try:
            from sightline.listen import VoiceCommands
            commands = {
                "text", "next", "spell", "money", "label", "translate", "barcode",
                "describe", "face", "who", "remember", "expression",
                "repeat", "faster", "slower", "louder", "quieter", "stop",
                "help", "battery", "time", "date", "distance",
            }
            v = VoiceCommands(
                model_path=config.resolve_path(vcfg["model"]).as_posix(),
                wakeword=vcfg.get("wakeword", "sight"),
                commands=commands,
                samplerate=int(vcfg.get("samplerate", 16000)),
                device=vcfg.get("device"),
                on_wake=self._on_wake,
            ).start()
            print(f"Voice: listening for '{vcfg.get('wakeword','sight')} ...'")
            return v
        except Exception as e:
            print(f"Voice: unavailable ({e}) — use the buttons / keys.")
            return None

    # -- response helper --------------------------------------------------
    def respond(self, text: str, *, remember=True):
        text = (text or "").strip()
        if remember:
            self._last_response = text
        self.win.set_text(text)
        self.win.set_status(self._idle_status)
        self.speaker.say_blocking(text)

    def _vision_cmd(self, frame, fn, filler, status):
        if self.vision is None:
            self.respond("The vision service is unavailable. Set your A.P.I. key.")
            return
        self.win.set_status(status); self.win.show(frame)
        self.speaker.say(filler)
        try:
            text = fn(frame)
        except Exception as e:
            print(f"Vision error: {e}", file=sys.stderr)
            text = "Sorry, that didn't work."
        self.respond(text)

    # -- command handlers (cmd_<action>) ----------------------------------
    def cmd_text(self, frame):
        if self.ocr is None:
            self.respond("Text reading is unavailable."); return
        self.win.set_status("Reading…"); self.win.show(frame)
        self.speaker.say("Reading.")
        try:
            text = self.ocr.read(frame)
        except Exception as e:
            print(f"OCR error: {e}", file=sys.stderr); text = ""
        self._last_ocr = text
        if len(text.strip()) < self.cfg["ocr"]["min_chars"]:
            self.respond("No readable text found."); return
        self._read_chunks = chunk_text(text, self.read_chunk_chars)
        self._read_idx = 0
        self._speak_chunk()

    def _speak_chunk(self):
        chunk = self._read_chunks[self._read_idx]
        more = self._read_idx < len(self._read_chunks) - 1
        self._last_response = chunk
        self.win.set_text(chunk + ("\n[ say SIGHT next ]" if more else ""))
        self.win.set_status(self._idle_status)
        self.speaker.say_blocking(chunk)
        if more:
            self.speaker.say("Say next to continue.")

    def cmd_next(self, frame=None):
        if not self._read_chunks or self._read_idx >= len(self._read_chunks) - 1:
            self.respond("No more text."); return
        self._read_idx += 1
        self._speak_chunk()

    def cmd_spell(self, frame=None):
        src = (self._last_ocr or self._last_response).strip()
        if not src:
            self.respond("There's nothing to spell."); return
        src = src[:120]
        letters = [c.upper() if c.isalnum() else "space" for c in src if c.isalnum() or c == " "]
        self.win.set_text("Spelling: " + src)
        self._last_response = "Spelling " + src
        self.speaker.say_blocking(", ".join(letters))

    def cmd_describe(self, frame):
        if self.describer is None:
            self.respond("Scene description is unavailable."); return
        self.win.set_status("Describing…"); self.win.show(frame)
        self.speaker.say("Looking.")
        try:
            full = self.describer.describe(
                frame, speaker=self.speaker,
                on_update=lambda t: (self.win.set_text(t), self.win.show(frame)))
            self._last_response = full
        except Exception as e:
            print(f"Scene error: {e}", file=sys.stderr)
            self.respond("Description failed.")

    def cmd_face(self, frame):
        if self.faces is None:
            self.respond("Face recognition is unavailable."); return
        self.win.set_status("Checking face…"); self.win.show(frame)
        face = self.faces.best(frame)
        if face is None:
            self.respond("No face in view.")
        elif face.label == "unknown person":
            self.respond("I don't recognise this person.")
        else:
            self.respond(f"That's {face.label}, {horizontal_phrase(face.cx)}.")

    def cmd_who(self, frame):
        if self.faces is None:
            self.respond("Face recognition is unavailable."); return
        self.win.set_status("Looking…"); self.win.show(frame)
        faces = self.faces.identify(frame)
        if not faces:
            self.respond("I don't see anyone."); return
        known = [f.label for f in faces if f.label != "unknown person"]
        unknown = len(faces) - len(known)
        parts = []
        if known:
            parts.append(", ".join(known))
        if unknown:
            parts.append(f"{unknown} unrecognised " + ("person" if unknown == 1 else "people"))
        self.respond("I can see " + " and ".join(parts) + ".")

    def cmd_remember(self, frame):
        if self.faces is None:
            self.respond("Face recognition is unavailable."); return
        if not self.faces.identify(frame):
            self.respond("No face to remember. Point the camera at the person."); return
        if self.voice is None:
            self.respond("Voice name capture is unavailable."); return
        self.speaker.say_blocking("Who is this? Say their name after the tone.")
        self.cues.chime()
        name = self.voice.capture_phrase(timeout=6.0)
        if not name:
            self.respond("I didn't catch the name. Try again."); return
        name = name.strip().title()
        try:
            self.faces.enroll(frame, name)
            self.respond(f"Saved {name}.")
        except Exception as e:
            print(f"Enroll error: {e}", file=sys.stderr)
            self.respond("I couldn't save that face. Make sure only one face is visible.")

    def cmd_money(self, frame):
        self._vision_cmd(frame, self.vision.money if self.vision else None,
                         "Checking money.", "Money…")

    def cmd_label(self, frame):
        self._vision_cmd(frame, self.vision.label if self.vision else None,
                         "Reading label.", "Label…")

    def cmd_translate(self, frame):
        self._vision_cmd(frame, self.vision.translate if self.vision else None,
                         "Translating.", "Translate…")

    def cmd_expression(self, frame):
        self._vision_cmd(frame, self.vision.expression if self.vision else None,
                         "Looking.", "Expression…")

    def cmd_barcode(self, frame):
        from sightline import barcode
        self.win.set_status("Scanning…"); self.win.show(frame)
        self.speaker.say("Scanning.")
        self.respond(barcode.read(frame))

    def cmd_repeat(self, frame=None):
        if not self._last_response:
            self.respond("Nothing to repeat."); return
        self.win.set_text(self._last_response)
        self.speaker.say_blocking(self._last_response)

    def cmd_faster(self, frame=None):
        self.speaker.faster(); self.speaker.say_blocking("Faster.")

    def cmd_slower(self, frame=None):
        self.speaker.slower(); self.speaker.say_blocking("Slower.")

    def cmd_louder(self, frame=None):
        self.speaker.louder(); self.speaker.say_blocking("Louder.")

    def cmd_quieter(self, frame=None):
        self.speaker.quieter(); self.speaker.say_blocking("Quieter.")

    def cmd_help(self, frame=None):
        self.respond(HELP_TEXT)

    def cmd_battery(self, frame=None):
        from sightline.sysinfo import battery_phrase
        self.respond(battery_phrase())

    def cmd_time(self, frame=None):
        self.respond(datetime.datetime.now().strftime("It's %I:%M %p.").replace(" 0", " "))

    def cmd_date(self, frame=None):
        self.respond(datetime.datetime.now().strftime("Today is %A, %B %d.").replace(" 0", " "))

    def cmd_distance(self, frame=None):
        self.beeps = not self.beeps
        self.speaker.say_blocking("Distance on." if self.beeps else "Distance off.")

    # -- dispatch ---------------------------------------------------------
    def dispatch(self, action, frame, source="voice"):
        if action == "stop":
            self.speaker.interrupt(); return
        if source == "button":
            self.cues.ping()
        method = getattr(self, f"cmd_{action}", None)
        if method:
            try:
                method(frame)
            except Exception as e:
                print(f"cmd {action} error: {e}", file=sys.stderr)
        self.win.set_status(self._idle_status)

    # -- continuous background --------------------------------------------
    def update_detections(self, frame):
        self._frame_idx += 1
        if self._frame_idx % self.detect_interval == 0:
            try:
                self._detections = self.det.detect(frame)
            except Exception as e:
                print(f"Detection error: {e}", file=sys.stderr)
        return self._detections

    def proximity_beep(self):
        if not self.beeps or self.speaker.is_busy():
            return
        obstacles = [d for d in self._detections if d.label in OBSTACLE_CLASSES]
        if not obstacles:
            return
        nearest = max(obstacles, key=lambda d: d.height)
        if nearest.height < WARN_HEIGHT:
            return
        dist = estimate_distance_m(nearest.height, self.max_d)
        now = time.monotonic()
        interval = 0.2 + 0.6 * (dist / self.max_d)
        if now - self._last_beep >= interval:
            self.cues.obstacle(pan=pan_from_cx(nearest.cx), distance_m=dist,
                               volume=self.beep_volume)
            self._last_beep = now

    # -- main loop --------------------------------------------------------
    def run(self):
        self.speaker.say("Sightline ready. Say sight help for commands.")
        self.win.set_status(self._idle_status)
        try:
            with Camera(self.cfg["camera"]) as cam:
                while True:
                    frame = cam.read()
                    detections = self.update_detections(frame)
                    self.proximity_beep()

                    display = frame.copy()
                    draw_detections(display, detections)
                    action = self.win.show(display)
                    if action == "quit":
                        break

                    voice_cmd = self.voice.poll() if self.voice else None
                    if voice_cmd:
                        self.dispatch(voice_cmd, frame, source="voice")
                    elif action in BUTTON_ACTIONS:
                        self.dispatch(action, frame, source="button")
                    time.sleep(0.01)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            if self.voice:
                self.voice.stop()
            self.win.close()
            self.speaker.say_blocking("Goodbye.")
            self.speaker.close()


def main():
    App(config.load()).run()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Demo 3 — Read text aloud (OCR).

Point the camera at a sign, a letter, a medicine label, or a menu and the device
reads any text it finds. This is an *on-demand* tool: it captures one frame when
triggered, reads it with the most accurate OCR backend available (a vision model
by default — see sightline/ocr.py), and speaks the result.

    python3 demos/03_text_reader.py
A live camera window opens — press SPACE to read the text in view, Q to quit.
(Headless, e.g. on the Pi: press Enter to read, Ctrl-C to quit.)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sightline import config
from sightline.camera import Camera
from sightline.speech import Speaker
from sightline.viz import CaptureWindow
from sightline.ocr import OcrReader
from sightline.scene import SceneDescriber


def main() -> None:
    cfg = config.load()
    speaker = Speaker(cfg["speech"])
    win = CaptureWindow("Sightline - Text reader", buttons=[
        ("READ TEXT", "capture", [ord(" "), ord("r"), 13, 10]),
        ("DESCRIBE", "describe", [ord("d")]),
    ])

    try:
        reader = OcrReader(cfg["ocr"])
    except Exception as e:
        print(e)
        return
    print(f"OCR backend: {reader.backend}")
    min_chars = cfg["ocr"]["min_chars"]

    # Scene description is optional here (needs the API key); build it lazily.
    describer = None
    try:
        describer = SceneDescriber(cfg["scene"])
    except Exception as e:
        print(f"Scene description unavailable: {e}")

    speaker.say("Text reader ready. Read text, or describe surroundings.")

    try:
        with Camera(cfg["camera"]) as cam:
            # Read every loop so the camera stays live (fresh frames, no stall);
            # the window pumps events and turns a key/click into an action.
            while True:
                frame = cam.read()
                action = win.show(frame)
                if action == "quit":
                    break

                if action == "capture":
                    win.set_status("Reading…")
                    win.show(frame)            # repaint so the status is visible
                    speaker.say("Reading.")
                    try:
                        text = reader.read(frame)
                    except Exception as e:
                        text = ""
                        print(f"OCR error: {e}", file=sys.stderr)
                    if len(text.strip()) < min_chars:
                        text = "No readable text found."
                    win.set_text(text)
                    win.set_status("")
                    speaker.say_blocking(text)

                elif action == "describe":
                    if describer is None:
                        speaker.say_blocking("Scene description is unavailable.")
                        win.set_text("Scene description unavailable (no API key).")
                    else:
                        win.set_status("Describing…")
                        win.show(frame)
                        try:
                            describer.describe(
                                frame, speaker=speaker,
                                on_update=lambda t: (win.set_text(t), win.show(frame)),
                            )
                        except Exception as e:
                            speaker.say_blocking("Description failed.")
                            print(f"Scene error: {e}", file=sys.stderr)
                        win.set_status("")
                time.sleep(0.02)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        win.close()
        speaker.close()


if __name__ == "__main__":
    main()

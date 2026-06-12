#!/usr/bin/env python3
"""Demo 4 — Rich scene description via a vision-language model (off-device).

On-device detection tells you *what* discrete objects are present. A VLM tells
you what's actually *going on*. By default this uses the terse "succinct" style
(short telegraphic fragments — quick to hear and cheap); set scene.style: full in
config for 2-4 natural sentences instead.

Setup:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 demos/04_scene_describer.py
A live camera window opens — press SPACE (or click DESCRIBE) to describe, Q to quit.
(Headless, e.g. on the Pi: press Enter to describe, Ctrl-C to quit.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sightline import config
from sightline.camera import Camera
from sightline.speech import Speaker
from sightline.viz import CaptureWindow
from sightline.scene import SceneDescriber


def main() -> None:
    cfg = config.load()
    speaker = Speaker(cfg["speech"])
    win = CaptureWindow("Sightline - Scene describer", buttons=[
        ("DESCRIBE", "capture", [ord(" "), ord("d"), 13, 10]),
    ])

    try:
        describer = SceneDescriber(cfg["scene"])
    except Exception as e:
        print(e)
        return
    print(f"Scene style: {describer.style}, model: {describer.model}")
    speaker.say("Scene describer ready. Press space to describe your surroundings.")

    try:
        with Camera(cfg["camera"]) as cam:
            import time
            # Keep the camera live each loop; the window turns a key/click into a capture.
            while True:
                frame = cam.read()
                action = win.show(frame)
                if action == "quit":
                    break
                if action == "capture":
                    win.set_status("Describing…")
                    win.show(frame)            # repaint before the (blocking) call
                    speaker.say("Looking.")
                    try:
                        describer.describe(
                            frame, speaker=speaker,
                            on_update=lambda t: (win.set_text(t), win.show(frame)),
                        )
                    except Exception as e:
                        win.set_text("Service unavailable.")
                        speaker.say_blocking("Sorry, the description service is unavailable.")
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

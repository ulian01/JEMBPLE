#!/usr/bin/env python3
"""Enrolment helper for the face recogniser.

Captures a face from the Pi Camera and saves it as ``known_faces/<name>.jpg``.
Speak/announce guidance is included so a blind user can enrol someone with a
sighted helper, or enrol themselves with verbal prompts.

    python3 demos/enroll_face.py "Mum"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from sightline import config
from sightline.camera import Camera
from sightline.speech import Speaker

try:
    import face_recognition
except Exception:
    face_recognition = None


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: enroll_face.py "Person Name"')
        return
    if face_recognition is None:
        print("face_recognition not installed. Run: pip install face_recognition")
        return

    name = sys.argv[1]
    cfg = config.load()
    speaker = Speaker(cfg["speech"])
    known_dir = config.resolve_path(cfg["faces"]["known_dir"])
    known_dir.mkdir(parents=True, exist_ok=True)

    speaker.say_blocking(f"Enrolling {name}. Please face the camera.")
    time.sleep(1.0)

    with Camera(cfg["camera"]) as cam:
        # Try for a few seconds to capture a frame with exactly one clear face.
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            frame = cam.read()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb, model=cfg["faces"]["model"])
            if len(locs) == 1:
                out = known_dir / f"{name.replace(' ', '_')}.jpg"
                cv2.imwrite(str(out), frame)
                speaker.say_blocking(f"Saved {name}.")
                print(f"Saved {out}")
                break
            elif len(locs) > 1:
                speaker.say("I see more than one face. Only one person please.")
                time.sleep(1.5)
            else:
                time.sleep(0.3)
        else:
            speaker.say_blocking("Could not capture a clear face. Please try again.")

    speaker.close()


if __name__ == "__main__":
    main()

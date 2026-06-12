#!/usr/bin/env python3
"""Demo 2 — Face detection & recognition.

Announces when a face appears and, if it matches someone the user has enrolled,
names them: "I see Mum, ahead". Unknown faces are announced as "an unfamiliar
person". Enrol people first with ``demos/enroll_face.py``.

Uses the ``face_recognition`` library (dlib). On a Pi 5, run it on every Nth
frame and at a reduced resolution to keep it responsive — both are configurable.

Run on the Pi:
    python3 demos/02_face_recognizer.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sightline import config
from sightline.camera import Camera
from sightline.speech import Speaker
from sightline.audio_cues import AudioCues
from sightline.announcer import Announcer, Detection, pan_from_cx, horizontal_phrase
from sightline.viz import Preview

try:
    import face_recognition
except Exception:
    face_recognition = None

import cv2

DOWNSCALE = 0.5          # process at half resolution for speed
PROCESS_EVERY = 3        # only run recognition every N frames


def load_known(faces_cfg: dict):
    """Return (encodings, names) loaded from the known-faces directory."""
    known_dir = config.resolve_path(faces_cfg["known_dir"])
    encs, names = [], []
    if not known_dir.is_dir():
        return encs, names
    for img_path in sorted(known_dir.glob("*")):
        if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        image = face_recognition.load_image_file(str(img_path))
        found = face_recognition.face_encodings(image)
        if found:
            encs.append(found[0])
            names.append(img_path.stem.replace("_", " "))
    return encs, names


def main() -> None:
    if face_recognition is None:
        print("face_recognition is not installed. Run: pip install face_recognition")
        return

    cfg = config.load()
    faces_cfg = cfg["faces"]
    speaker = Speaker(cfg["speech"])
    cues = AudioCues(cfg["audio_cues"], device=cfg["speech"]["audio_device"])
    announcer = Announcer(cfg["announcer"])

    known_encs, known_names = load_known(faces_cfg)
    preview = Preview(cfg["display"], "Face recognition")
    speaker.say(f"Face recognition ready. {len(known_names)} people enrolled.")

    frame_idx = 0
    faces: list[Detection] = []   # kept across skipped frames for a steady preview
    try:
        with Camera(cfg["camera"]) as cam:
            while True:
                frame = cam.read()
                frame_idx += 1
                if frame_idx % PROCESS_EVERY != 0:
                    if preview.update(frame, faces):
                        break
                    time.sleep(0.02)
                    continue

                small = cv2.resize(frame, (0, 0), fx=DOWNSCALE, fy=DOWNSCALE)
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locations = face_recognition.face_locations(rgb, model=faces_cfg["model"])
                encodings = face_recognition.face_encodings(rgb, locations)

                h, w = small.shape[:2]
                faces = []
                for (top, right, bottom, left), enc in zip(locations, encodings):
                    name = "unfamiliar person"
                    if known_encs:
                        dists = face_recognition.face_distance(known_encs, enc)
                        best = int(np.argmin(dists))
                        if dists[best] <= faces_cfg["tolerance"]:
                            name = known_names[best]

                    # normalised box (small-frame dims == normalised in full frame)
                    faces.append(Detection(name, 1.0, (left / w, top / h, right / w, bottom / h)))
                    cx = ((left + right) / 2) / w
                    if announcer.should_announce(f"face:{name}", 1.0):
                        cues.ping(pan=pan_from_cx(cx))
                        if name == "unfamiliar person":
                            speaker.say(f"An unfamiliar person, {horizontal_phrase(cx)}.")
                        else:
                            speaker.say(f"I see {name}, {horizontal_phrase(cx)}.")
                if preview.update(frame, faces):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        preview.close()
        speaker.say_blocking("Stopping face recognition.")
        speaker.close()


if __name__ == "__main__":
    main()

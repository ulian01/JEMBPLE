#!/usr/bin/env python3
"""Demo 1 — Real-time object detection with spoken, spatialised announcements.

Continuously detects COCO objects from the Pi Camera and tells the user what is
around them and roughly where: "a person, to your left, close". A short stereo
ping fires first (instant directional hint), then the spoken phrase. Repeats of
the same object are throttled so it doesn't chatter.

Run on the Pi:
    python3 demos/01_object_detector.py
Press Ctrl-C to stop.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sightline import config
from sightline.camera import Camera
from sightline.speech import Speaker
from sightline.audio_cues import AudioCues
from sightline.announcer import Announcer, pan_from_cx
from sightline import detector
from sightline.viz import Preview


def main() -> None:
    cfg = config.load()
    speaker = Speaker(cfg["speech"])
    cues = AudioCues(cfg["audio_cues"], device=cfg["speech"]["audio_device"])
    announcer = Announcer(cfg["announcer"])
    preview = Preview(cfg["display"], "Object detection")

    print("Loading detector…")
    det = detector.build(cfg["object_detection"])
    speaker.say("Object detection ready.")

    try:
        with Camera(cfg["camera"]) as cam:
            while True:
                frame = cam.read()
                detections = det.detect(frame)
                # Announce the most confident new object this frame, so we don't
                # talk over ourselves. Others will surface on later frames.
                detections.sort(key=lambda d: d.confidence, reverse=True)
                for d in detections:
                    if announcer.should_announce(d.label, d.confidence):
                        cues.ping(pan=pan_from_cx(d.cx), distance_m=None)
                        speaker.say(announcer.phrase(d))
                        break
                if preview.update(frame, detections):
                    break
                time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        preview.close()
        speaker.say_blocking("Stopping object detection.")
        speaker.close()


if __name__ == "__main__":
    main()

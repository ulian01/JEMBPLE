#!/usr/bin/env python3
"""Demo 5 — Obstacle proximity alerts (safety-first, low-latency).

This is the "watch where you're walking" mode. It tracks a few obstacle-relevant
COCO classes (person, chair, etc.) and warns with an escalating parking-sensor
earcon as something fills more of the frame — i.e. gets closer. Audio cues, not
speech, are the primary channel here because they're near-instant and don't
block; a spoken word ("person, close!") is only added when an object gets very
near.

Distance is estimated monocularly from bounding-box size — a genuine depth
sensor (VL53L5CX ToF, or the AI Kit + a depth model) would be more reliable and
can be dropped in via ``announcer.estimate_distance_m``'s call site.

    python3 demos/05_obstacle_alert.py
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
from sightline.announcer import (
    Announcer, pan_from_cx, estimate_distance_m, horizontal_phrase, OBSTACLE_CLASSES,
)
from sightline import detector
from sightline.viz import Preview

WARN_HEIGHT = 0.30   # box taller than this => emit a proximity sweep
SPEAK_HEIGHT = 0.55  # very close => also speak a spoken warning


def main() -> None:
    cfg = config.load()
    speaker = Speaker(cfg["speech"])
    cues = AudioCues(cfg["audio_cues"], device=cfg["speech"]["audio_device"])
    announcer = Announcer(cfg["announcer"])
    preview = Preview(cfg["display"], "Obstacle alerts")
    max_d = cfg["audio_cues"]["max_distance_m"]

    obstacles = set(cfg["object_detection"].get("announce_classes") or []) or OBSTACLE_CLASSES

    print("Loading detector…")
    det = detector.build(cfg["object_detection"])
    speaker.say("Obstacle alerts on.")

    try:
        with Camera(cfg["camera"]) as cam:
            while True:
                frame = cam.read()
                detections = [d for d in det.detect(frame) if d.label in obstacles]
                # focus on the nearest (largest) obstacle
                detections.sort(key=lambda d: d.height, reverse=True)
                if detections:
                    d = detections[0]
                    if d.height >= WARN_HEIGHT:
                        dist = estimate_distance_m(d.height, max_d)
                        cues.proximity_sweep(pan=pan_from_cx(d.cx), distance_m=dist)
                        if d.height >= SPEAK_HEIGHT and announcer.should_announce(
                            f"warn:{d.label}", 1.0, force=False
                        ):
                            speaker.say(
                                f"{d.label} {horizontal_phrase(d.cx)}, close!",
                                priority=Speaker.PRIORITY_HIGH,
                            )
                if preview.update(frame, detections):
                    break
                time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        preview.close()
        speaker.say_blocking("Obstacle alerts off.")
        speaker.close()


if __name__ == "__main__":
    main()

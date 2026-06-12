"""Reusable face identification (enrol once, recognise anywhere).

Wraps the ``face_recognition`` library: loads the enrolled faces from the
known-faces directory and matches faces in a frame against them. Used by the
production app's "SIGHT face" command and shareable with the face demo.
"""
from __future__ import annotations

import cv2
import numpy as np

from . import config
from .announcer import Detection

try:
    import face_recognition
except Exception:
    face_recognition = None


class FaceIdentifier:
    def __init__(self, faces_cfg: dict):
        if face_recognition is None:
            raise RuntimeError("face_recognition not installed. Run: pip install face_recognition")
        self.tolerance = float(faces_cfg.get("tolerance", 0.6))
        self.model = faces_cfg.get("model", "hog")
        self.known_dir = config.resolve_path(faces_cfg.get("known_dir", "known_faces"))
        self.encodings, self.names = self._load()

    def _load(self):
        encs, names = [], []
        if not self.known_dir.is_dir():
            return encs, names
        for img_path in sorted(self.known_dir.glob("*")):
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            image = face_recognition.load_image_file(str(img_path))
            found = face_recognition.face_encodings(image)
            if found:
                encs.append(found[0])
                names.append(img_path.stem.replace("_", " "))
        return encs, names

    def identify(self, frame_bgr: np.ndarray, downscale: float = 0.5) -> list[Detection]:
        """Return a Detection per face; label is the name or 'unknown person'."""
        small = cv2.resize(frame_bgr, (0, 0), fx=downscale, fy=downscale)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model=self.model)
        encs = face_recognition.face_encodings(rgb, locations)
        h, w = small.shape[:2]
        out: list[Detection] = []
        for (top, right, bottom, left), enc in zip(locations, encs):
            name = "unknown person"
            conf = 0.0
            if self.encodings:
                dists = face_recognition.face_distance(self.encodings, enc)
                best = int(np.argmin(dists))
                if dists[best] <= self.tolerance:
                    name = self.names[best]
                    conf = float(1.0 - dists[best])
            out.append(Detection(name, conf, (left / w, top / h, right / w, bottom / h)))
        return out

    def best(self, frame_bgr: np.ndarray) -> Detection | None:
        """The largest (nearest) face in view, or None."""
        faces = self.identify(frame_bgr)
        if not faces:
            return None
        faces.sort(key=lambda d: (d.box[2] - d.box[0]) * (d.box[3] - d.box[1]), reverse=True)
        return faces[0]

    def enroll(self, frame_bgr: np.ndarray, name: str):
        """Save the face in view under ``name`` and add it live (no restart).

        Requires exactly one clearly-visible face. Returns the saved image path.
        """
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model=self.model)
        if len(locations) != 1:
            raise ValueError("need exactly one face in view")
        enc = face_recognition.face_encodings(rgb, locations)[0]
        self.known_dir.mkdir(parents=True, exist_ok=True)
        path = self.known_dir / f"{name.replace(' ', '_')}.jpg"
        cv2.imwrite(str(path), frame_bgr)
        self.encodings.append(enc)
        self.names.append(name)
        return path

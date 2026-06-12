"""Optional on-screen preview for local/laptop development.

On the wearable there's no screen — but on a laptop a window showing the camera
feed with detection overlays makes it easy to *see* what the device is reacting
to while you hear it. Entirely optional and a no-op when disabled or headless;
press ``q`` in the window to quit.
"""
from __future__ import annotations

import textwrap
from typing import Iterable, Optional

import cv2


def draw_detections(frame, detections, color=(0, 220, 0)) -> None:
    """Draw labeled boxes (objects with .box/.label/optional .confidence) in place."""
    h, w = frame.shape[:2]
    for d in detections or []:
        x1, y1, x2, y2 = d.box
        p1, p2 = (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h))
        cv2.rectangle(frame, p1, p2, color, 2)
        conf = getattr(d, "confidence", None)
        tag = d.label if not conf else f"{d.label} {conf:.2f}"
        cv2.putText(frame, tag, (p1[0], max(15, p1[1] - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


class Preview:
    def __init__(self, display_cfg: dict, title: Optional[str] = None):
        self.enabled = bool(display_cfg.get("preview", False))
        self.window = title or display_cfg.get("window", "Sightline")
        self._ok = self.enabled

    def update(self, frame, detections: Optional[Iterable] = None) -> bool:
        """Draw ``detections`` (objects with .box, .label, optional .confidence)
        on ``frame`` and show it. Returns True if the user pressed 'q'."""
        if not self._ok:
            return False
        try:
            img = frame.copy()
            draw_detections(img, detections)
            cv2.imshow(self.window, img)
            return (cv2.waitKey(1) & 0xFF) == ord("q")
        except cv2.error:
            # no GUI backend (headless) — disable and carry on
            self._ok = False
            return False

    def close(self) -> None:
        if self.enabled:
            try:
                cv2.destroyWindow(self.window)
            except cv2.error:
                pass


class CaptureWindow:
    """Interactive window with clickable buttons for the on-demand demos.

    Buttons are drawn on the frame and clicked with the mouse (works on any
    OpenCV GUI backend), and each also has keyboard shortcuts. ``show()`` returns
    the action id of whatever the user pressed/clicked, or "". A QUIT button is
    added automatically. If there's no display (headless Pi), it falls back to a
    non-blocking stdin trigger that fires the default capture action.

    ``buttons`` is a list of ``(label, action, keys)`` tuples, e.g.::

        CaptureWindow("Reader", [("READ", "capture", [ord(' ')]),
                                 ("DESCRIBE", "describe", [ord('d')])])
    """

    def __init__(self, title: str, buttons=None):
        self.title = title
        btns = list(buttons or [("CAPTURE", "capture", [ord(" "), ord("r"), 13, 10])])
        if not any(b[1] == "quit" for b in btns):
            btns.append(("QUIT", "quit", [ord("q"), 27]))
        self.buttons = btns
        self._gui = True
        self._win_ready = False
        self.status = ""
        self._text_lines: list[str] = []
        self._click = None
        self._rects: dict[str, tuple[int, int, int, int]] = {}

    # -- mouse ------------------------------------------------------------
    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._click = (x, y)

    # -- content ----------------------------------------------------------
    def set_status(self, text: str = "") -> None:
        self.status = text

    def set_text(self, text: str) -> None:
        wrapped: list[str] = []
        for para in (text or "").splitlines() or [""]:
            wrapped.extend(textwrap.wrap(para, width=52) or [""])
        self._text_lines = wrapped[-8:]  # keep the panel a sane height

    # -- rendering --------------------------------------------------------
    def _draw_buttons(self, img) -> None:
        self._rects = {}
        x, y1, h = 6, 6, 26
        for label, action, _keys in self.buttons:
            (tw, _th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            x2, y2 = x + tw + 18, y1 + h
            fill = (40, 40, 40) if action != "quit" else (30, 30, 70)
            cv2.rectangle(img, (x, y1), (x2, y2), fill, -1)
            cv2.rectangle(img, (x, y1), (x2, y2), (200, 200, 200), 1)
            cv2.putText(img, label, (x + 9, y1 + 18), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)
            self._rects[action] = (x, y1, x2, y2)
            x = x2 + 6

    def _render(self, frame):
        img = frame.copy()
        h, w = img.shape[:2]
        cv2.rectangle(img, (0, 0), (w, 38), (0, 0, 0), -1)
        self._draw_buttons(img)
        if self.status:
            cv2.putText(img, self.status, (w - 220, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 220, 255), 1, cv2.LINE_AA)
        if self._text_lines:
            panel_h = 22 * len(self._text_lines) + 12
            cv2.rectangle(img, (0, h - panel_h), (w, h), (0, 0, 0), -1)
            y = h - panel_h + 20
            for line in self._text_lines:
                cv2.putText(img, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.55, (220, 255, 220), 1, cv2.LINE_AA)
                y += 22
        return img

    def _hit(self, pos) -> str | None:
        px, py = pos
        for action, (x1, y1, x2, y2) in self._rects.items():
            if x1 <= px <= x2 and y1 <= py <= y2:
                return action
        return None

    # -- main entry -------------------------------------------------------
    def show(self, frame) -> str:
        """Render one frame; return the triggered action id or "". Never blocks."""
        if self._gui:
            try:
                if not self._win_ready:
                    cv2.namedWindow(self.title, cv2.WINDOW_AUTOSIZE)
                    cv2.setMouseCallback(self.title, self._on_mouse)
                    self._win_ready = True
                cv2.imshow(self.title, self._render(frame))
                key = cv2.waitKey(1) & 0xFF
                for _label, action, keys in self.buttons:
                    if key in keys:
                        return action
                if self._click is not None:
                    pos, self._click = self._click, None
                    hit = self._hit(pos)
                    if hit:
                        return hit
                return ""
            except cv2.error:
                self._gui = False
                print("No display; using keyboard (Enter to capture, Ctrl-C to quit).")
        from .trigger import triggered
        try:
            return "capture" if triggered() else ""
        except EOFError:
            return "quit"

    def close(self) -> None:
        if self._gui:
            try:
                cv2.destroyWindow(self.title)
            except cv2.error:
                pass

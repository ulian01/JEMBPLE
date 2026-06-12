"""Non-blocking stdin trigger for the on-demand demos (text reader, scene).

The earlier demos blocked on ``input()``, which stalls the camera pipeline (the
grab buffer backs up and the next read returns a stale frame or hangs) and is
fragile when driven through ``main.py``'s stdin pipe. Instead, the demos read a
fresh frame every loop iteration and call ``triggered()`` to check — without
blocking — whether the user has asked for a capture.

Works the same whether stdin is a terminal (press Enter) or a pipe (``main.py``
writes a newline on the ACTION button).
"""
from __future__ import annotations

import select
import sys


def triggered() -> bool:
    """Return True if a line is waiting on stdin; never blocks.

    Raises ``EOFError`` if stdin has closed (e.g. the controller terminated this
    child), so the caller's existing EOF handling exits cleanly.
    """
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
    except (ValueError, OSError):
        return False
    if not ready:
        return False
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return True

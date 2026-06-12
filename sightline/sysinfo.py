"""Device status helpers (battery, etc.) for spoken status commands."""
from __future__ import annotations

import glob
import os


def battery_phrase() -> str:
    """A spoken-friendly battery status, or a clear 'unavailable' message.

    Works on laptops (psutil / sysfs). On a Pi powered by a dumb USB bank there's
    usually no battery gauge — add a fuel-gauge HAT (e.g. PiSugar/MAX17048) and
    expose it under /sys/class/power_supply for this to report.
    """
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is not None:
            pct = int(round(b.percent))
            if b.power_plugged:
                return f"Battery {pct} percent, charging."
            secs = b.secsleft
            if secs and secs > 0 and secs != getattr(psutil, "POWER_TIME_UNLIMITED", -2):
                mins = secs // 60
                if mins >= 60:
                    return f"Battery {pct} percent, about {mins // 60} hours {mins % 60} minutes remaining."
                return f"Battery {pct} percent, about {mins} minutes remaining."
            return f"Battery {pct} percent."
    except Exception:
        pass
    # sysfs fallback
    try:
        for base in sorted(glob.glob("/sys/class/power_supply/BAT*")):
            with open(os.path.join(base, "capacity")) as f:
                pct = f.read().strip()
            status = ""
            try:
                with open(os.path.join(base, "status")) as f:
                    status = ", " + f.read().strip().lower()
            except OSError:
                pass
            return f"Battery {pct} percent{status}."
    except Exception:
        pass
    return "Battery status is not available on this device."

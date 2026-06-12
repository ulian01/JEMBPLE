"""Keep a configured Bluetooth audio device connected.

On the arm strap there is no screen and often no keyboard, so the headset has to
reconnect on its own. This polls the system Bluetooth stack through
``bluetoothctl``: if the configured device is not connected it tries to connect,
and it keeps retrying on an interval, so the headset comes back automatically
after it drops, moves out of range, or is powered on later.

Everything degrades to a no-op. A missing ``bluetoothctl``, an empty device
address, or any command failure simply means the manager does nothing rather
than breaking the app. The device must already be paired and trusted once (a
one-time ``bluetoothctl pair``/``trust``); this only handles reconnection.
"""
from __future__ import annotations

import shutil
import subprocess
import threading


def _run_bluetoothctl(args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bluetoothctl", *args],
        capture_output=True, text=True, timeout=timeout,
    )


def parse_connected(info_output: str) -> bool:
    """Return True if ``bluetoothctl info <mac>`` output reports Connected: yes."""
    for line in (info_output or "").splitlines():
        line = line.strip()
        if line.lower().startswith("connected:"):
            return line.split(":", 1)[1].strip().lower() == "yes"
    return False


class BluetoothManager:
    def __init__(self, bt_cfg: dict | None = None):
        bt_cfg = bt_cfg or {}
        self.enabled = bool(bt_cfg.get("enabled", False))
        self.mac = str(bt_cfg.get("mac", "")).strip()
        self.interval = float(bt_cfg.get("poll_interval", 15.0))
        self._available = shutil.which("bluetoothctl") is not None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def active(self) -> bool:
        """True only if enabled, a device is configured, and bluetoothctl exists."""
        return self.enabled and bool(self.mac) and self._available

    # -- status / actions -------------------------------------------------
    def is_connected(self) -> bool:
        try:
            result = _run_bluetoothctl(["info", self.mac])
            return parse_connected(result.stdout)
        except Exception:
            return False

    def ensure_connected(self) -> bool:
        """Connect the device if it is not already connected. Returns the state."""
        if self.is_connected():
            return True
        try:
            _run_bluetoothctl(["connect", self.mac], timeout=20.0)
        except Exception:
            return False
        return self.is_connected()

    # -- lifecycle --------------------------------------------------------
    def start(self) -> "BluetoothManager":
        if not self.active():
            if self.enabled and self.mac and not self._available:
                print("Bluetooth: bluetoothctl not found; auto-reconnect disabled.")
            return self
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"Bluetooth: keeping {self.mac} connected (every {self.interval:g}s).")
        return self

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.ensure_connected()
            except Exception:
                pass
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

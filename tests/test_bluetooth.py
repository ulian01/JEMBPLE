"""Tests for the Bluetooth auto-reconnect manager.

No real Bluetooth stack is touched: bluetoothctl calls are monkeypatched.
"""
from __future__ import annotations

from sightline import bluetooth
from sightline.bluetooth import BluetoothManager, parse_connected


def test_parse_connected_yes():
    info = "Device AA:BB\n\tName: Buds\n\tConnected: yes\n\tTrusted: yes\n"
    assert parse_connected(info) is True


def test_parse_connected_no():
    info = "Device AA:BB\n\tConnected: no\n"
    assert parse_connected(info) is False


def test_parse_connected_missing():
    assert parse_connected("Device AA:BB\n\tPaired: yes\n") is False
    assert parse_connected("") is False


def test_inactive_when_disabled():
    mgr = BluetoothManager({"enabled": False, "mac": "AA:BB:CC:DD:EE:FF"})
    assert mgr.active() is False


def test_inactive_without_mac():
    mgr = BluetoothManager({"enabled": True, "mac": ""})
    assert mgr.active() is False


def test_active_requires_bluetoothctl(monkeypatch):
    mgr = BluetoothManager({"enabled": True, "mac": "AA:BB:CC:DD:EE:FF"})
    mgr._available = True
    assert mgr.active() is True
    mgr._available = False
    assert mgr.active() is False


def test_ensure_connected_skips_when_already_connected(monkeypatch):
    mgr = BluetoothManager({"enabled": True, "mac": "AA:BB:CC:DD:EE:FF"})
    calls = []

    def fake_run(args, timeout=10.0):
        calls.append(args)
        # info -> connected yes; connect should never be called
        class R: stdout = "\tConnected: yes\n"
        return R()

    monkeypatch.setattr(bluetooth, "_run_bluetoothctl", fake_run)
    assert mgr.ensure_connected() is True
    assert calls == [["info", "AA:BB:CC:DD:EE:FF"]]   # no connect attempt


def test_ensure_connected_connects_when_disconnected(monkeypatch):
    mgr = BluetoothManager({"enabled": True, "mac": "AA:BB:CC:DD:EE:FF"})
    states = iter(["no", "yes"])    # before connect: no; after connect: yes
    calls = []

    def fake_run(args, timeout=10.0):
        calls.append(args[0])
        class R: stdout = f"\tConnected: {next(states)}\n" if args[0] == "info" else ""
        return R()

    monkeypatch.setattr(bluetooth, "_run_bluetoothctl", fake_run)
    assert mgr.ensure_connected() is True
    assert "connect" in calls


def test_ensure_connected_survives_command_failure(monkeypatch):
    mgr = BluetoothManager({"enabled": True, "mac": "AA:BB:CC:DD:EE:FF"})

    def boom(args, timeout=10.0):
        raise RuntimeError("bluetoothctl exploded")

    monkeypatch.setattr(bluetooth, "_run_bluetoothctl", boom)
    assert mgr.is_connected() is False     # does not raise
    assert mgr.ensure_connected() is False


def test_start_is_noop_when_inactive():
    mgr = BluetoothManager({"enabled": False})
    mgr.start()                  # should not spawn a thread
    assert mgr._thread is None
    mgr.stop()                   # safe even though never started

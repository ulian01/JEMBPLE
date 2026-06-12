"""Barcode / QR reading with an optional product-name lookup.

Decodes with pyzbar (needs the system lib: ``sudo apt install libzbar0``), reads
QR payloads directly, and looks up retail barcodes (EAN/UPC) against the free
OpenFoodFacts database for a product name. All network/decoder failures degrade
to a spoken message rather than raising.
"""
from __future__ import annotations

import json
import urllib.request

import cv2

try:
    from pyzbar.pyzbar import decode as _zbar_decode
except Exception:
    _zbar_decode = None


def available() -> bool:
    return _zbar_decode is not None


def _scan(frame_bgr):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    results = _zbar_decode(gray)
    if not results:
        return None
    r = results[0]
    return r.type, r.data.decode("utf-8", "replace")


def _lookup(code: str):
    url = f"https://world.openfoodfacts.org/api/v0/product/{code}.json"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == 1:
            p = data["product"]
            return p.get("product_name") or p.get("generic_name")
    except Exception:
        return None
    return None


def read(frame_bgr) -> str:
    """High-level: decode whatever's in view and return a spoken message."""
    if _zbar_decode is None:
        return "Barcode scanning isn't installed. Run sudo apt install libzbar0 and pip install pyzbar."
    found = _scan(frame_bgr)
    if not found:
        return "No barcode found. Hold it steady in view."
    kind, data = found
    if kind == "QRCODE":
        return f"QR code says: {data}"
    name = _lookup(data)
    if name:
        return f"{name}."
    return f"Barcode {data}. Product not found in the database."

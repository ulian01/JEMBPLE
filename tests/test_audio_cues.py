from __future__ import annotations

import numpy as np
import pytest

from sightline.audio_cues import AudioCues


def _cues():
    # backend="aplay" avoids touching sounddevice; _tone never plays audio.
    return AudioCues(
        {"enabled": True, "sample_rate": 22050, "max_distance_m": 4.0},
        device="default", backend="aplay",
    )


def test_tone_shape_and_dtype():
    buf = _cues()._tone(440.0, 0.1, 0.0, 0.5)
    assert buf.shape == (int(22050 * 0.1), 2)
    assert buf.dtype == np.float32


def test_tone_amplitude_bounded_by_volume():
    buf = _cues()._tone(440.0, 0.1, 0.0, 0.5)
    assert np.max(np.abs(buf)) <= 0.5 + 1e-6


def test_tone_pan_full_left_silences_right():
    buf = _cues()._tone(440.0, 0.1, -1.0, 0.5)
    left, right = buf[:, 0], buf[:, 1]
    assert np.allclose(right, 0.0, atol=1e-6)
    assert np.max(np.abs(left)) > 0.1


def test_tone_pan_full_right_silences_left():
    buf = _cues()._tone(440.0, 0.1, 1.0, 0.5)
    left, right = buf[:, 0], buf[:, 1]
    assert np.allclose(left, 0.0, atol=1e-6)
    assert np.max(np.abs(right)) > 0.1


def test_tone_centre_pan_balances_channels():
    buf = _cues()._tone(440.0, 0.1, 0.0, 0.5)
    rms_left = float(np.sqrt(np.mean(buf[:, 0] ** 2)))
    rms_right = float(np.sqrt(np.mean(buf[:, 1] ** 2)))
    assert rms_left == pytest.approx(rms_right, rel=1e-5)

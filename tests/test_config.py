from __future__ import annotations

from sightline import config
from sightline.config import _deep_merge


def test_deep_merge_nested():
    out = _deep_merge({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}})
    assert out == {"a": {"x": 1, "y": 3}}


def test_deep_merge_scalar_replaces_dict():
    out = _deep_merge({"a": {"x": 1}}, {"a": 5})
    assert out == {"a": 5}


def test_deep_merge_adds_new_key():
    out = _deep_merge({"a": 1}, {"b": 2})
    assert out == {"a": 1, "b": 2}


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    _deep_merge(base, {"a": {"x": 9}})
    assert base == {"a": {"x": 1}}


def test_load_missing_file_returns_defaults():
    cfg = config.load("/nonexistent/path/does-not-exist.yaml")
    assert cfg["camera"]["width"] == 640        # built-in default
    assert cfg["speech"]["volume"] == 1.0


def test_load_overlays_user_yaml(tmp_path):
    p = tmp_path / "user.yaml"
    p.write_text("camera:\n  width: 1280\n")
    cfg = config.load(p)
    assert cfg["camera"]["width"] == 1280       # overridden
    assert cfg["camera"]["height"] == 480       # default preserved
    assert cfg["speech"]["volume"] == 1.0       # untouched branch preserved


def test_resolve_path_absolute_passthrough():
    from pathlib import Path
    assert config.resolve_path("/abs/x") == Path("/abs/x")


def test_resolve_path_relative_joins_root():
    p = config.resolve_path("models/x.tflite")
    assert p.is_absolute()
    assert p.as_posix().endswith("models/x.tflite")

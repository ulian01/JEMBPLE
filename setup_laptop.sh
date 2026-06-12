#!/usr/bin/env bash
# One-shot local setup for an LMDE / Debian / Ubuntu laptop.
# Sets up a virtualenv and installs everything needed to run Sightline off the
# built-in webcam. Face recognition (heavy dlib build) is optional — see the end.
set -euo pipefail

cd "$(dirname "$0")"

echo "==> System packages (sudo)…"
sudo apt update
sudo apt install -y \
  python3-venv python3-pip python3-opencv \
  espeak-ng tesseract-ocr \
  libportaudio2          # for sounddevice (spatial audio)

echo "==> Python virtualenv (.venv)…"
python3 -m venv --system-site-packages .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Core + demo Python deps…"
pip install --upgrade pip
pip install numpy PyYAML sounddevice pytesseract anthropic
pip install ultralytics      # YOLO detector; pulls torch (large, ~1 min+)

cat <<'EOF'

==> Done.

Activate the venv and run with the laptop profile:

    source .venv/bin/activate
    export SIGHTLINE_CONFIG=config.laptop.yaml
    export ANTHROPIC_API_KEY=sk-ant-...        # only needed for demo 4 (scene)

    python3 demos/01_object_detector.py        # webcam + preview window
    python3 demos/05_obstacle_alert.py
    python3 demos/03_text_reader.py            # press Enter to read text
    python3 demos/04_scene_describer.py        # press Enter to describe
    python3 main.py                            # m = mode, a = action, q = quit

Optional — face recognition (demo 2) needs dlib, which compiles from source:

    sudo apt install -y cmake build-essential
    pip install face_recognition
    python3 demos/enroll_face.py "Your Name"
EOF

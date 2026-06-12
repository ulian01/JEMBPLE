#!/usr/bin/env bash
# Install offline voice commands (Vosk STT) for the production app (app.py).
set -euo pipefail

MODEL_DIR="${HOME}/vosk_models"
MODEL="vosk-model-small-en-us-0.15"     # ~40 MB, fast, good for a command grammar
URL="https://alphacephei.com/vosk/models/${MODEL}.zip"

echo "==> System deps (sudo)…"
sudo apt install -y libportaudio2 unzip wget libzbar0   # libzbar0 = barcode scanning

echo "==> Python deps…"
pip install vosk sounddevice psutil pyzbar              # STT, battery, barcode

echo "==> Downloading ${MODEL}…"
mkdir -p "${MODEL_DIR}"
cd "${MODEL_DIR}"
if [ ! -d "${MODEL}" ]; then
  wget -q --show-progress -O "${MODEL}.zip" "${URL}"
  unzip -q "${MODEL}.zip"
  rm -f "${MODEL}.zip"
fi

cat <<EOF

==> Done. Enable voice in your config (config.laptop.yaml):

voice:
  enabled: true
  model: ${MODEL_DIR}/${MODEL}
  wakeword: sight

Then run:  python app.py
Say:  "SIGHT text"  /  "SIGHT describe"  /  "SIGHT face"  /  "SIGHT stop"
EOF

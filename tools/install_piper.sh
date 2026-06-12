#!/usr/bin/env bash
# Install Piper — a neural, offline, free text-to-speech voice that sounds far
# more natural than eSpeak. (Note: Whisper is speech-to-TEXT, not TTS, so it
# can't be used for the spoken output — Piper is the right tool here.)
set -euo pipefail

VOICE_DIR="${HOME}/piper_voices"
VOICE="en_GB-alba-medium"     # a clear British English voice; browse more at
                              # https://rhasspy.github.io/piper-samples/
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alba/medium"

echo "==> Installing piper-tts into the active environment…"
pip install piper-tts

echo "==> Downloading voice ${VOICE} into ${VOICE_DIR}…"
mkdir -p "${VOICE_DIR}"
cd "${VOICE_DIR}"
wget -q --show-progress -O "${VOICE}.onnx"      "${BASE}/${VOICE}.onnx"
wget -q --show-progress -O "${VOICE}.onnx.json" "${BASE}/${VOICE}.onnx.json"

cat <<EOF

==> Done. Point Sightline at the voice by adding this to your config
    (config.laptop.yaml or config.yaml):

speech:
  engine: piper
  piper_model: ${VOICE_DIR}/${VOICE}.onnx

Then run any demo — speech will use Piper. If 'piper' isn't found on PATH,
make sure the venv is activated. eSpeak-NG remains the automatic fallback.
EOF

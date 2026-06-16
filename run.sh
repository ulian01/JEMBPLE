#!/usr/bin/env bash
# Launch Sightline (app.py) with secrets loaded and the project venv.
#
# Secrets (ANTHROPIC_API_KEY, etc.) live in a 600-perm file OUTSIDE the repo so
# the key is never committed. Override its location with SIGHTLINE_ENV.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_FILE="${SIGHTLINE_ENV:-$HOME/.config/sightline/sightline.env}"
if [ -f "$ENV_FILE" ]; then
    set -a              # export everything sourced
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
else
    echo "run.sh: no env file at $ENV_FILE — Claude vision/OCR/scene commands" \
         "will fail without ANTHROPIC_API_KEY." >&2
fi

# Expose the venv's bin/ so tools installed into it (e.g. the `piper` TTS CLI)
# resolve via PATH even though we invoke python directly without activating.
export PATH="$HERE/.venv/bin:$PATH"

# Control GUI preview window (defaults to enabled, i.e., ENABLE_GUI=1).
# The app treats an unset DISPLAY/WAYLAND_DISPLAY as headless (see
# app.py _has_display). Run with ENABLE_GUI=0 ./run.sh to force headless mode
# even when launched from a desktop / VNC session.
if [ "${ENABLE_GUI:-1}" != "1" ]; then
    unset DISPLAY WAYLAND_DISPLAY
fi

exec "$HERE/.venv/bin/python" "$HERE/app.py" "$@"

#!/usr/bin/env bash
# install.sh — Install the jlcpcb-auth plugin into ~/.hermes/plugins/

set -e

PLUGIN_DIR="$HOME/.hermes/plugins/jlcpcb-auth"
ENV_FILE="$HOME/.hermes/.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "=== JLCPCB Auth Plugin Installer ==="
echo ""

mkdir -p "$PLUGIN_DIR"
cp -r "$SCRIPT_DIR"/. "$PLUGIN_DIR"/
echo "✓ Plugin files copied to $PLUGIN_DIR"

mkdir -p "$HOME/.hermes"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "✓ ~/.hermes/.env is present and chmod 600"

echo ""
echo "Would you like to set JLCPCB credentials now?"
echo "  (You can also do this later via Hermes dashboard → JLCPCB Auth tab)"
echo ""
read -r -p "Set credentials now? [y/N] " REPLY

if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    echo ""
    read -r -p "  JLCPCB email address: " JLC_USER
    read -r -s -p "  JLCPCB password: " JLC_PASS
    echo ""

    if [[ -z "$JLC_USER" || -z "$JLC_PASS" ]]; then
        echo "  ⚠ Skipped — one or both values were empty."
    else
        JLC_USER="$JLC_USER" JLC_PASS="$JLC_PASS" PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PY'
import os
from credentials import set_credentials

set_credentials(os.environ["JLC_USER"], os.environ["JLC_PASS"])
PY
        echo "  ✓ Credentials written to $ENV_FILE"
    fi
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Restart Hermes once to load the new plugin:"
echo "       docker compose restart   # if running in Docker"
echo "       hermes restart           # if running standalone"
echo ""
echo "  2. Verify the plugin loaded:"
echo "       hermes plugins list"
echo "     You should see: jlcpcb-auth  [enabled]"
echo ""
echo "  3. Open Hermes dashboard and set/update credentials anytime:"
echo "       hermes dashboard"
echo "     Navigate to the JLCPCB Auth tab."
echo ""
echo "  4. Test via agent chat:"
echo "       > Test my JLCPCB login"
echo ""

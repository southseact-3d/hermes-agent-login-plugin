#!/usr/bin/env bash
# install.sh — Install the jlcpcb-auth plugin into ~/.hermes/plugins/
#
# Usage:
#   chmod +x install.sh && ./install.sh
#
# What it does:
#   1. Copies the plugin directory to ~/.hermes/plugins/jlcpcb-auth/
#   2. Optionally prompts for credentials and writes them to ~/.hermes/.env
#   3. Sets correct permissions on the .env file (chmod 600)
#   4. Prints next steps

set -e

PLUGIN_DIR="$HOME/.hermes/plugins/jlcpcb-auth"
ENV_FILE="$HOME/.hermes/.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "=== JLCPCB Auth Plugin Installer ==="
echo ""

# ── Copy plugin files ─────────────────────────────────────────────────────────
mkdir -p "$PLUGIN_DIR"
cp -r "$SCRIPT_DIR"/. "$PLUGIN_DIR/"
echo "✓ Plugin files copied to $PLUGIN_DIR"

# ── Create .hermes directory and .env if needed ───────────────────────────────
mkdir -p "$HOME/.hermes"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
echo "✓ ~/.hermes/.env is present and chmod 600"

# ── Optional: prompt for credentials ─────────────────────────────────────────
echo ""
echo "Would you like to set JLCPCB credentials now?"
echo "  (You can also do this later via the Hermes dashboard → JLCPCB Auth tab)"
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
        # Remove any existing entries then append
        TMPFILE=$(mktemp)
        grep -v "^JLCPCB_USERNAME=" "$ENV_FILE" | grep -v "^JLCPCB_PASSWORD=" > "$TMPFILE" || true
        echo "JLCPCB_USERNAME=$JLC_USER" >> "$TMPFILE"
        echo "JLCPCB_PASSWORD=$JLC_PASS" >> "$TMPFILE"
        mv "$TMPFILE" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        echo "  ✓ Credentials written to $ENV_FILE"
    fi
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Restart Hermes (so it picks up the new plugin and .env values):"
echo "       docker compose restart   # if running in Docker"
echo "       hermes restart           # if running standalone"
echo ""
echo "  2. Verify the plugin loaded:"
echo "       hermes plugins list"
echo "     You should see: jlcpcb-auth  [enabled]"
echo ""
echo "  3. Test in the Hermes dashboard:"
echo "       hermes dashboard"
echo "     Navigate to the 🔐 JLCPCB Auth tab."
echo ""
echo "  4. Or test via agent chat:"
echo "       > Test my JLCPCB login"
echo ""

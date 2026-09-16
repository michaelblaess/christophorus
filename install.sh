#!/usr/bin/env bash
# ============================================================
#  Christophorus - installer for Linux and macOS
#
#  Usage:
#    curl -fsSL https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.sh | bash
#
#  Downloads the prebuilt package of the latest release.
#  No Python and no git required.
#
#  Supported: Linux x86_64, macOS on Apple Silicon (arm64).
#
#  Installs to:  ~/.local/share/christophorus/
#  Commands:     ~/.local/bin/christophorus and ~/.local/bin/christo
#
#  Optional environment variables (mainly for testing):
#    CHRISTOPHORUS_INSTALL_DIR  other install folder
#    CHRISTOPHORUS_BIN_DIR      other folder for the commands
# ============================================================

set -euo pipefail

REPO="michaelblaess/christophorus"
INSTALL_DIR="${CHRISTOPHORUS_INSTALL_DIR:-$HOME/.local/share/christophorus}"
BIN_DIR="${CHRISTOPHORUS_BIN_DIR:-$HOME/.local/bin}"

echo ""
echo "  Christophorus - installer"
echo ""

case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) SUFFIX="linux-x86_64.tar.gz" ;;
    Darwin-arm64) SUFFIX="macos-arm64.tar.gz" ;;
    *)
        echo "  [ERROR] No prebuilt package for $(uname -s) $(uname -m)."
        echo "  Run it from source instead: https://github.com/$REPO#from-source"
        exit 1
        ;;
esac

for tool in curl tar; do
    command -v "$tool" >/dev/null 2>&1 || { echo "  [ERROR] $tool is required."; exit 1; }
done

echo "  Looking up the latest release..."
RELEASE_JSON="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest")"
VERSION="$(printf '%s' "$RELEASE_JSON" | grep -m1 '"tag_name"' | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')"
URL="$(printf '%s' "$RELEASE_JSON" | grep -o "\"browser_download_url\": *\"[^\"]*$SUFFIX\"" | head -1 | sed -E 's/.*"(https[^"]+)"/\1/')"
if [ -z "$URL" ]; then
    echo "  [ERROR] Release $VERSION has no package *$SUFFIX."
    echo "  See https://github.com/$REPO/releases"
    exit 1
fi
echo "  [OK] $VERSION ($(basename "$URL"))"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "  Downloading..."
curl -fsSL "$URL" -o "$TMP_DIR/package.tar.gz"
tar -xzf "$TMP_DIR/package.tar.gz" -C "$TMP_DIR"
if [ ! -x "$TMP_DIR/christophorus/christophorus" ]; then
    echo "  [ERROR] christophorus not found in the package."
    exit 1
fi

# Replace only the program files. Settings and logbooks live elsewhere
# (~/.christo and the folders you chose) and are not touched.
mkdir -p "$INSTALL_DIR" "$BIN_DIR"
rm -rf "$INSTALL_DIR/app"
mv "$TMP_DIR/christophorus" "$INSTALL_DIR/app"
if [ "$(uname -s)" = "Darwin" ]; then
    xattr -dr com.apple.quarantine "$INSTALL_DIR/app" 2>/dev/null || true
fi
echo "  [OK] Installed to $INSTALL_DIR/app"

for name in christophorus christo; do
    ln -sf "$INSTALL_DIR/app/christophorus" "$BIN_DIR/$name"
done
echo "  [OK] Commands christophorus and christo in $BIN_DIR"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo ""
        echo "  $BIN_DIR is not on your PATH. Add this line to your shell profile:"
        echo "    export PATH=\"$BIN_DIR:\$PATH\""
        ;;
esac

echo ""
echo "  Done: Christophorus $VERSION"
echo ""
echo "  Start:      christophorus   (or: christo)"
echo "  Update:     run this installer again"
echo "  Uninstall:  rm -rf \"$INSTALL_DIR\" \"$BIN_DIR/christophorus\" \"$BIN_DIR/christo\""
echo ""

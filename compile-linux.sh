#!/usr/bin/env bash
# compile-linux.sh - compiles christophorus into a standalone Linux binary with Nuitka.
#
# Produces a self-contained --standalone build (no Python install needed on the
# target machine). Output: dist/christophorus/christophorus plus its shared libraries,
# and dist/christophorus-vX.Y.Z-linux-x86_64.tar.gz ready to hand out.
#
# Build-Maschine braucht: gcc, patchelf und die Python-Header.
#   Debian/Ubuntu:  sudo apt install gcc patchelf python3-dev
#   Fedora:         sudo dnf install gcc patchelf python3-devel

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
entry="$root/src/christo/__main__.py"
init_py="$root/src/christo/__init__.py"
out_dir="$root/dist"
dist_dir="$out_dir/christophorus"

# venv-Python bevorzugen, sonst System-Python
if [ -x "$root/.venv/bin/python" ]; then
    python="$root/.venv/bin/python"
else
    python="python3"
fi

# Build-Tools pruefen, bevor Nuitka mittendrin abbricht
for tool in gcc patchelf; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Fehlt: $tool - bitte installieren (z.B. sudo apt install gcc patchelf python3-dev)" >&2
        exit 1
    fi
done

# venv mit dem Lockfile abgleichen, damit Nuitka keine veralteten
# (Git-)Dependencies einkompiliert. --inexact laesst Extra-Pakete wie das
# ad-hoc installierte nuitka unangetastet.
if command -v uv >/dev/null 2>&1; then
    echo "Syncing venv to lockfile (uv sync --inexact)..."
    uv sync --inexact --project "$root"
else
    echo "uv nicht gefunden - venv-Sync uebersprungen" >&2
fi

# Version aus __init__.py lesen, damit nichts driftet
# (portables sed - 'grep -oP' gibt es auf dem BSD-grep von macOS nicht)
version="$(sed -n 's/^__version__ *= *"\([^"]*\)".*/\1/p' "$init_py")"
if [ -z "$version" ]; then
    echo "Konnte __version__ nicht aus $init_py lesen" >&2
    exit 1
fi

echo "Compiling christophorus v$version with Nuitka..."

# Alten Build verwerfen - das Ergebnis soll reproduzierbar sein
rm -rf "$dist_dir"

started=$(date +%s)

# --standalone        : self-contained, kein Python auf dem Zielrechner noetig
# --remove-output     : C-/Objekt-Zwischendateien nach dem Build aufraeumen
# --include-package-data=christo : eingebettete Datendateien (tcss etc.) mitnehmen
# Nuitka als Build-Tool sicherstellen (kein Dev-Dep, wird ad-hoc installiert).
# 'uv sync' ohne --inexact entfernt es wieder, daher: nach jedem Sync pruefen.
if ! "$python" -m nuitka --version >/dev/null 2>&1; then
    echo "Nuitka fehlt im venv - installiere..."
    uv pip install nuitka || { echo "Nuitka-Installation fehlgeschlagen" >&2; exit 1; }
fi

"$python" -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --remove-output \
    --include-package=christo \
    --include-package-data=christo \
    --output-dir="$out_dir" \
    --output-filename=christophorus \
    "$entry"

# Nuitka benennt den dist-Ordner nach dem Hauptmodul (__main__.dist) - umbenennen
if [ -d "$out_dir/__main__.dist" ]; then
    mv "$out_dir/__main__.dist" "$dist_dir"
fi

elapsed=$(( $(date +%s) - started ))
exe="$dist_dir/christophorus"
size_mb=$(du -sm "$dist_dir" | cut -f1)

# Verteilbares Archiv: tar.gz statt zip - tar bewahrt das Ausfuehrungs-Flag
# der Binary, ein zip wuerde es verlieren.
tarball="$out_dir/christophorus-v$version-linux-x86_64.tar.gz"
rm -f "$tarball"
tar -czf "$tarball" -C "$out_dir" christophorus
tar_mb=$(du -sm "$tarball" | cut -f1)

echo ""
echo "Done in ${elapsed}s"
echo "  dist folder : $dist_dir  (${size_mb} MB)"
echo "  tarball     : $tarball  (${tar_mb} MB)"
echo "  run         : $exe"

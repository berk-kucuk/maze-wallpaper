#!/usr/bin/env bash
# Development install: link the Plasma plugin from this checkout into
# ~/.local/share/plasma/wallpapers, so edits to the QML take effect the next
# time the wallpaper loads. Needs no root. The package (PKGBUILD) installs it
# system-wide instead; do not use both.
#
#   ./install-plugin.sh            link the plugin
#   ./install-plugin.sh --remove   unlink it
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ID=com.mazelinux.wallpaper
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/wallpapers/$ID"

if [[ "${1:-}" == "--remove" ]]; then
  [[ -L "$DEST" ]] && rm "$DEST" && echo "removed $DEST"
  exit 0
fi
if [[ -e "$DEST" && ! -L "$DEST" ]]; then
  echo "$DEST exists and is not a link — remove it first" >&2
  exit 1
fi
mkdir -p "$(dirname "$DEST")"
ln -sfn "$ROOT/plasma/$ID" "$DEST"
echo "linked $DEST -> $ROOT/plasma/$ID"
echo "Run the app with: python3 $ROOT/main.py"

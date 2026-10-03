#!/usr/bin/env bash
# =============================================================================
#  Maze Wallpaper — local Arch package builder
#
#  Builds maze-wallpaper-<version>-<rel>-any.pkg.tar.zst from the current
#  working tree using packaging/PKGBUILD. The version is read from
#  mazewallpaper/__init__.py. Runs the tests first; installs nothing.
#
#  Usage:
#    ./build-pkg.sh              build into ./dist-pkg/
#    ./build-pkg.sh --clean      remove ./dist-pkg/ and exit
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/dist-pkg"
NAME=maze-wallpaper

if [[ -t 1 ]]; then
  GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; RESET='\033[0m'
else
  GREEN=''; BLUE=''; RED=''; RESET=''
fi
info() { echo -e "${BLUE}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
die()  { echo -e "${RED}[✗]${RESET} $*" >&2; exit 1; }

case "${1:-}" in
  --clean)   rm -rf "$OUT"; ok "Removed $OUT"; exit 0 ;;
  -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^#\s\?//'; exit 0 ;;
  "") ;;
  *) die "Unknown option: $1" ;;
esac

command -v makepkg >/dev/null || die "makepkg not found — run this on Arch."

VER="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/mazewallpaper/__init__.py")"
[[ -n "$VER" ]] || die "Could not read __version__"
info "Building $NAME $VER from working tree"

info "Running tests ..."
LOG="$(mktemp)"
if QT_QPA_PLATFORM=offscreen python3 "$ROOT/tests/test_core.py" >"$LOG" 2>&1; then
  ok "$(grep -c '\.\.\. ok' "$LOG") tests passed"
else
  tail -30 "$LOG"; die "Tests failed — see $LOG"
fi

if command -v qmllint >/dev/null; then
  info "Linting QML ..."
  ( cd "$ROOT/plasma/com.mazelinux.wallpaper/contents/ui" && qmllint *.qml ) \
    || die "qmllint failed"
fi

BUILD="$OUT/build"; STAGE="$OUT/stage/$NAME-$VER"
rm -rf "$BUILD" "$OUT/stage"; mkdir -p "$BUILD" "$STAGE"
cp -r "$ROOT/mazewallpaper" "$ROOT/plasma" "$ROOT/assets" "$STAGE/"
cp "$ROOT/main.py" "$ROOT/LICENSE" "$ROOT/README.md" "$STAGE/"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +

tar czf "$BUILD/$NAME-$VER.tar.gz" -C "$OUT/stage" "$NAME-$VER"
rm -rf "$OUT/stage"
cp "$ROOT/packaging/PKGBUILD" "$BUILD/"
sed -i "s/^pkgver=.*/pkgver=${VER}/" "$BUILD/PKGBUILD"

info "Running makepkg ..."
( cd "$BUILD" && makepkg -f --noconfirm --nodeps )
PKG="$(find "$BUILD" -maxdepth 1 -name '*.pkg.tar.zst' -print -quit)"
[[ -n "$PKG" ]] || die "makepkg produced no package"
mv -f "$PKG" "$OUT/"
rm -rf "$BUILD"

ok "Package ready: $OUT/$(basename "$PKG")"
echo
echo "  To install:  sudo pacman -U \"$OUT/$(basename "$PKG")\""
echo "  If you used ./install-plugin.sh, run ./install-plugin.sh --remove first."

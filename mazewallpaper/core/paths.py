"""Where things live. Everything is per-user except the system wallpaper dirs."""
from __future__ import annotations

import os
from pathlib import Path


def _xdg(var: str, fallback: str) -> Path:
    return Path(os.environ.get(var) or (Path.home() / fallback))


DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share") / "maze-wallpaper"
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config") / "maze-wallpaper"
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache") / "maze-wallpaper"

# The user's own imports. Files are copied in, so deleting or moving the
# original never breaks a wallpaper that is on screen.
LIBRARY_DIR = DATA_DIR / "library"
# Full-resolution first frames of videos, used for the lock screen.
POSTER_DIR = DATA_DIR / "posters"
THUMB_DIR = CACHE_DIR / "thumbs"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# KPackage wallpaper folders: Maze's own (maze-branding) and anything the user
# installed through Plasma's "Get New Wallpapers".
SYSTEM_WALLPAPER_DIRS = (
    Path("/usr/share/wallpapers"),
    _xdg("XDG_DATA_HOME", ".local/share") / "wallpapers",
)


def ensure_dirs() -> None:
    for d in (LIBRARY_DIR, POSTER_DIR, THUMB_DIR, CONFIG_DIR):
        d.mkdir(parents=True, exist_ok=True)

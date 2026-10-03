"""Thumbnails and lock-screen posters.

Everything here works on QImage only — no widgets, no pixmaps — so it is safe
to call from a worker thread, which is where the gallery calls it from.

Thumbnails are cached by (path, mtime, size), so a replaced file gets a fresh
thumbnail and an unchanged one is never decoded twice.
"""
from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage, QImageReader

from mazewallpaper.core import paths
from mazewallpaper.core.library import KIND_VIDEO, Wallpaper

THUMB_W, THUMB_H = 480, 270
_FFMPEG_TIMEOUT = 20


def _cache_key(wp: Wallpaper) -> str:
    try:
        st = Path(wp.source).stat()
        stamp = f"{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        stamp = "missing"
    return hashlib.sha1(f"{wp.source}|{stamp}|{THUMB_W}x{THUMB_H}".encode()).hexdigest()


def thumb_path(wp: Wallpaper) -> Path:
    return paths.THUMB_DIR / f"{_cache_key(wp)}.jpg"


def ensure_thumb(wp: Wallpaper) -> Path | None:
    """Return a cached thumbnail for `wp`, creating it if needed."""
    out = thumb_path(wp)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)

    if wp.kind == KIND_VIDEO:
        return out if _ffmpeg_frame(Path(wp.source), out, THUMB_W, THUMB_H) else None
    img = _read_scaled(Path(wp.source), THUMB_W, THUMB_H)

    if img is None or img.isNull():
        return None
    return out if img.save(str(out), "JPG", 88) else None


def _read_scaled(path: Path, w: int, h: int) -> QImage | None:
    """Decode at (roughly) thumbnail size, cropped to fill. For GIFs this is
    the first frame."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    src = reader.size()
    if src.isValid() and src.width() > 0 and src.height() > 0:
        scale = max(w / src.width(), h / src.height())
        reader.setScaledSize(QSize(max(1, math.ceil(src.width() * scale)),
                                   max(1, math.ceil(src.height() * scale))))
    img = reader.read()
    if img.isNull():
        return None
    img = img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    x = (img.width() - w) // 2
    y = (img.height() - h) // 2
    return img.copy(x, y, w, h)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffmpeg_frame(src: Path, out: Path, w: int | None, h: int | None) -> bool:
    """Grab one frame from a video. Tries 1 s in first (the opening frame is
    often black), then the very first frame for clips shorter than that."""
    if not ffmpeg_available():
        return False
    vf = []
    if w and h:
        vf = ["-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"]
    for seek in ("1", "0"):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", seek, "-i", str(src), "-frames:v", "1", *vf, "-q:v", "3", str(out)]
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=_FFMPEG_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True
    return False


def ensure_poster(wp: Wallpaper) -> Path | None:
    """A full-resolution still for places that cannot play video — the lock
    screen. Images and GIFs are their own poster."""
    if wp.kind == KIND_VIDEO:
        out = paths.POSTER_DIR / f"{_cache_key(wp)}.jpg"
        if out.exists():
            return out
        out.parent.mkdir(parents=True, exist_ok=True)
        return out if _ffmpeg_frame(Path(wp.source), out, None, None) else None
    return Path(wp.source)

"""High-resolution cover art for media mode.

Browsers hand MPRIS whatever artwork the page offered, and Firefox writes a
small copy of it to disk: YouTube comes through at 336×188, which is what made
media mode look pixelated. The page address (xesam:url) is in the metadata,
though, and from a YouTube video id the full 1280×720 thumbnail is one request
away.

The plugin cannot do this itself: Plasma's MPRIS QML model does not expose the
page address. So the media helper fetches the better image into a cache
directory, and the plugin looks for it under a name both sides can compute:

    ~/.cache/maze-wallpaper/hires/<md5(artUrl + "\\n" + title)>.jpg

(QML has Qt.md5, which hashes the same UTF-8 string the same way.)
"""
from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mazewallpaper.core import paths

HIRES_DIR = paths.CACHE_DIR / "hires"
_KEEP = 40
_TIMEOUT = 8
_MAX_BYTES = 8 * 1024 * 1024
_UA = "Mozilla/5.0 (X11; Linux x86_64) MazeWallpaper/1.0"

_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
# Spotify cover ids carry the size in their prefix: …1e02 is 300 px, …b273 is
# 640 px and …82c1 is the largest Spotify serves.
_SPOTIFY = re.compile(r"^(https://i\.scdn\.co/image/ab67616d)(00001e02|00004851|0000b273)([0-9a-f]+)$")


def cache_key(art_url: str, title: str) -> str:
    return hashlib.md5(f"{art_url}\n{title}".encode("utf-8")).hexdigest()


def cache_path(art_url: str, title: str) -> Path:
    return HIRES_DIR / f"{cache_key(art_url, title)}.jpg"


def youtube_id(page_url: str) -> str | None:
    try:
        u = urlparse(page_url)
    except ValueError:
        return None
    host = (u.hostname or "").lower()
    if host not in _YT_HOSTS:
        return None
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    elif u.path.startswith(("/shorts/", "/live/", "/embed/")):
        vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
    else:
        vid = (parse_qs(u.query).get("v") or [""])[0]
    return vid if _YT_ID.match(vid or "") else None


def candidates(art_url: str, page_url: str) -> list[str]:
    """Better images to try for this track, best first. Empty when there is
    nothing better than what the player already gave."""
    vid = youtube_id(page_url)
    if vid:
        base = f"https://i.ytimg.com/vi/{vid}"
        # maxres does not exist for every video (YouTube answers 404, or a
        # 120×90 grey placeholder for some); sd and hq always do.
        return [f"{base}/maxresdefault.jpg", f"{base}/sddefault.jpg", f"{base}/hqdefault.jpg"]
    m = _SPOTIFY.match(art_url)
    if m and m.group(2) != "82c1":
        return [f"{m.group(1)}000082c1{m.group(3)}", f"{m.group(1)}0000b273{m.group(3)}"]
    return []


def _download(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            if r.status != 200:
                return None
            data = r.read(_MAX_BYTES + 1)
            return data if len(data) <= _MAX_BYTES else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def fetch(art_url: str, title: str, page_url: str, min_width: int = 400) -> Path | None:
    """Download the best candidate into the cache. Returns its path, or None
    when nothing better exists. Runs on a worker thread (QImage only)."""
    from PyQt6.QtGui import QImage

    out = cache_path(art_url, title)
    if out.exists():
        return out
    for url in candidates(art_url, page_url):
        data = _download(url)
        if not data:
            continue
        img = QImage()
        if not img.loadFromData(data) or img.width() < min_width:
            continue   # YouTube's 120×90 "no thumbnail" placeholder lands here
        HIRES_DIR.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".part")
        if img.save(str(tmp), "JPG", 92):
            # The plugin polls for this name; it must never see half a file.
            tmp.replace(out)
            _prune()
            return out
    return None


def _prune() -> None:
    try:
        files = sorted(HIRES_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for old in files[_KEEP:]:
        old.unlink(missing_ok=True)

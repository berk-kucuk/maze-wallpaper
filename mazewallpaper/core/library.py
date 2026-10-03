"""The wallpaper library: what can be shown, and the user's own imports.

Two sources, merged into one list:

  system   Maze Linux's own KPackage wallpapers in /usr/share/wallpapers, plus
           anything the user installed into ~/.local/share/wallpapers
           (Plasma's "Get New Wallpapers")
  user     files the user imported, copied into ~/.local/share/maze-wallpaper/library

KDE's stock wallpapers (Next, Air, Horos…) share /usr/share/wallpapers with
Maze's; they are left out, since this is Maze's wallpaper app. Anyone who
wants one can still add the file themselves.

Every entry has a stable `id` so the app can remember which one is on screen
across restarts and rescans.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from mazewallpaper.core import paths

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".avif", ".jxl", ".tif", ".tiff"}
ANIMATED_EXTS = {".gif"}
VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".ogv"}
IMPORTABLE_EXTS = IMAGE_EXTS | ANIMATED_EXTS | VIDEO_EXTS

KIND_IMAGE = "image"
KIND_ANIMATED = "animated"
KIND_VIDEO = "video"

ORIGIN_SYSTEM = "system"
ORIGIN_USER = "user"


@dataclass(frozen=True)
class Wallpaper:
    id: str
    name: str
    kind: str      # image | animated | video
    source: str    # absolute path
    origin: str    # system | user

    @property
    def is_live(self) -> bool:
        return self.kind != KIND_IMAGE

    @property
    def removable(self) -> bool:
        return self.origin == ORIGIN_USER




def kind_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:
        return KIND_VIDEO
    if ext in ANIMATED_EXTS:
        return KIND_ANIMATED
    if ext in IMAGE_EXTS:
        return KIND_IMAGE
    return None


_SIZE_RE = re.compile(r"^(\d+)x(\d+)$")


def _best_package_image(images_dir: Path) -> Path | None:
    """Pick the file Plasma would: the largest landscape image in the package.

    KPackage wallpapers name their files by resolution ("2560x1440.png").
    Portrait variants exist for phones and are skipped unless nothing else is
    there. Animated files win over stills, since a package that bothers to ship
    a GIF means it.
    """
    best: tuple[int, Path] | None = None
    fallback: Path | None = None
    for f in images_dir.iterdir():
        if not f.is_file() or kind_for(f) is None:
            continue
        fallback = fallback or f
        m = _SIZE_RE.match(f.stem)
        w, h = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        if h > w:
            continue
        score = w * h + (10**12 if f.suffix.lower() in ANIMATED_EXTS else 0)
        if best is None or score > best[0]:
            best = (score, f)
    return best[1] if best else fallback


MAZE_AUTHOR = "Maze Linux"
# Only the system-wide directory is filtered; the user's own wallpaper
# directory is theirs and is shown whole.
_FILTERED_ROOTS = (Path("/usr/share/wallpapers"),)


def _package_meta(pkg: Path) -> dict:
    try:
        return json.loads((pkg / "metadata.json").read_text(encoding="utf-8")).get("KPlugin", {}) or {}
    except (OSError, ValueError, AttributeError):
        return {}


def _package_name(meta: dict, pkg: Path) -> str:
    return str(meta.get("Name") or pkg.name.replace("-", " "))


def is_maze_package(meta: dict) -> bool:
    """maze-branding marks every wallpaper with the author "Maze Linux"."""
    return any(isinstance(a, dict) and a.get("Name") == MAZE_AUTHOR
               for a in (meta.get("Authors") or []))


def scan_system(dirs=paths.SYSTEM_WALLPAPER_DIRS, filtered=_FILTERED_ROOTS) -> list[Wallpaper]:
    found: list[Wallpaper] = []
    seen: set[str] = set()
    for root in dirs:
        if not root.is_dir():
            continue
        maze_only = root in filtered
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir():
                images = entry / "contents" / "images"
                if not images.is_dir():
                    continue
                meta = _package_meta(entry)
                if maze_only and not is_maze_package(meta):
                    continue
                f = _best_package_image(images)
                name = _package_name(meta, entry)
            elif entry.is_file() and kind_for(entry) in (KIND_IMAGE, KIND_ANIMATED):
                if maze_only:
                    continue   # loose files carry no author; not Maze's
                f, name = entry, entry.stem
            else:
                continue
            if f is None:
                continue
            wid = f"system:{entry}"
            if wid in seen:
                continue
            seen.add(wid)
            found.append(Wallpaper(wid, name, kind_for(f), str(f), ORIGIN_SYSTEM))
    return found


def scan_user(library_dir: Path = paths.LIBRARY_DIR) -> list[Wallpaper]:
    if not library_dir.is_dir():
        return []
    out = []
    for f in sorted(library_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        kind = kind_for(f)
        if f.is_file() and kind:
            out.append(Wallpaper(f"user:{f.name}", _display_name(f), kind, str(f), ORIGIN_USER))
    return out


def _display_name(f: Path) -> str:
    return re.sub(r"[_\-]+", " ", f.stem).strip() or f.name


def scan_all() -> list[Wallpaper]:
    """User imports first (that is what someone opening the app just added),
    then the system packages."""
    return scan_user() + scan_system()


def _unique_target(library_dir: Path, name: str) -> Path:
    safe = re.sub(r"[^\w.\- ]+", "_", name).strip() or "wallpaper"
    target = library_dir / safe
    stem, suffix = target.stem, target.suffix
    n = 2
    while target.exists():
        target = library_dir / f"{stem} ({n}){suffix}"
        n += 1
    return target


def import_file(src: Path, library_dir: Path = paths.LIBRARY_DIR) -> Wallpaper:
    """Copy `src` into the library and return its entry.

    Raises ValueError for a file type the plugin cannot show, and OSError when
    the copy fails (disk full, unreadable source).
    """
    src = Path(src)
    kind = kind_for(src)
    if kind is None:
        raise ValueError(f"unsupported file type: {src.suffix or src.name}")
    if not src.is_file():
        raise FileNotFoundError(src)
    library_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_target(library_dir, src.name)
    shutil.copy2(src, target)
    return Wallpaper(f"user:{target.name}", _display_name(target), kind, str(target), ORIGIN_USER)


def remove(wp: Wallpaper, library_dir: Path = paths.LIBRARY_DIR) -> None:
    """Delete a user import. System packages are never touched."""
    if not wp.removable:
        raise PermissionError(f"{wp.id} is not a user wallpaper")
    path = Path(wp.source).resolve()
    if path.parent != library_dir.resolve():
        raise PermissionError(f"{path} is outside the library")
    path.unlink(missing_ok=True)

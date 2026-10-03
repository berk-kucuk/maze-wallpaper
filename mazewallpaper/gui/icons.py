"""The app mark, and the checkbox/radio glyphs Qt stylesheets cannot draw.

The glyph painting is Maze Cloak's: a stylesheet can only *fill* a checked
indicator, so the tick and dot are painted to PNGs it can reference.
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen

_ROOT = Path(__file__).resolve().parent.parent.parent
_SVG = _ROOT / "assets" / "maze-wallpaper.svg"

_cache_dir = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "maze-wallpaper"


def app_icon() -> QIcon:
    """The installed themed icon, or the in-tree SVG when run from a checkout."""
    themed = QIcon.fromTheme("maze-wallpaper")
    if not themed.isNull():
        return themed
    if _SVG.exists():
        return QIcon(str(_SVG))
    return QIcon.fromTheme("preferences-desktop-wallpaper")


def _glyph_path(name: str, theme: str) -> Path:
    return _cache_dir / f"{name}-{theme}.png"


def _paint_check(path: Path, colour: str, size: int = 16) -> None:
    scale = 3
    image = QImage(size * scale, size * scale, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(colour))
    pen.setWidthF(2.0 * scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    unit = size * scale
    stroke = QPainterPath()
    stroke.moveTo(unit * 0.24, unit * 0.52)
    stroke.lineTo(unit * 0.42, unit * 0.70)
    stroke.lineTo(unit * 0.77, unit * 0.31)
    painter.drawPath(stroke)
    painter.end()
    image.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                 Qt.TransformationMode.SmoothTransformation).save(str(path))


def _paint_dot(path: Path, colour: str, size: int = 15) -> None:
    scale = 3
    image = QImage(size * scale, size * scale, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(colour))
    unit = size * scale
    inset = unit * 0.30
    painter.drawEllipse(QRectF(inset, inset, unit - 2 * inset, unit - 2 * inset))
    painter.end()
    image.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                 Qt.TransformationMode.SmoothTransformation).save(str(path))


def ensure_control_glyphs(theme: str, on_accent: str) -> dict[str, str]:
    paths = {"check": _glyph_path("check", theme), "dot": _glyph_path("dot", theme)}
    try:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        if not paths["check"].exists():
            _paint_check(paths["check"], on_accent)
        if not paths["dot"].exists():
            _paint_dot(paths["dot"], on_accent)
    except OSError:
        return {"check": "", "dot": ""}
    return {k: v.as_posix() for k, v in paths.items()}

"""The app's own settings, in ~/.config/maze-wallpaper/settings.json.

`Behaviour` mirrors the plugin's kcfg keys one-to-one (see
plasma/.../contents/config/main.xml): the app keeps its own copy so the
choices survive switching to another wallpaper plugin and back.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

from mazewallpaper.core import paths

PAUSE_NEVER, PAUSE_MAXIMIZED, PAUSE_FOCUSED = 0, 1, 2
FILL_STRETCH, FILL_FIT, FILL_CROP = 0, 1, 2
MEDIA_BLURRED, MEDIA_FULL, MEDIA_OLED = 0, 1, 2
PLACE_WIDGET, PLACE_FULLSCREEN = 0, 1
CORNER_TOP_RIGHT, CORNER_TOP_LEFT, CORNER_BOTTOM_RIGHT, CORNER_BOTTOM_LEFT = range(4)

# Bumped when a default changes in a way existing users should get too.
#   2: blur 48 → 32 and dim 25 → 10 (dark Maze wallpapers went black);
#      language defaults to English.
SCHEMA = 2


@dataclass
class Behaviour:
    FillMode: int = FILL_CROP
    Muted: bool = True
    Volume: int = 50
    PlaybackRate: float = 1.0
    PauseMode: int = PAUSE_MAXIMIZED
    ActiveBlur: bool = True
    BlurRadius: int = 32
    ActiveDim: int = 10
    MediaMode: bool = False
    MediaPlacement: int = PLACE_WIDGET
    MediaCorner: int = CORNER_TOP_RIGHT
    MediaWidgetSize: int = 100
    MediaStyle: int = MEDIA_BLURRED
    MediaShowInfo: bool = True
    MediaLyrics: bool = False
    MediaOnlyPlaying: bool = False


@dataclass
class Settings:
    current_id: str = ""
    lock_screen: bool = False
    language: str = "en"
    theme: str = "dark"
    schema: int = SCHEMA
    behaviour: Behaviour = field(default_factory=Behaviour)
    # set by from_dict when an older file was upgraded; not saved
    migrated: bool = field(default=False, compare=False, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        """Unknown keys are dropped and missing ones defaulted, so an old or
        hand-edited file never stops the app from starting."""
        known = {f.name for f in fields(cls)} - {"behaviour", "migrated", "schema"}
        s = cls(**{k: v for k, v in data.items() if k in known})
        b = data.get("behaviour") or {}
        bknown = {f.name: f.type for f in fields(Behaviour)}
        defaults = Behaviour()
        for k, v in b.items():
            if k in bknown and type(v) is type(getattr(defaults, k)):
                setattr(s.behaviour, k, v)
            elif k == "PlaybackRate" and isinstance(v, int):
                s.behaviour.PlaybackRate = float(v)
        if data.get("schema", 1) < 2:
            s.behaviour.BlurRadius = defaults.BlurRadius
            s.behaviour.ActiveDim = defaults.ActiveDim
            s.language = "en"
        s.migrated = data.get("schema", 1) < SCHEMA
        s.schema = SCHEMA
        return s


def load() -> Settings:
    try:
        return Settings.from_dict(json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return Settings()


def save(s: Settings) -> None:
    paths.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.SETTINGS_FILE.with_suffix(".tmp")
    data = asdict(s)
    data.pop("migrated", None)
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(paths.SETTINGS_FILE)

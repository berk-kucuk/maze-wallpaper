"""What is playing right now, read over MPRIS.

Used only for the app's preview card. The wallpaper itself reads MPRIS
through Plasma's own model (org.kde.plasma.private.mpris), so the two pick the
same player in practice: a playing one before a paused one.
"""
from __future__ import annotations

from dataclasses import dataclass

_PREFIX = "org.mpris.MediaPlayer2."
_OBJ = "/org/mpris/MediaPlayer2"

_STATUS_RANK = {"Playing": 0, "Paused": 1}


@dataclass(frozen=True)
class NowPlaying:
    player: str        # bus name suffix, e.g. "spotify"
    status: str        # Playing | Paused | Stopped
    title: str
    artist: str
    album: str
    art_url: str
    url: str = ""      # xesam:url — the page or file being played

    @property
    def playing(self) -> bool:
        return self.status == "Playing"


def _player_label(bus_name: str) -> str:
    # "org.mpris.MediaPlayer2.firefox.instance_1_71" -> "firefox"
    return bus_name[len(_PREFIX):].split(".")[0]


def _from_props(bus_name: str, props: dict) -> NowPlaying | None:
    meta = props.get("Metadata") or {}
    if not isinstance(meta, dict):
        return None
    artist = meta.get("xesam:artist") or ""
    if isinstance(artist, (list, tuple)):
        artist = ", ".join(str(a) for a in artist)
    return NowPlaying(
        player=_player_label(bus_name),
        status=str(props.get("PlaybackStatus") or "Stopped"),
        title=str(meta.get("xesam:title") or ""),
        artist=str(artist),
        album=str(meta.get("xesam:album") or ""),
        art_url=str(meta.get("mpris:artUrl") or ""),
        url=str(meta.get("xesam:url") or ""),
    )


def pick(candidates: list[NowPlaying]) -> NowPlaying | None:
    """Playing beats paused beats stopped; Spotify wins a tie, since it is the
    player this feature is mostly for."""
    live = [c for c in candidates if c.status in _STATUS_RANK]
    if not live:
        return None
    return min(live, key=lambda c: (_STATUS_RANK[c.status], c.player != "spotify"))


def now_playing() -> NowPlaying | None:
    return pick(players())


def players() -> list[NowPlaying]:
    """Every MPRIS player on the session bus, whatever its state."""
    from PyQt6.QtDBus import QDBusConnection, QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return []
    reply = bus.interface().registeredServiceNames()
    if not reply.isValid():
        return []
    found = []
    for name in reply.value():
        if not name.startswith(_PREFIX):
            continue
        msg = QDBusMessage.createMethodCall(name, _OBJ, "org.freedesktop.DBus.Properties", "GetAll")
        msg.setArguments(["org.mpris.MediaPlayer2.Player"])
        r = bus.call(msg, timeout=800)
        args = r.arguments()
        if r.type() == QDBusMessage.MessageType.ReplyMessage and args and isinstance(args[0], dict):
            np = _from_props(name, args[0])
            if np:
                found.append(np)
    return found

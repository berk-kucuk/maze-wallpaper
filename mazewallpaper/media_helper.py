"""The media helper: a small background process that fetches high-resolution
covers for media mode (see core/hires.py for why the plugin needs it).

Started at login from /etc/xdg/autostart and by the app when media mode is
turned on. It only polls MPRIS while media mode is on, re-reading the setting
when settings.json changes, so with media mode off it is an idle timer.
"""
from __future__ import annotations

import sys
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from mazewallpaper.core import hires, media, paths, settings

SINGLETON = "maze-wallpaper-media-helper"
_POLL_MS = 1500
_IDLE_MS = 10000
_MAX_TRIES = 4


def already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SINGLETON)
    running = sock.waitForConnected(200)
    sock.disconnectFromServer()
    return running


class Helper:
    def __init__(self):
        self._settings_mtime = -1.0
        self._enabled = False
        self._done: set[str] = set()      # keys fetched or found to have nothing better
        self._busy: set[str] = set()
        # key -> (failures so far, monotonic time of the next allowed try)
        self._failed: dict[str, tuple[int, float]] = {}
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(0)

    def _reload_settings(self) -> None:
        try:
            mtime = paths.SETTINGS_FILE.stat().st_mtime
        except OSError:
            mtime = 0.0
        if mtime != self._settings_mtime:
            self._settings_mtime = mtime
            self._enabled = settings.load().behaviour.MediaMode

    def _tick(self) -> None:
        self._reload_settings()
        self._timer.setInterval(_POLL_MS if self._enabled else _IDLE_MS)
        if not self._enabled:
            return
        # Every player, not just the "best" one: Plasma decides which player
        # the wallpaper shows, and the cover must be ready whichever it picks.
        for np in media.players():
            if np.status not in ("Playing", "Paused") or not np.art_url and not np.url:
                continue
            key = hires.cache_key(np.art_url, np.title)
            if key in self._done or key in self._busy:
                continue
            _fails, not_before = self._failed.get(key, (0, 0.0))
            if time.monotonic() < not_before:
                continue
            if not hires.candidates(np.art_url, np.url):
                self._done.add(key)
                continue
            self._busy.add(key)
            self._fetch(key, np)

    def _fetch(self, key: str, np: media.NowPlaying) -> None:
        from mazewallpaper.gui.controller import run_async

        def done(result, key=key):
            self._busy.discard(key)
            if result is not None and not isinstance(result, Exception):
                self._done.add(key)
                self._failed.pop(key, None)
                return
            # Spotify publishes a new track's metadata in pieces and a network
            # can blip; one miss used to mean that song never got its cover.
            # Retry a few times, further apart each time, then give up.
            fails = self._failed.get(key, (0, 0.0))[0] + 1
            if fails >= _MAX_TRIES:
                self._done.add(key)
                self._failed.pop(key, None)
            else:
                self._failed[key] = (fails, time.monotonic() + 5 * 2 ** fails)

        run_async(hires.fetch, np.art_url, np.title, np.url, on_done=done)


def run() -> int:
    # QGuiApplication, not QCoreApplication: QImage decoding needs the GUI
    # module, but no window is ever shown.
    app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
    if already_running():
        return 0
    QLocalServer.removeServer(SINGLETON)
    server = QLocalServer()
    server.listen(SINGLETON)
    helper = Helper()  # noqa: F841 — kept alive by this frame
    return app.exec()

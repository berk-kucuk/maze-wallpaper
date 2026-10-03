"""Glue between the widgets and the core.

Everything slow — copying a 500 MB video into the library, running ffmpeg for
a thumbnail — happens on the global QThreadPool, and comes back to the GUI
thread as a signal.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import (
    QObject, QProcess, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot,
)

from mazewallpaper import PLUGIN_ID
from mazewallpaper.core import library, paths, plasma, settings, thumbs
from mazewallpaper.core.library import Wallpaper
from mazewallpaper.gui.i18n import t as _t


class _Signals(QObject):
    done = pyqtSignal(object)


class _Task(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args)
        except Exception as e:  # reported to the user, never lost silently
            result = e
        self.signals.done.emit(result)


class _Relay(QObject):
    """Lives in the GUI thread, so the worker's signal reaches it queued and
    `callback` runs where widgets may be touched. Connecting the signal to a
    plain function would run it on the worker thread instead."""

    def __init__(self, callback, signals: _Signals):
        super().__init__()
        self.callback = callback
        self.signals = signals          # kept alive until delivery
        signals.done.connect(self.deliver)

    @pyqtSlot(object)
    def deliver(self, result) -> None:
        _pending.discard(self)
        if self.callback:
            self.callback(result)


_pending: set[_Relay] = set()


def run_async(fn, *args, on_done=None) -> None:
    task = _Task(fn, *args)
    _pending.add(_Relay(on_done, task.signals))
    QThreadPool.globalInstance().start(task)


def plugin_installed() -> bool:
    for root in (Path("/usr/share/plasma/wallpapers"), paths.DATA_DIR.parent / "plasma" / "wallpapers"):
        if (root / PLUGIN_ID / "metadata.json").exists():
            return True
    return False


_MAIN_PY = Path(__file__).resolve().parent.parent.parent / "main.py"


def ensure_media_helper() -> None:
    """Start the high-res cover helper unless it is already running. It is
    autostarted at login; this covers turning media mode on mid-session."""
    from mazewallpaper.media_helper import already_running

    if not already_running():
        QProcess.startDetached(sys.executable, [str(_MAIN_PY), "--media-helper"])


def _import_many(files: list[str]) -> tuple[list[Wallpaper], list[tuple[str, str]]]:
    added, failed = [], []
    for f in files:
        try:
            wp = library.import_file(Path(f))
            thumbs.ensure_thumb(wp)
            added.append(wp)
        except Exception as e:
            failed.append((Path(f).name, str(e)))
    return added, failed


class Controller(QObject):
    library_changed = pyqtSignal()
    current_changed = pyqtSignal(str)        # wallpaper id ("" if not ours)
    behaviour_changed = pyqtSignal()
    language_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    thumb_ready = pyqtSignal(str, str)       # wallpaper id, thumbnail path
    message = pyqtSignal(str, bool)          # text, is_error
    lock_changed = pyqtSignal(bool)
    imported = pyqtSignal(str)               # id of the first file added

    def __init__(self):
        super().__init__()
        paths.ensure_dirs()
        self.settings = settings.load()
        self.items: list[Wallpaper] = []
        self._by_id: dict[str, Wallpaper] = {}
        self._thumbs_requested: set[str] = set()

        # Behaviour sliders fire on every pixel of a drag; Plasma gets the
        # final value only.
        self._push_timer = QTimer(self)
        self._push_timer.setSingleShot(True)
        self._push_timer.setInterval(250)
        self._push_timer.timeout.connect(self._push_behaviour)

        self.rescan()
        self.sync_current()
        if self.settings.behaviour.MediaMode:
            ensure_media_helper()
        if self.settings.migrated:
            # New defaults (gentler blur) reach the desktop without the user
            # having to touch a slider.
            settings.save(self.settings)
            QTimer.singleShot(0, self._push_behaviour)

    # ── i18n ──────────────────────────────────────────────────────────────

    def t(self, key: str, **fmt) -> str:
        return _t(key, self.settings.language, **fmt)

    def set_language(self, lang: str) -> None:
        if lang != self.settings.language:
            self.settings.language = lang
            settings.save(self.settings)
            self.language_changed.emit(lang)

    def set_theme(self, theme: str) -> None:
        if theme != self.settings.theme:
            self.settings.theme = theme
            settings.save(self.settings)
            self.theme_changed.emit(theme)

    # ── library ───────────────────────────────────────────────────────────

    def rescan(self) -> None:
        self.items = library.scan_all()
        self._by_id = {w.id: w for w in self.items}
        self.library_changed.emit()

    def get(self, wid: str) -> Wallpaper | None:
        return self._by_id.get(wid)

    def current_wallpaper(self) -> Wallpaper | None:
        return self._by_id.get(self.settings.current_id)

    def request_thumb(self, wp: Wallpaper) -> str | None:
        """Cached path now, or None and a thumb_ready signal later."""
        cached = thumbs.thumb_path(wp)
        if cached.exists():
            return str(cached)
        if wp.id in self._thumbs_requested:
            return None
        self._thumbs_requested.add(wp.id)

        def done(result, wid=wp.id):
            if isinstance(result, Path):
                self.thumb_ready.emit(wid, str(result))

        run_async(thumbs.ensure_thumb, wp, on_done=done)
        return None

    def import_files(self, files: list[str]) -> None:
        good = [f for f in files if library.kind_for(Path(f))]
        for f in files:
            if f not in good:
                self.message.emit(self.t("unsupported", name=Path(f).name), True)
        if not good:
            return
        self.message.emit(self.t("importing", n=len(good)), False)

        def done(result):
            if isinstance(result, Exception):
                self.message.emit(self.t("import_failed", name="", err=result), True)
                return
            added, failed = result
            for name, err in failed:
                self.message.emit(self.t("import_failed", name=name, err=err), True)
            if added:
                self.rescan()
                self.imported.emit(added[0].id)
                self.message.emit(self.t("imported", n=len(added)), False)

        run_async(_import_many, good, on_done=done)

    def remove(self, wp: Wallpaper) -> None:
        try:
            library.remove(wp)
        except OSError as e:
            self.message.emit(str(e), True)
            return
        self.rescan()
        self.message.emit(self.t("removed"), False)

    # ── desktop ───────────────────────────────────────────────────────────

    @property
    def current_id(self) -> str:
        return self.settings.current_id

    def sync_current(self) -> None:
        """Ask Plasma what is really on the desktop — the user may have
        changed it from Plasma's own dialog since the app last ran."""
        cur = plasma.read_current()
        wid = ""
        if cur.ours:
            for w in self.items:
                if w.kind == cur.kind and w.source == cur.source:
                    wid = w.id
                    break
        elif not cur.plugin:
            wid = self.settings.current_id  # Plasma not reachable; trust our record
        if wid != self.settings.current_id:
            self.settings.current_id = wid
            settings.save(self.settings)
        self.current_changed.emit(wid)

    def apply(self, wp: Wallpaper) -> None:
        if not plugin_installed():
            self.message.emit(self.t("plugin_missing"), True)
            return
        try:
            n = plasma.apply(wp, self.settings.behaviour)
        except plasma.PlasmaError as e:
            self.message.emit(self.t("plasma_error", err=e), True)
            return
        self.settings.current_id = wp.id
        settings.save(self.settings)
        self.current_changed.emit(wp.id)

        if self.settings.lock_screen:
            def done(poster):
                if isinstance(poster, Path):
                    try:
                        plasma.apply_lock_screen(poster)
                        self.message.emit(self.t("applied_lock"), False)
                        return
                    except (plasma.PlasmaError, OSError) as e:
                        self.message.emit(self.t("plasma_error", err=e), True)
                        return
                self.message.emit(self.t("no_ffmpeg"), True)
            run_async(thumbs.ensure_poster, wp, on_done=done)
        else:
            self.message.emit(self.t("applied", n=max(1, n)), False)

    def set_lock_screen(self, on: bool) -> None:
        if on == self.settings.lock_screen:
            return
        self.settings.lock_screen = on
        settings.save(self.settings)
        self.lock_changed.emit(on)

    # ── behaviour ─────────────────────────────────────────────────────────

    @property
    def behaviour(self) -> settings.Behaviour:
        return self.settings.behaviour

    def set_behaviour(self, **changes) -> None:
        new = replace(self.settings.behaviour, **changes)
        if new == self.settings.behaviour:
            return
        self.settings.behaviour = new
        settings.save(self.settings)
        self.behaviour_changed.emit()
        self._push_timer.start()
        if new.MediaMode:
            ensure_media_helper()

    def _push_behaviour(self) -> None:
        if not self.settings.current_id:
            return  # nothing of ours on the desktop to update
        try:
            plasma.push_behaviour(self.settings.behaviour)
        except plasma.PlasmaError as e:
            self.message.emit(self.t("plasma_error", err=e), True)

"""The right-hand panel: a live preview of the selected wallpaper and what can
be done with it.

The preview plays the real thing — the video or the GIF the plugin will
run — not a thumbnail, so what you see is what lands on the
desktop. Playback stops whenever the panel is hidden.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QMovie, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from mazewallpaper.core.settings import PLACE_FULLSCREEN, PLACE_WIDGET
from mazewallpaper.core.library import (
    KIND_ANIMATED, KIND_VIDEO, Wallpaper,
)

class _Ratio(QWidget):
    """Keeps its child at 16:9 for whatever width the panel has."""

    def __init__(self, child: QWidget):
        super().__init__()
        self._child = child
        child.setParent(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return int(w * 9 / 16)

    def sizeHint(self) -> QSize:
        return QSize(340, 191)

    def resizeEvent(self, e) -> None:
        self._child.setGeometry(0, 0, self.width(), int(self.width() * 9 / 16))


class PreviewPanel(QFrame):
    apply_requested = pyqtSignal(object)
    remove_requested = pyqtSignal(object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._c = controller
        self._wp: Wallpaper | None = None
        self._player = None
        self._video_widget = None
        self._movie: QMovie | None = None
        self._image_source: QPixmap | None = None

        self.setObjectName("preview_panel")
        self.setFixedWidth(380)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        box = QFrame()
        box.setObjectName("preview_box")
        box_lay = QVBoxLayout(box)
        box_lay.setContentsMargins(1, 1, 1, 1)
        self._stack = QStackedWidget()
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet("background: #000; border-radius: 9px;")
        self._image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._stack.addWidget(self._image)
        box_lay.addWidget(self._stack)
        lay.addWidget(_Ratio(box))

        self._name = QLabel()
        self._name.setObjectName("title")
        self._name.setWordWrap(True)
        lay.addWidget(self._name)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        self._badge = QLabel()
        self._badge.setObjectName("badge")
        meta.addWidget(self._badge)
        self._origin = QLabel()
        self._origin.setObjectName("meta")
        meta.addWidget(self._origin)
        meta.addStretch()
        lay.addLayout(meta)

        self._details = QLabel()
        self._details.setObjectName("hint")
        self._details.setWordWrap(True)
        lay.addWidget(self._details)

        lay.addSpacing(6)

        fill_row = QHBoxLayout()
        fill_lbl = QLabel(controller.t("fill"))
        fill_lbl.setObjectName("meta")
        fill_row.addWidget(fill_lbl)
        fill_row.addStretch()
        self._fill = QComboBox()
        for key in ("fill_stretch", "fill_fit", "fill_crop"):
            self._fill.addItem(controller.t(key))
        self._fill.setCurrentIndex(controller.behaviour.FillMode)
        self._fill.currentIndexChanged.connect(lambda i: controller.set_behaviour(FillMode=i))
        fill_row.addWidget(self._fill)
        lay.addLayout(fill_row)

        self._lock = QCheckBox(controller.t("also_lock"))
        self._lock.setChecked(controller.settings.lock_screen)
        self._lock.toggled.connect(controller.set_lock_screen)
        lay.addWidget(self._lock)

        # Media as a widget over *this* wallpaper, one click from where the
        # wallpaper is chosen. The Media tab has the details (corner, size).
        media_card = QFrame()
        media_card.setObjectName("card")
        ml = QVBoxLayout(media_card)
        ml.setContentsMargins(14, 12, 14, 12)
        ml.setSpacing(4)
        self._media = QCheckBox(controller.t("quick_widget"))
        self._media.toggled.connect(self._on_media)
        ml.addWidget(self._media)
        mh = QLabel(controller.t("quick_widget_hint"))
        mh.setObjectName("hint")
        mh.setWordWrap(True)
        ml.addWidget(mh)
        lay.addSpacing(4)
        lay.addWidget(media_card)

        lay.addStretch()

        self._note = QLabel(controller.t("live_preview_note"))
        self._note.setObjectName("hint")
        self._note.setWordWrap(True)
        lay.addWidget(self._note)

        self._apply = QPushButton()
        self._apply.setObjectName("primary")
        self._apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply.clicked.connect(lambda: self._wp and self.apply_requested.emit(self._wp))
        lay.addWidget(self._apply)

        row = QHBoxLayout()
        self._show_file = QPushButton(controller.t("btn_show_file"))
        self._show_file.clicked.connect(self._open_folder)
        row.addWidget(self._show_file)
        self._remove = QPushButton(controller.t("btn_remove"))
        self._remove.setObjectName("danger")
        self._remove.clicked.connect(lambda: self._wp and self.remove_requested.emit(self._wp))
        row.addWidget(self._remove)
        lay.addLayout(row)

        controller.current_changed.connect(lambda _w: self._update_apply())
        controller.lock_changed.connect(self._sync_lock)
        controller.behaviour_changed.connect(self._sync_media)
        self._sync_media()
        controller.thumb_ready.connect(self._on_thumb)
        self.show_wallpaper(None)

    # ── public ────────────────────────────────────────────────────────────

    def show_wallpaper(self, wp: Wallpaper | None) -> None:
        self._stop()
        self._wp = wp
        has = wp is not None
        for w in (self._badge, self._origin, self._apply, self._show_file, self._fill, self._lock):
            w.setEnabled(has)
        if not has:
            self._name.setText(self._c.t("nothing_selected"))
            self._badge.hide()
            self._origin.clear()
            self._details.clear()
            self._image.clear()
            self._note.hide()
            self._remove.hide()
            self._update_apply()
            return

        self._name.setText(wp.name)
        self._badge.setText(self._c.t(f"kind_{wp.kind}"))
        self._badge.show()
        self._origin.setText(self._c.t(f"origin_{wp.origin}"))
        self._details.setText(self._describe(wp))
        self._remove.setVisible(wp.removable)
        self._note.setVisible(wp.is_live)
        self._update_apply()
        self._start(wp)

    def pause(self) -> None:
        self._stop()

    def resume(self) -> None:
        if self._wp is not None:
            self._start(self._wp)

    # ── playback ──────────────────────────────────────────────────────────

    def _start(self, wp: Wallpaper) -> None:
        if not self.isVisible():
            self._show_thumb(wp)
            return
        if wp.kind == KIND_VIDEO and self._start_video(wp):
            return
        if wp.kind == KIND_ANIMATED:
            movie = QMovie(wp.source)
            if movie.isValid():
                self._movie = movie
                movie.frameChanged.connect(self._on_movie_frame)
                movie.start()
                self._stack.setCurrentWidget(self._image)
                return
        if wp.kind == KIND_VIDEO:
            self._show_thumb(wp)
            return
        pm = QPixmap(wp.source)
        self._set_pixmap(pm if not pm.isNull() else None, wp)

    def _show_thumb(self, wp: Wallpaper) -> None:
        path = self._c.request_thumb(wp)
        self._set_pixmap(QPixmap(path) if path else None, wp)

    def _set_pixmap(self, pm: QPixmap | None, wp: Wallpaper | None = None) -> None:
        self._stack.setCurrentWidget(self._image)
        if pm is None or pm.isNull():
            self._image.clear()
            self._image_source = None
            return
        self._image_source = pm
        self._rescale()

    def _rescale(self) -> None:
        pm = self._image_source
        if pm is None:
            return
        size = self._image.size()
        scaled = pm.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - size.width()) // 2
        y = (scaled.height() - size.height()) // 2
        self._image.setPixmap(scaled.copy(x, y, size.width(), size.height()))

    def _on_movie_frame(self, _n: int) -> None:
        if self._movie:
            self._image_source = self._movie.currentPixmap()
            self._rescale()

    def _start_video(self, wp: Wallpaper) -> bool:
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        except ImportError:
            return False
        if self._video_widget is None:
            self._video_widget = QVideoWidget()
            self._video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            self._video_widget.setStyleSheet("background: #000;")
            self._stack.addWidget(self._video_widget)
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._audio.setMuted(True)   # previews are always silent
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video_widget)
            self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._player.setSource(QUrl.fromLocalFile(wp.source))
        self._stack.setCurrentWidget(self._video_widget)
        self._player.play()
        return True

    def _stop(self) -> None:
        if self._movie:
            self._movie.stop()
            self._movie = None
        if self._player:
            self._player.stop()
            self._player.setSource(QUrl())

    def _on_thumb(self, wid: str, path: str) -> None:
        if self._wp and self._wp.id == wid and self._stack.currentWidget() is self._image \
                and self._movie is None and self._wp.kind == KIND_VIDEO:
            self._set_pixmap(QPixmap(path), self._wp)

    # ── chrome ────────────────────────────────────────────────────────────

    def _on_media(self, on: bool) -> None:
        if on:
            self._c.set_behaviour(MediaMode=True, MediaPlacement=PLACE_WIDGET)
        else:
            self._c.set_behaviour(MediaMode=False)

    def _sync_media(self) -> None:
        b = self._c.behaviour
        self._media.blockSignals(True)
        self._media.setChecked(b.MediaMode and b.MediaPlacement != PLACE_FULLSCREEN)
        self._media.blockSignals(False)

    def _sync_lock(self, on: bool) -> None:
        self._lock.blockSignals(True)
        self._lock.setChecked(on)
        self._lock.blockSignals(False)

    def _describe(self, wp: Wallpaper) -> str:
        p = Path(wp.source)
        try:
            size = p.stat().st_size
        except OSError:
            return p.name
        mb = size / (1024 * 1024)
        human = f"{mb:.1f} MB" if mb >= 1 else f"{size / 1024:.0f} KB"
        return f"{p.name}  ·  {human}"

    def _update_apply(self) -> None:
        on = self._wp is not None and self._wp.id == self._c.current_id
        self._apply.setText(self._c.t("btn_applied" if on else "btn_apply"))

    def _open_folder(self) -> None:
        if self._wp:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._wp.source).parent)))

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._rescale()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.resume()

    def hideEvent(self, e) -> None:
        super().hideEvent(e)
        self._stop()

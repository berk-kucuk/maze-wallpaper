"""The Settings tab: how live wallpapers behave, sound, active blur, lock
screen, and the app itself."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGraphicsBlurEffect, QGraphicsPixmapItem,
    QGraphicsScene, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from mazewallpaper.core import paths

_SPEEDS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
_PREVIEW_W, _PREVIEW_H = 384, 216


def render_active_blur(wall: QPixmap, radius: int, dim: int, w: int, h: int) -> QPixmap:
    """What the plugin draws while a window has focus: the wallpaper blurred
    by `radius` screen pixels (scaled to the preview) under a `dim`% black
    veil — the same two steps as main.qml."""
    pad = 24
    base = wall.scaled(w + 2 * pad, h + 2 * pad, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                       Qt.TransformationMode.SmoothTransformation)
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(base)
    if radius > 0:
        eff = QGraphicsBlurEffect()
        eff.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        eff.setBlurRadius(radius * w / 1920)
        item.setGraphicsEffect(eff)
    scene.addItem(item)
    img = QImage(base.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("black"))
    p = QPainter(img)
    scene.render(p, QRectF(img.rect()), QRectF(0, 0, base.width(), base.height()))
    p.fillRect(img.rect(), QColor(0, 0, 0, round(255 * dim / 100)))
    p.end()
    x = (img.width() - w) // 2
    y = (img.height() - h) // 2
    return QPixmap.fromImage(img.copy(x, y, w, h))


def _slider(lo: int, hi: int, step: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setPageStep(step * 2)
    s.setValue(value)
    s.setMinimumWidth(220)
    return s


class SettingsView(QScrollArea):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._c = controller
        b = controller.behaviour
        t = controller.t

        self.setWidgetResizable(True)
        body = QWidget()
        self.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(28, 12, 28, 28)
        outer.setSpacing(6)

        def group(title: str) -> QGridLayout:
            g = QGroupBox(title)
            g.setMaximumWidth(760)
            lay = QGridLayout(g)
            lay.setHorizontalSpacing(18)
            lay.setVerticalSpacing(12)
            lay.setColumnStretch(1, 1)
            lay.setColumnMinimumWidth(0, 200)   # one label column across every group
            outer.addWidget(g)
            return lay

        def label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("meta")
            return lbl

        def hint(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("hint")
            lbl.setWordWrap(True)
            return lbl

        # ── performance ───────────────────────────────────────────────────
        g = group(t("grp_performance"))
        g.addWidget(label(t("pause_label")), 0, 0)
        self._pause = QComboBox()
        for key in ("pause_never", "pause_maximized", "pause_focused"):
            self._pause.addItem(t(key))
        self._pause.setCurrentIndex(b.PauseMode)
        self._pause.currentIndexChanged.connect(lambda i: controller.set_behaviour(PauseMode=i))
        g.addWidget(self._pause, 0, 1, Qt.AlignmentFlag.AlignLeft)
        g.addWidget(hint(t("pause_hint")), 1, 0, 1, 2)
        g.addWidget(label(t("speed_label")), 2, 0)
        self._speed = QComboBox()
        for s in _SPEEDS:
            self._speed.addItem(f"{s:g}×", s)
        idx = min(range(len(_SPEEDS)), key=lambda i: abs(_SPEEDS[i] - b.PlaybackRate))
        self._speed.setCurrentIndex(idx)
        self._speed.currentIndexChanged.connect(
            lambda i: controller.set_behaviour(PlaybackRate=float(_SPEEDS[i])))
        g.addWidget(self._speed, 2, 1, Qt.AlignmentFlag.AlignLeft)

        # ── sound ─────────────────────────────────────────────────────────
        g = group(t("grp_sound"))
        self._mute = QCheckBox(t("mute"))
        self._mute.setChecked(b.Muted)
        g.addWidget(self._mute, 0, 0, 1, 2)
        g.addWidget(label(t("volume")), 1, 0)
        self._volume = _slider(0, 100, 5, b.Volume)
        self._volume.setEnabled(not b.Muted)
        self._volume.valueChanged.connect(lambda v: controller.set_behaviour(Volume=v))
        g.addWidget(self._volume, 1, 1)

        def on_mute(on: bool) -> None:
            self._volume.setEnabled(not on)
            controller.set_behaviour(Muted=on)
        self._mute.toggled.connect(on_mute)

        # ── active blur ───────────────────────────────────────────────────
        g = group(t("grp_blur"))
        self._blur = QCheckBox(t("active_blur"))
        self._blur.setChecked(b.ActiveBlur)
        g.addWidget(self._blur, 0, 0, 1, 2)
        g.addWidget(label(t("blur_strength")), 1, 0)
        self._radius = _slider(8, 64, 4, b.BlurRadius)
        self._radius.valueChanged.connect(lambda v: controller.set_behaviour(BlurRadius=v))
        g.addWidget(self._radius, 1, 1)
        g.addWidget(label(t("dim")), 2, 0)
        self._dim = _slider(0, 80, 5, b.ActiveDim)
        self._dim.valueChanged.connect(lambda v: controller.set_behaviour(ActiveDim=v))
        g.addWidget(self._dim, 2, 1)

        self._blur_preview = QLabel()
        self._blur_preview.setFixedSize(_PREVIEW_W, _PREVIEW_H)
        self._blur_preview.setStyleSheet("border-radius: 8px; background: #000;")
        g.addWidget(self._blur_preview, 3, 0, 1, 2)
        g.addWidget(hint(t("blur_preview")), 4, 0, 1, 2)
        self._radius.valueChanged.connect(lambda _v: self._render_blur())
        self._dim.valueChanged.connect(lambda _v: self._render_blur())

        def on_blur(on: bool) -> None:
            self._radius.setEnabled(on)
            self._dim.setEnabled(on)
            controller.set_behaviour(ActiveBlur=on)
            self._render_blur()
        self._blur.toggled.connect(on_blur)
        self._radius.setEnabled(b.ActiveBlur)
        self._dim.setEnabled(b.ActiveBlur)
        controller.current_changed.connect(lambda _w: self._render_blur())
        controller.thumb_ready.connect(lambda _id, _p: self._render_blur())

        # ── lock screen ───────────────────────────────────────────────────
        g = group(t("grp_lock"))
        self._lock = QCheckBox(t("also_lock"))
        self._lock.setChecked(controller.settings.lock_screen)
        self._lock.toggled.connect(controller.set_lock_screen)
        g.addWidget(self._lock, 0, 0, 1, 2)
        g.addWidget(hint(t("lock_hint")), 1, 0, 1, 2)

        # ── app ───────────────────────────────────────────────────────────
        g = group(t("grp_app"))
        g.addWidget(label(t("language")), 0, 0)
        self._lang = QComboBox()
        self._lang.addItem("English", "en")
        self._lang.addItem("Türkçe", "tr")
        self._lang.setCurrentIndex(max(0, self._lang.findData(controller.settings.language)))
        self._lang.currentIndexChanged.connect(lambda _i: controller.set_language(self._lang.currentData()))
        g.addWidget(self._lang, 0, 1, Qt.AlignmentFlag.AlignLeft)
        g.addWidget(label(t("theme")), 1, 0)
        self._theme = QComboBox()
        self._theme.addItem(t("theme_dark"), "dark")
        self._theme.addItem(t("theme_light"), "light")
        self._theme.setCurrentIndex(max(0, self._theme.findData(controller.settings.theme)))
        self._theme.currentIndexChanged.connect(lambda _i: controller.set_theme(self._theme.currentData()))
        g.addWidget(self._theme, 1, 1, Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout()
        lib = QPushButton(t("open_library"))
        lib.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.LIBRARY_DIR))))
        row.addWidget(lib)
        row.addStretch()
        g.addLayout(row, 2, 0, 1, 2)

        outer.addStretch()

        # The lock-screen box also lives on the preview panel; keep both honest.
        controller.lock_changed.connect(self._sync_lock)

    def _render_blur(self) -> None:
        wp = self._c.current_wallpaper()
        path = self._c.request_thumb(wp) if wp else None
        wall = QPixmap(path) if path else QPixmap()
        if wall.isNull():
            self._blur_preview.clear()
            return
        on = self._blur.isChecked()
        self._blur_preview.setPixmap(render_active_blur(
            wall, self._radius.value() if on else 0, self._dim.value() if on else 0,
            _PREVIEW_W, _PREVIEW_H))

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._render_blur()

    def _sync_lock(self, on: bool) -> None:
        self._lock.blockSignals(True)
        self._lock.setChecked(on)
        self._lock.blockSignals(False)

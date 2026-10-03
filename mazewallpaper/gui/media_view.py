"""The Media tab: turn media mode on, see what is playing, choose where it
shows — as a card in a corner of your wallpaper, or full screen.

Every preview here is drawn from the real thing: your current wallpaper and
the cover that is playing right now, so choosing is choosing between pictures
of your own desktop.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from mazewallpaper.core import media
from mazewallpaper.core.settings import (
    CORNER_BOTTOM_LEFT, CORNER_BOTTOM_RIGHT, CORNER_TOP_LEFT, CORNER_TOP_RIGHT,
    MEDIA_BLURRED, MEDIA_FULL, MEDIA_OLED, PLACE_FULLSCREEN, PLACE_WIDGET,
)
from mazewallpaper.gui.theme import ACTIVE_COLOR

_POLL_MS = 2000
_PREVIEW = QSize(320, 180)


# ── drawing helpers ──────────────────────────────────────────────────────────

def _placeholder_cover(size: int = 512) -> QPixmap:
    pm = QPixmap(size, size)
    p = QPainter(pm)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#3a3a3a"))
    g.setColorAt(1, QColor("#121212"))
    p.fillRect(0, 0, size, size, g)
    p.setPen(QColor("#6a6a6a"))
    f = QFont()
    f.setPixelSize(size // 3)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "♪")
    p.end()
    return pm


def _placeholder_wall(w: int, h: int) -> QPixmap:
    pm = QPixmap(w, h)
    p = QPainter(pm)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#141414"))
    g.setColorAt(1, QColor("#050505"))
    p.fillRect(0, 0, w, h, g)
    p.end()
    return pm


def _crop_fill(pm: QPixmap, w: int, h: int) -> QPixmap:
    s = pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                  Qt.TransformationMode.SmoothTransformation)
    return s.copy((s.width() - w) // 2, (s.height() - h) // 2, w, h)


def _cheap_blur(pm: QPixmap, w: int, h: int, detail: int = 16) -> QPixmap:
    # Down to a few pixels and back up with smoothing: a convincing blur at
    # card size for no cost.
    tiny = _crop_fill(pm, detail, max(1, detail * h // w))
    return tiny.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)


def _rounded(p: QPainter, pm: QPixmap, r: QRectF, radius: float) -> None:
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    p.save()
    p.setClipPath(path)
    p.drawPixmap(r.toRect(), _crop_fill(pm, int(r.width()), int(r.height())))
    p.restore()


def render_fullscreen(style: int, cover: QPixmap, w: int, h: int) -> QPixmap:
    out = QPixmap(w, h)
    out.fill(QColor("black"))
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if style == MEDIA_BLURRED:
        p.drawPixmap(0, 0, _cheap_blur(cover, w, h))
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 90))
    elif style == MEDIA_FULL:
        p.drawPixmap(0, 0, _crop_fill(cover, w, h))
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 40))
    p.setPen(Qt.PenStyle.NoPen)
    if style != MEDIA_FULL:
        side = int(h * 0.5)
        r = QRectF((w - side) / 2, h * 0.16, side, side)
        _rounded(p, cover, r, 4)
        p.setBrush(QColor(240, 240, 240, 200))
        p.drawRoundedRect(QRectF(w / 2 - w * 0.16, r.bottom() + h * 0.06, w * 0.32, h * 0.04), 2, 2)
        p.setBrush(QColor(154, 154, 154, 160))
        p.drawRoundedRect(QRectF(w / 2 - w * 0.11, r.bottom() + h * 0.13, w * 0.22, h * 0.03), 2, 2)
    else:
        p.setBrush(QColor(240, 240, 240, 220))
        p.drawRoundedRect(QRectF(w * 0.06, h * 0.74, w * 0.34, h * 0.05), 2, 2)
        p.setBrush(QColor(154, 154, 154, 180))
        p.drawRoundedRect(QRectF(w * 0.06, h * 0.82, w * 0.22, h * 0.035), 2, 2)
    p.end()
    return out


def render_widget(wall: QPixmap, cover: QPixmap, corner: int, size_pct: int,
                  w: int, h: int) -> QPixmap:
    """The corner card over the wallpaper — the same proportions as
    MediaWidget.qml, scaled to the preview."""
    out = _crop_fill(wall, w, h)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    unit = h / 1080 * size_pct / 100
    cw, ch = 430 * unit, 132 * unit
    floor = 28 * h / 1080        # MediaWidget's 28 px minimum, at preview scale
    mx, my = max(floor, 48 * unit), max(floor, 64 * unit)
    left = corner in (CORNER_TOP_LEFT, CORNER_BOTTOM_LEFT)
    bottom = corner in (CORNER_BOTTOM_RIGHT, CORNER_BOTTOM_LEFT)
    x = mx if left else w - cw - mx
    y = h - ch - my if bottom else my
    card = QRectF(x, y, cw, ch)
    radius = 20 * unit

    # glass: the wallpaper under the card, blurred and tinted
    under = out.copy(card.toRect())
    path = QPainterPath()
    path.addRoundedRect(card, radius, radius)
    p.save()
    p.setClipPath(path)
    p.drawPixmap(card.toRect(), _cheap_blur(under, max(1, int(cw)), max(1, int(ch)), 8))
    p.fillRect(card, QColor(10, 10, 10, 150))
    p.restore()
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)

    side = 100 * unit
    cover_r = QRectF(x + 16 * unit, y + (ch - side) / 2, side, side)
    _rounded(p, cover, cover_r, 12 * unit)
    tx = cover_r.right() + 16 * unit
    tw = card.right() - 20 * unit - tx
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 230, 118))
    p.drawRoundedRect(QRectF(tx, y + ch * 0.22, tw * 0.12, ch * 0.06), 1, 1)
    p.setBrush(QColor(245, 245, 245, 230))
    p.drawRoundedRect(QRectF(tx, y + ch * 0.38, tw * 0.62, ch * 0.10), 2, 2)
    p.setBrush(QColor(176, 176, 176, 200))
    p.drawRoundedRect(QRectF(tx, y + ch * 0.56, tw * 0.42, ch * 0.07), 2, 2)
    p.setBrush(QColor(255, 255, 255, 40))
    p.drawRoundedRect(QRectF(tx, y + ch * 0.76, tw, ch * 0.03), 1, 1)
    p.setBrush(QColor(240, 240, 240))
    p.drawRoundedRect(QRectF(tx, y + ch * 0.76, tw * 0.42, ch * 0.03), 1, 1)
    p.end()
    return out


# ── widgets ──────────────────────────────────────────────────────────────────

class _ChoiceCard(QFrame):
    """A picture with a title under it; clicking selects it."""
    clicked = pyqtSignal(int)

    def __init__(self, value: int, title: str, subtitle: str = "", size: QSize = _PREVIEW):
        super().__init__()
        self.value = value
        self.setObjectName("style_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(6)
        self.image = QLabel()
        self.image.setFixedSize(size)
        lay.addWidget(self.image)
        t = QLabel(title)
        t.setStyleSheet("font-weight: bold;")
        lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("hint")
            s.setWordWrap(True)
            s.setMaximumWidth(size.width())
            lay.addWidget(s)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.value)
        super().mouseReleaseEvent(e)


class MediaView(QScrollArea):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._c = controller
        t = controller.t
        self._cover = _placeholder_cover()
        self._cover_url = ""
        self._wall: QPixmap | None = None
        self._np: media.NowPlaying | None = None
        self._net = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

        self.setWidgetResizable(True)
        body = QWidget()
        self.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(28, 24, 28, 28)
        outer.setSpacing(16)

        # ── hero: on/off ──────────────────────────────────────────────────
        hero = QFrame()
        hero.setObjectName("card")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(24, 22, 24, 22)
        hl.setSpacing(24)
        text = QVBoxLayout()
        text.setSpacing(8)
        title = QLabel(t("media_title"))
        title.setObjectName("big_title")
        text.addWidget(title)
        desc = QLabel(t("media_desc"))
        desc.setObjectName("meta")
        desc.setWordWrap(True)
        text.addWidget(desc)
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._dot = QLabel("●")
        status_row.addWidget(self._dot)
        self._status = QLabel()
        status_row.addWidget(self._status)
        status_row.addStretch()
        text.addSpacing(4)
        text.addLayout(status_row)
        hl.addLayout(text, 1)
        self._toggle = QPushButton()
        self._toggle.setObjectName("primary")
        self._toggle.setMinimumWidth(150)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(
            lambda: controller.set_behaviour(MediaMode=not controller.behaviour.MediaMode))
        hl.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addWidget(hero)

        self._needs_plugin = QLabel(t("media_needs_plugin"))
        self._needs_plugin.setObjectName("toast")
        self._needs_plugin.setWordWrap(True)
        outer.addWidget(self._needs_plugin)

        # ── now playing ───────────────────────────────────────────────────
        np_card = QFrame()
        np_card.setObjectName("card")
        nl = QHBoxLayout(np_card)
        nl.setContentsMargins(18, 18, 18, 18)
        nl.setSpacing(18)
        self._art = QLabel()
        self._art.setFixedSize(96, 96)
        nl.addWidget(self._art)
        info = QVBoxLayout()
        info.setSpacing(4)
        lbl = QLabel(t("now_playing"))
        lbl.setObjectName("label")
        info.addWidget(lbl)
        self._track = QLabel()
        self._track.setObjectName("title")
        self._track.setWordWrap(True)
        info.addWidget(self._track)
        self._artist = QLabel()
        self._artist.setObjectName("meta")
        self._artist.setWordWrap(True)
        info.addWidget(self._artist)
        self._player = QLabel()
        self._player.setObjectName("hint")
        info.addWidget(self._player)
        info.addStretch()
        nl.addLayout(info, 1)
        outer.addWidget(np_card)

        # ── placement ─────────────────────────────────────────────────────
        pl = QLabel(t("placement"))
        pl.setObjectName("label")
        outer.addWidget(pl)
        row = QHBoxLayout()
        row.setSpacing(14)
        self._place_cards = [
            _ChoiceCard(PLACE_WIDGET, t("place_widget"), t("place_widget_desc")),
            _ChoiceCard(PLACE_FULLSCREEN, t("place_full"), t("place_full_desc")),
        ]
        for card in self._place_cards:
            card.clicked.connect(lambda v: controller.set_behaviour(MediaPlacement=v))
            row.addWidget(card)
        row.addStretch()
        outer.addLayout(row)

        # ── widget options ────────────────────────────────────────────────
        self._widget_box = QWidget()
        wl = QVBoxLayout(self._widget_box)
        wl.setContentsMargins(0, 4, 0, 0)
        wl.setSpacing(10)
        cl = QLabel(t("corner"))
        cl.setObjectName("label")
        wl.addWidget(cl)
        corners = QHBoxLayout()
        corners.setSpacing(8)
        self._corners = QButtonGroup(self)
        for value, key in ((CORNER_TOP_LEFT, "corner_tl"), (CORNER_TOP_RIGHT, "corner_tr"),
                           (CORNER_BOTTOM_LEFT, "corner_bl"), (CORNER_BOTTOM_RIGHT, "corner_br")):
            b = QPushButton(t(key))
            b.setProperty("chip", True)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._corners.addButton(b, value)
            corners.addWidget(b)
        corners.addStretch()
        self._corners.idClicked.connect(lambda v: controller.set_behaviour(MediaCorner=v))
        wl.addLayout(corners)
        size_row = QHBoxLayout()
        sl = QLabel(t("widget_size"))
        sl.setObjectName("meta")
        sl.setMinimumWidth(60)
        size_row.addWidget(sl)
        self._size = QSlider(Qt.Orientation.Horizontal)
        self._size.setRange(60, 160)
        self._size.setSingleStep(10)
        self._size.setPageStep(20)
        self._size.setMaximumWidth(340)
        self._size.valueChanged.connect(self._on_size)
        size_row.addWidget(self._size)
        self._size_val = QLabel()
        self._size_val.setObjectName("meta")
        self._size_val.setMinimumWidth(44)
        size_row.addWidget(self._size_val)
        size_row.addStretch()
        wl.addLayout(size_row)
        outer.addWidget(self._widget_box)

        # ── full-screen options ───────────────────────────────────────────
        self._full_box = QWidget()
        fl = QVBoxLayout(self._full_box)
        fl.setContentsMargins(0, 4, 0, 0)
        fl.setSpacing(10)
        stl = QLabel(t("media_style"))
        stl.setObjectName("label")
        fl.addWidget(stl)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self._style_cards: list[_ChoiceCard] = []
        for col, (style, key) in enumerate(((MEDIA_BLURRED, "style_blurred"),
                                            (MEDIA_FULL, "style_full"),
                                            (MEDIA_OLED, "style_oled"))):
            card = _ChoiceCard(style, t(key), size=QSize(208, 117))
            card.clicked.connect(lambda s: controller.set_behaviour(MediaStyle=s))
            self._style_cards.append(card)
            grid.addWidget(card, 0, col)
        grid.setColumnStretch(3, 1)
        fl.addLayout(grid)
        self._show_info = QCheckBox(t("media_show_info"))
        self._show_info.toggled.connect(lambda on: controller.set_behaviour(MediaShowInfo=on))
        fl.addWidget(self._show_info)
        outer.addWidget(self._full_box)

        # ── lyrics ────────────────────────────────────────────────────────
        ll = QLabel(t("lyrics"))
        ll.setObjectName("label")
        outer.addWidget(ll)
        lyr_card = QFrame()
        lyr_card.setObjectName("card")
        lc = QVBoxLayout(lyr_card)
        lc.setContentsMargins(16, 14, 16, 14)
        lc.setSpacing(6)
        self._lyrics = QCheckBox(t("lyrics_on"))
        self._lyrics.toggled.connect(lambda on: controller.set_behaviour(MediaLyrics=on))
        lc.addWidget(self._lyrics)
        lh = QLabel(t("lyrics_hint"))
        lh.setObjectName("hint")
        lh.setWordWrap(True)
        lc.addWidget(lh)
        outer.addWidget(lyr_card)

        self._only_playing = QCheckBox(t("media_only_playing"))
        self._only_playing.toggled.connect(lambda on: controller.set_behaviour(MediaOnlyPlaying=on))
        outer.addWidget(self._only_playing)
        outer.addStretch()

        # Slider drags change the preview at once and reach Plasma on release.
        self._size_timer = QTimer(self)
        self._size_timer.setSingleShot(True)
        self._size_timer.setInterval(200)
        self._size_timer.timeout.connect(
            lambda: controller.set_behaviour(MediaWidgetSize=self._size.value()))

        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._poll)

        controller.behaviour_changed.connect(self._sync)
        controller.current_changed.connect(lambda _w: self._load_wall())
        controller.thumb_ready.connect(lambda _id, _p: self._load_wall())
        self._load_wall()
        self._sync()

    # ── state → widgets ───────────────────────────────────────────────────

    def _sync(self) -> None:
        b = self._c.behaviour
        on = b.MediaMode
        self._toggle.setText(self._c.t("btn_media_disable" if on else "btn_media_enable"))
        self._status.setText(self._c.t("media_on" if on else "media_off"))
        self._dot.setStyleSheet(f"color: {ACTIVE_COLOR if on else '#6a6a6a'};")
        self._needs_plugin.setVisible(on and not self._c.current_id)
        widget = b.MediaPlacement != PLACE_FULLSCREEN
        for card in self._place_cards:
            card.set_selected(card.value == b.MediaPlacement)
        for card in self._style_cards:
            card.set_selected(card.value == b.MediaStyle)
        self._widget_box.setVisible(widget)
        self._full_box.setVisible(not widget)
        btn = self._corners.button(b.MediaCorner)
        if btn:
            btn.setChecked(True)
        self._size.blockSignals(True)
        self._size.setValue(b.MediaWidgetSize)
        self._size.blockSignals(False)
        self._size_val.setText(f"{b.MediaWidgetSize}%")
        for box, val in ((self._show_info, b.MediaShowInfo), (self._only_playing, b.MediaOnlyPlaying),
                         (self._lyrics, b.MediaLyrics)):
            box.blockSignals(True)
            box.setChecked(val)
            box.blockSignals(False)
        self._render_previews()

    def _on_size(self, v: int) -> None:
        self._size_val.setText(f"{v}%")
        self._render_previews(size=v)
        self._size_timer.start()

    def _load_wall(self) -> None:
        wp = self._c.current_wallpaper()
        path = self._c.request_thumb(wp) if wp else None
        pm = QPixmap(path) if path else None
        self._wall = pm if pm is not None and not pm.isNull() else None
        self._render_previews()

    def _render_previews(self, size: int | None = None) -> None:
        b = self._c.behaviour
        wall = self._wall or _placeholder_wall(_PREVIEW.width(), _PREVIEW.height())
        w, h = _PREVIEW.width(), _PREVIEW.height()
        self._place_cards[0].image.setPixmap(
            render_widget(wall, self._cover, b.MediaCorner, size or b.MediaWidgetSize, w, h))
        self._place_cards[1].image.setPixmap(render_fullscreen(b.MediaStyle, self._cover, w, h))
        for card in self._style_cards:
            card.image.setPixmap(render_fullscreen(card.value, self._cover, 208, 117))

    def _render_now_playing(self) -> None:
        np = self._np
        if np is None:
            self._track.setText(self._c.t("nothing_playing"))
            self._artist.setText(self._c.t("nothing_playing_hint"))
            self._player.clear()
        else:
            self._track.setText(np.title or "—")
            self._artist.setText("  ·  ".join(x for x in (np.artist, np.album) if x))
            status = self._c.t("status_playing" if np.playing else "status_paused")
            self._player.setText(f"{status}  ·  {self._c.t('via', player=np.player)}")
        art = QPixmap(96, 96)
        art.fill(Qt.GlobalColor.transparent)
        p = QPainter(art)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        _rounded(p, self._cover, QRectF(0, 0, 96, 96), 8)
        p.end()
        self._art.setPixmap(art)
        self._render_previews()

    # ── polling ───────────────────────────────────────────────────────────

    def _poll(self) -> None:
        np = media.now_playing()
        changed = np != self._np
        self._np = np
        url = np.art_url if np else ""
        if url != self._cover_url:
            self._cover_url = url
            self._load_cover(url)
        elif changed:
            self._render_now_playing()

    def _load_cover(self, url: str) -> None:
        if self._reply is not None:
            self._reply.abort()
            self._reply = None
        q = QUrl(url)
        if not url or (not q.isLocalFile() and q.scheme() not in ("http", "https")):
            self._cover = _placeholder_cover()
            self._render_now_playing()
            return
        if q.isLocalFile():
            pm = QPixmap(q.toLocalFile())
            self._cover = pm if not pm.isNull() else _placeholder_cover()
            self._render_now_playing()
            return
        reply = self._net.get(QNetworkRequest(q))
        self._reply = reply

        def done(r=reply):
            if r is self._reply:
                self._reply = None
                if r.error() == QNetworkReply.NetworkError.NoError:
                    pm = QPixmap()
                    if pm.loadFromData(r.readAll()):
                        self._cover = pm
                self._render_now_playing()
            r.deleteLater()

        reply.finished.connect(done)
        self._render_now_playing()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._poll()
        self._render_now_playing()
        self._timer.start()

    def hideEvent(self, e) -> None:
        super().hideEvent(e)
        self._timer.stop()

"""The wallpaper grid: filter chips, search, and the card delegate."""
from __future__ import annotations

from PyQt6.QtCore import (
    QAbstractListModel, QModelIndex, QRectF, QSize, QSortFilterProxyModel, Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QListView, QPushButton,
    QStackedWidget, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from mazewallpaper.core.library import ORIGIN_USER, Wallpaper
from mazewallpaper.gui import theme
from mazewallpaper.gui.theme import ACTIVE_COLOR

WALLPAPER_ROLE = Qt.ItemDataRole.UserRole + 1
THUMB_ROLE = Qt.ItemDataRole.UserRole + 2
CURRENT_ROLE = Qt.ItemDataRole.UserRole + 3

FILTER_ALL, FILTER_STATIC, FILTER_LIVE, FILTER_MINE = range(4)

_CARD_MIN_W = 230
_TEXT_H = 46
_PAD = 8


class WallpaperModel(QAbstractListModel):
    def __init__(self, controller):
        super().__init__()
        self._c = controller
        self._items: list[Wallpaper] = []
        self._pixmaps: dict[str, QPixmap] = {}
        self._row_of: dict[str, int] = {}
        controller.library_changed.connect(self.reload)
        controller.thumb_ready.connect(self._on_thumb)
        controller.current_changed.connect(self._on_current)
        self.reload()

    def reload(self) -> None:
        self.beginResetModel()
        self._items = list(self._c.items)
        self._row_of = {w.id: i for i, w in enumerate(self._items)}
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        wp = self._items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return wp.name
        if role == WALLPAPER_ROLE:
            return wp
        if role == CURRENT_ROLE:
            return wp.id == self._c.current_id
        if role == THUMB_ROLE:
            pm = self._pixmaps.get(wp.id)
            if pm is None:
                path = self._c.request_thumb(wp)
                if path:
                    pm = QPixmap(path)
                    self._pixmaps[wp.id] = pm
            return pm
        return None

    def index_of(self, wid: str) -> QModelIndex:
        row = self._row_of.get(wid)
        return self.index(row) if row is not None else QModelIndex()

    def _on_thumb(self, wid: str, path: str) -> None:
        self._pixmaps[wid] = QPixmap(path)
        idx = self.index_of(wid)
        if idx.isValid():
            self.dataChanged.emit(idx, idx, [THUMB_ROLE])

    def _on_current(self, _wid: str) -> None:
        if self._items:
            self.dataChanged.emit(self.index(0), self.index(len(self._items) - 1), [CURRENT_ROLE])


class FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.mode = FILTER_ALL
        self.text = ""

    def set_mode(self, mode: int) -> None:
        self.mode = mode
        self.invalidateFilter()

    def set_text(self, text: str) -> None:
        self.text = text.strip().casefold()
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        wp: Wallpaper = self.sourceModel().index(row, 0, parent).data(WALLPAPER_ROLE)
        if wp is None:
            return False
        if self.mode == FILTER_STATIC and wp.is_live:
            return False
        if self.mode == FILTER_LIVE and not wp.is_live:
            return False
        if self.mode == FILTER_MINE and wp.origin != ORIGIN_USER:
            return False
        return not self.text or self.text in wp.name.casefold()


class CardDelegate(QStyledItemDelegate):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._c = controller

    def sizeHint(self, option, index) -> QSize:
        view = self.parent()
        grid = view.gridSize() if isinstance(view, QListView) else QSize()
        if grid.isValid():
            return grid
        return QSize(_CARD_MIN_W, int(_CARD_MIN_W * 9 / 16) + _TEXT_H)

    def paint(self, p: QPainter, option, index) -> None:
        pal = theme.palette(self._c.settings.theme)
        wp: Wallpaper = index.data(WALLPAPER_ROLE)
        pm: QPixmap | None = index.data(THUMB_ROLE)
        current: bool = index.data(CURRENT_ROLE)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        r = QRectF(option.rect).adjusted(_PAD, _PAD, -_PAD, -_PAD)
        thumb = QRectF(r.left(), r.top(), r.width(), r.width() * 9 / 16)
        path = QPainterPath()
        path.addRoundedRect(thumb, 10, 10)

        p.fillPath(path, QColor("#141414"))
        if pm is not None and not pm.isNull():
            p.save()
            p.setClipPath(path)
            scaled = pm.scaled(thumb.size().toSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
            sx = (scaled.width() - thumb.width()) / 2
            sy = (scaled.height() - thumb.height()) / 2
            p.drawPixmap(thumb.toRect(), scaled, QRectF(sx, sy, thumb.width(), thumb.height()).toRect())
            if hovered and not selected:
                p.fillPath(path, QColor(255, 255, 255, 18))
            p.restore()

        if selected:
            pen = QPen(QColor(pal["accent"]), 2.5)
        elif hovered:
            pen = QPen(QColor(pal["focus"]), 1)
        else:
            pen = QPen(QColor(pal["border2"]), 1)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # kind badge (live kinds only — a static image needs no label)
        badge_font = QFont(option.font)
        badge_font.setPixelSize(10)
        badge_font.setBold(True)
        badge_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        p.setFont(badge_font)
        fm = p.fontMetrics()
        if wp.is_live:
            text = self._c.t(f"kind_{wp.kind}")
            bw = fm.horizontalAdvance(text) + 14
            badge = QRectF(thumb.left() + 10, thumb.top() + 10, bw, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(badge, 4, 4)
            p.setPen(QColor("#f0f0f0"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        if current:
            text = self._c.t("on_desktop")
            bw = fm.horizontalAdvance(text) + 26
            badge = QRectF(thumb.right() - bw - 10, thumb.top() + 10, bw, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 190))
            p.drawRoundedRect(badge, 10, 10)
            p.setBrush(QColor(ACTIVE_COLOR))
            p.drawEllipse(QRectF(badge.left() + 8, badge.center().y() - 3.5, 7, 7))
            p.setPen(QColor("#f0f0f0"))
            p.drawText(badge.adjusted(16, 0, 0, 0), Qt.AlignmentFlag.AlignCenter, text)

        # name + origin
        name_font = QFont(option.font)
        name_font.setPixelSize(13)
        name_font.setBold(selected or current)
        p.setFont(name_font)
        p.setPen(QColor(pal["text"]))
        text_r = QRectF(r.left() + 2, thumb.bottom() + 8, r.width() - 4, 18)
        p.drawText(text_r, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(wp.name, Qt.TextElideMode.ElideRight, int(text_r.width())))
        sub_font = QFont(option.font)
        sub_font.setPixelSize(11)
        p.setFont(sub_font)
        p.setPen(QColor(pal["text_mid"]))
        p.drawText(text_r.translated(0, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._c.t(f"origin_{wp.origin}"))
        p.restore()


class GalleryList(QListView):
    """IconMode list whose cards stretch to fill each row exactly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gallery")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setSpacing(0)
        self.setContentsMargins(0, 0, 0, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        avail = self.viewport().width() - 2
        cols = max(1, avail // _CARD_MIN_W)
        w = avail // cols
        h = int((w - 2 * _PAD) * 9 / 16) + _TEXT_H + 2 * _PAD
        size = QSize(w, h)
        if size != self.gridSize():
            self.setGridSize(size)


class GalleryView(QWidget):
    selected = pyqtSignal(object)     # Wallpaper | None
    activated = pyqtSignal(object)    # double-click → apply
    add_requested = pyqtSignal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._c = controller

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 12, 0)
        lay.setSpacing(12)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._chips = QButtonGroup(self)
        self._chips.setExclusive(True)
        for mode, key in ((FILTER_ALL, "filter_all"), (FILTER_STATIC, "filter_static"),
                          (FILTER_LIVE, "filter_live"), (FILTER_MINE, "filter_mine")):
            b = QPushButton(controller.t(key))
            b.setProperty("chip", True)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._chips.addButton(b, mode)
            bar.addWidget(b)
        self._chips.button(FILTER_ALL).setChecked(True)
        self._chips.idClicked.connect(self._on_mode)
        bar.addSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(controller.t("search"))
        self._search.setClearButtonEnabled(True)
        self._search.setMaximumWidth(260)
        self._search.textChanged.connect(self._on_search)
        bar.addWidget(self._search, 1)
        bar.addStretch()

        add = QPushButton(controller.t("btn_add"))
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_requested)
        bar.addWidget(add)
        lay.addLayout(bar)

        self.model = WallpaperModel(controller)
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model)

        self._list = GalleryList()
        self._list.setModel(self.proxy)
        self._list.setItemDelegate(CardDelegate(controller, self._list))
        self._list.selectionModel().currentChanged.connect(self._on_current)
        self._list.doubleClicked.connect(
            lambda idx: self.activated.emit(idx.data(WALLPAPER_ROLE)))

        self._empty = QLabel()
        self._empty.setObjectName("meta")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._empty)
        lay.addWidget(self._stack, 1)

        self.proxy.modelReset.connect(self._update_empty)
        self.proxy.rowsInserted.connect(self._update_empty)
        self.proxy.rowsRemoved.connect(self._update_empty)
        self.proxy.layoutChanged.connect(self._update_empty)
        controller.library_changed.connect(self._restore_selection)
        self._update_empty()

    def _on_mode(self, mode: int) -> None:
        self.proxy.set_mode(mode)
        self._update_empty()

    def _on_search(self, text: str) -> None:
        self.proxy.set_text(text)
        self._update_empty()

    def _update_empty(self, *_a) -> None:
        empty = self.proxy.rowCount() == 0
        if empty:
            key = "empty_mine" if self.proxy.mode == FILTER_MINE and not self.proxy.text else "empty_search"
            self._empty.setText(self._c.t(key))
        self._stack.setCurrentIndex(1 if empty else 0)

    def _on_current(self, idx: QModelIndex, _prev: QModelIndex) -> None:
        self.selected.emit(idx.data(WALLPAPER_ROLE) if idx.isValid() else None)

    def select(self, wid: str) -> None:
        src = self.model.index_of(wid)
        idx = self.proxy.mapFromSource(src) if src.isValid() else QModelIndex()
        if idx.isValid():
            self._list.setCurrentIndex(idx)
            self._list.scrollTo(idx)

    def show_mine(self) -> None:
        self._chips.button(FILTER_MINE).setChecked(True)
        self._on_mode(FILTER_MINE)

    def _restore_selection(self) -> None:
        # A model reset drops the selection; put back the one on the desktop
        # so the preview panel is never left describing nothing.
        if self._c.current_id:
            self.select(self._c.current_id)
        elif self.proxy.rowCount():
            self._list.setCurrentIndex(self.proxy.index(0, 0))

    def refresh(self) -> None:
        self._list.viewport().update()

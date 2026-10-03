"""The main window: Maze's frameless chrome around three tabs.

Files dropped anywhere on the window are imported into the library.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from mazewallpaper.core import library
from mazewallpaper.gui.gallery import GalleryView
from mazewallpaper.gui.icons import app_icon
from mazewallpaper.gui.media_view import MediaView
from mazewallpaper.gui.preview import PreviewPanel
from mazewallpaper.gui.settings_view import SettingsView
from mazewallpaper.gui.theme import ACTIVE_COLOR


class _TitleBar(QWidget):
    """Draggable header. startSystemMove() is what makes this work on Wayland."""

    def __init__(self, window: QMainWindow):
        super().__init__()
        self._window = window

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximized()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self._c = controller
        self.setWindowTitle("Maze Wallpaper")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(980, 640)
        self.resize(1240, 800)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAcceptDrops(True)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast.hide())

        self._build()

        controller.message.connect(self.show_message)
        controller.language_changed.connect(lambda _l: self._rebuild())
        controller.theme_changed.connect(lambda _t: self._gallery.refresh())
        controller.imported.connect(self._on_imported)
        controller.current_changed.connect(lambda _w: self._update_pill())

    # ── build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_header())

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        gallery_page = QWidget()
        gl = QHBoxLayout(gallery_page)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(0)
        self._gallery = GalleryView(self._c)
        self._preview = PreviewPanel(self._c)
        gl.addWidget(self._gallery, 1)
        gl.addWidget(self._preview)
        self._gallery.selected.connect(self._preview.show_wallpaper)
        self._gallery.activated.connect(self._c.apply)
        self._gallery.add_requested.connect(self._add_files)
        self._preview.apply_requested.connect(self._c.apply)
        self._preview.remove_requested.connect(self._confirm_remove)

        self._tabs.addTab(gallery_page, self._c.t("tab_gallery"))
        self._tabs.addTab(MediaView(self._c), self._c.t("tab_media"))
        self._tabs.addTab(SettingsView(self._c), self._c.t("tab_settings"))
        root.addWidget(self._tabs, 1)

        self._toast = QLabel(central)
        self._toast.setObjectName("toast")
        self._toast.setWordWrap(True)
        self._toast.setMaximumWidth(560)
        self._toast.hide()

        self._drop = QFrame(central)
        self._drop.setObjectName("drop_overlay")
        dl = QVBoxLayout(self._drop)
        msg = QLabel(self._c.t("drop_here"))
        msg.setObjectName("title")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(msg)
        self._drop.hide()

        # select what is on the desktop, or the first card
        QTimer.singleShot(0, self._gallery._restore_selection)

    def _rebuild(self) -> None:
        current_tab = self._tabs.currentIndex()
        old = self.centralWidget()
        self._build()
        old.deleteLater()
        self._tabs.setCurrentIndex(current_tab)

    def _make_header(self) -> QWidget:
        header = _TitleBar(self)
        header.setObjectName("header")
        header.setFixedHeight(50)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(18, 0, 0, 0)
        lay.setSpacing(4)
        logo = QLabel(self._c.t("app_name"))
        logo.setObjectName("logo")
        lay.addWidget(logo)
        lay.addStretch()

        # What is on the desktop right now, readable from any tab.
        self._pill_dot = QLabel("●")
        self._pill_dot.setStyleSheet(f"color: {ACTIVE_COLOR};")
        self._pill = QLabel()
        self._pill.setObjectName("meta")
        lay.addWidget(self._pill_dot)
        lay.addWidget(self._pill)
        lay.addSpacing(18)

        lang = QButtonGroup(header)
        lang.setExclusive(True)
        for code, label in (("en", "EN"), ("tr", "TR")):
            b = QPushButton(label)
            b.setProperty("chip", True)
            b.setCheckable(True)
            b.setChecked(self._c.settings.language == code)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, code=code: self._c.set_language(code))
            lang.addButton(b)
            lay.addWidget(b)
        lay.addSpacing(14)
        self._update_pill()
        for text, name, tip, slot in (
            ("—", "win_btn", "tip_minimize", self.showMinimized),
            ("☐", "win_btn", "tip_maximize", self.toggle_maximized),
            ("✕", "win_close", "tip_close", self.close),
        ):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setToolTip(self._c.t(tip))
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(slot)
            lay.addWidget(b)
        return header

    def _update_pill(self) -> None:
        wp = self._c.current_wallpaper()
        self._pill_dot.setVisible(wp is not None)
        self._pill.setText(f"{self._c.t('on_desktop').capitalize()}: {wp.name}" if wp else "")

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ── actions ───────────────────────────────────────────────────────────

    def _add_files(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(library.IMPORTABLE_EXTS))
        files, _ = QFileDialog.getOpenFileNames(
            self, self._c.t("add_title"), "",
            f"{self._c.t('add_filter')} ({exts})")
        if files:
            self._c.import_files(files)

    def _on_imported(self, wid: str) -> None:
        self._tabs.setCurrentIndex(0)
        self._gallery.show_mine()
        self._gallery.select(wid)

    def _confirm_remove(self, wp) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(self._c.t("remove_confirm_title"))
        box.setText(self._c.t("remove_confirm", name=wp.name))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self._c.remove(wp)

    def show_message(self, text: str, error: bool = False) -> None:
        self._toast.setText(("⚠  " if error else "") + text)
        self._toast.adjustSize()
        self._place_overlays()
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(7000 if error else 3500)

    def _place_overlays(self) -> None:
        cw = self.centralWidget()
        if not cw:
            return
        t = self._toast
        t.move((cw.width() - t.width()) // 2, cw.height() - t.height() - 24)
        self._drop.setGeometry(cw.rect().adjusted(16, 66, -16, -16))

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._place_overlays()

    # ── drag and drop ─────────────────────────────────────────────────────

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._place_overlays()
            self._drop.show()
            self._drop.raise_()

    def dragLeaveEvent(self, e) -> None:
        self._drop.hide()

    def dropEvent(self, e) -> None:
        self._drop.hide()
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if files:
            e.acceptProposedAction()
            self._c.import_files(files)

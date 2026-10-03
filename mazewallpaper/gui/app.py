"""Application entry point."""
from __future__ import annotations

import sys

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from mazewallpaper.gui.controller import Controller
from mazewallpaper.gui.icons import app_icon
from mazewallpaper.gui.theme import get_stylesheet
from mazewallpaper.gui.window import MainWindow

_SINGLETON_NAME = "maze-wallpaper-singleton"


def _activate_running_instance() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(_SINGLETON_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Maze Wallpaper")
    app.setApplicationDisplayName("Maze Wallpaper")
    app.setOrganizationName("maze")
    # Matches StartupWMClass in maze-wallpaper.desktop.
    app.setDesktopFileName("maze-wallpaper")
    app.setWindowIcon(app_icon())

    if _activate_running_instance():
        return 0
    QLocalServer.removeServer(_SINGLETON_NAME)
    singleton = QLocalServer()
    singleton.listen(_SINGLETON_NAME)

    controller = Controller()
    app.setStyleSheet(get_stylesheet(controller.settings.theme))
    controller.theme_changed.connect(lambda t: app.setStyleSheet(get_stylesheet(t)))

    window = MainWindow(controller)

    def _raise() -> None:
        conn = singleton.nextPendingConnection()
        if conn is not None:
            conn.disconnectFromServer()
        window.showNormal()
        window.raise_()
        window.activateWindow()

    singleton.newConnection.connect(_raise)

    # Files passed on the command line (e.g. "Open with Maze Wallpaper" from
    # Dolphin) go straight into the library.
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if files:
        controller.import_files(files)

    window.show()
    return app.exec()

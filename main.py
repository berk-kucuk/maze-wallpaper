#!/usr/bin/env python3
import sys


def _usage() -> None:
    print(
        "Maze Wallpaper — static, live and now-playing wallpapers for Maze Linux\n"
        "\n"
        "  maze-wallpaper                open the app\n"
        "  maze-wallpaper FILE…          add images or videos to your library\n"
        "  maze-wallpaper --list         list every wallpaper and its id\n"
        "  maze-wallpaper --apply ID     put a wallpaper on the desktop\n"
        "  maze-wallpaper --media on|off turn media mode on or off\n"
        "  maze-wallpaper --media-helper run the high-res cover helper (autostarted)\n"
        "  maze-wallpaper --version      print the version\n"
    )


def _cli(argv: list[str]) -> int | None:
    """Headless commands, for scripts and the ISO. None means "open the GUI"."""
    if not argv:
        return None
    cmd = argv[0]
    if cmd in ("-h", "--help"):
        _usage()
        return 0
    if cmd == "--media-helper":
        from mazewallpaper.media_helper import run
        return run()
    if cmd == "--version":
        from mazewallpaper import __version__
        print(__version__)
        return 0
    if cmd not in ("--list", "--apply", "--media"):
        return None

    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication(sys.argv[:1])  # QtDBus needs an application object
    from mazewallpaper.core import library, plasma, settings

    s = settings.load()
    if cmd == "--list":
        for w in library.scan_all():
            print(f"{w.id:<48} {w.kind:<9} {w.name}")
        return 0
    if cmd == "--apply":
        if len(argv) < 2:
            _usage()
            return 2
        wp = next((w for w in library.scan_all() if w.id == argv[1]), None)
        if wp is None:
            print(f"no wallpaper with id {argv[1]!r} (see --list)", file=sys.stderr)
            return 1
        try:
            n = plasma.apply(wp, s.behaviour)
        except plasma.PlasmaError as e:
            print(f"plasma: {e}", file=sys.stderr)
            return 1
        s.current_id = wp.id
        settings.save(s)
        print(f"applied {wp.name} on {n} desktop(s)")
        return 0
    if cmd == "--media":
        if len(argv) < 2 or argv[1] not in ("on", "off"):
            _usage()
            return 2
        s.behaviour.MediaMode = argv[1] == "on"
        settings.save(s)
        try:
            plasma.push_behaviour(s.behaviour)
        except plasma.PlasmaError as e:
            print(f"plasma: {e}", file=sys.stderr)
            return 1
        if s.behaviour.MediaMode:
            from mazewallpaper.gui.controller import ensure_media_helper
            ensure_media_helper()
        print(f"media mode {argv[1]}")
        return 0
    return None


if __name__ == "__main__":
    code = _cli(sys.argv[1:])
    if code is not None:
        sys.exit(code)
    from mazewallpaper.gui.app import run
    sys.exit(run())

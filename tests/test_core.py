"""Core tests. Nothing here talks to Plasma or D-Bus, and every file it writes
goes to a temporary directory.

    python3 tests/test_core.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from dataclasses import asdict, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402

_app = QGuiApplication.instance() or QGuiApplication([])

from mazewallpaper import PLUGIN_ID  # noqa: E402
from mazewallpaper.core import hires, library, media, plasma, settings, thumbs  # noqa: E402
from mazewallpaper.gui import i18n  # noqa: E402

PLUGIN_DIR = ROOT / "plasma" / PLUGIN_ID


def _png(path: Path, w: int = 64, h: int = 36) -> Path:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor("#336699"))
    path.parent.mkdir(parents=True, exist_ok=True)
    assert img.save(str(path))
    return path


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_kind_for(self):
        self.assertEqual(library.kind_for(Path("a.MP4")), library.KIND_VIDEO)
        self.assertEqual(library.kind_for(Path("a.webm")), library.KIND_VIDEO)
        self.assertEqual(library.kind_for(Path("a.gif")), library.KIND_ANIMATED)
        self.assertEqual(library.kind_for(Path("a.jpeg")), library.KIND_IMAGE)
        self.assertIsNone(library.kind_for(Path("a.txt")))

    def test_package_picks_largest_landscape_and_prefers_gif(self):
        pkg = self.tmp / "walls" / "Pkg"
        imgs = pkg / "contents" / "images"
        _png(imgs / "1920x1080.png")
        _png(imgs / "5120x2880.png")
        _png(imgs / "1440x2960.png")
        (pkg / "metadata.json").write_text(json.dumps({"KPlugin": {"Name": "Pretty"}}))
        found = library.scan_system((self.tmp / "walls",))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "Pretty")
        self.assertTrue(found[0].source.endswith("5120x2880.png"))

        # Qt cannot write GIFs; the scan only looks at the name.
        (imgs / "1920x1080.gif").write_bytes(b"GIF89a")
        found = library.scan_system((self.tmp / "walls",))
        self.assertEqual(found[0].kind, library.KIND_ANIMATED)

    def test_import_copies_and_dedupes(self):
        lib = self.tmp / "lib"
        src = _png(self.tmp / "My_Cool-Wall.png")
        a = library.import_file(src, lib)
        b = library.import_file(src, lib)
        self.assertNotEqual(a.source, b.source)
        self.assertTrue(Path(a.source).exists() and Path(b.source).exists())
        self.assertEqual(a.name, "My Cool Wall")
        self.assertEqual(a.origin, library.ORIGIN_USER)
        self.assertTrue(src.exists(), "the original is never moved")
        self.assertEqual(len(library.scan_user(lib)), 2)

    def test_import_rejects_unknown(self):
        bad = self.tmp / "notes.txt"
        bad.write_text("x")
        with self.assertRaises(ValueError):
            library.import_file(bad, self.tmp / "lib")

    def test_remove_only_user_and_only_inside_library(self):
        lib = self.tmp / "lib"
        wp = library.import_file(_png(self.tmp / "x.png"), lib)
        library.remove(wp, lib)
        self.assertFalse(Path(wp.source).exists())

        system = library.Wallpaper("system:x", "x", "image", "/usr/share/wallpapers/X/a.png", "system")
        with self.assertRaises(PermissionError):
            library.remove(system, lib)
        outside = library.Wallpaper("user:evil", "evil", "image", str(_png(self.tmp / "keep.png")), "user")
        with self.assertRaises(PermissionError):
            library.remove(outside, lib)
        self.assertTrue((self.tmp / "keep.png").exists())

    def test_only_maze_packages_from_the_system_dir(self):
        root = self.tmp / "usr-walls"
        def pkg(name, author):
            _png(root / name / "contents" / "images" / "1920x1080.png")
            (root / name / "metadata.json").write_text(json.dumps(
                {"KPlugin": {"Name": name, "Authors": [{"Name": author}]}}))
        pkg("Maze-Path", "Maze Linux")
        pkg("Next", "Krystian Zajdel")
        _png(root / "loose.png")
        user = self.tmp / "home-walls"
        _png(user / "Mine" / "contents" / "images" / "1920x1080.png")

        found = library.scan_system((root, user), filtered=(root,))
        self.assertEqual(sorted(w.name for w in found), ["Maze-Path", "Mine"])

    def test_no_scenes_left(self):
        ui = PLUGIN_DIR / "contents" / "ui"
        self.assertFalse((ui / "scenes").exists())
        self.assertNotIn("sceneComponent", (ui / "main.qml").read_text())
        self.assertFalse(hasattr(library, "SCENES"))


class SettingsTests(unittest.TestCase):
    def test_behaviour_matches_kcfg(self):
        """Every Behaviour field must be a kcfg entry, or Plasma drops it."""
        tree = ET.parse(PLUGIN_DIR / "contents" / "config" / "main.xml")
        ns = {"k": "http://www.kde.org/standards/kcfg/1.0"}
        entries = {e.get("name") for e in tree.getroot().iter(f"{{{ns['k']}}}entry")}
        for f in fields(settings.Behaviour):
            self.assertIn(f.name, entries)
        self.assertTrue({"Kind", "Source"} <= entries)

    def test_config_qml_declares_every_key(self):
        cfg = (PLUGIN_DIR / "contents" / "ui" / "config.qml").read_text()
        for f in fields(settings.Behaviour):
            self.assertIn(f"cfg_{f.name}", cfg)

    def test_from_dict_tolerates_garbage(self):
        s = settings.Settings.from_dict({
            "current_id": "x", "bogus": 1, "schema": settings.SCHEMA,
            "behaviour": {"Volume": "loud", "BlurRadius": 30, "PlaybackRate": 2, "Nope": True},
        })
        self.assertEqual(s.current_id, "x")
        self.assertEqual(s.behaviour.Volume, 50)          # wrong type → default
        self.assertEqual(s.behaviour.BlurRadius, 30)
        self.assertEqual(s.behaviour.PlaybackRate, 2.0)
        self.assertFalse(s.migrated)

    def test_old_file_gets_gentler_blur_and_english(self):
        s = settings.Settings.from_dict({
            "language": "tr", "behaviour": {"BlurRadius": 48, "ActiveDim": 25, "MediaMode": True}})
        self.assertTrue(s.migrated)
        self.assertEqual((s.behaviour.BlurRadius, s.behaviour.ActiveDim), (32, 10))
        self.assertEqual(s.language, "en")
        self.assertTrue(s.behaviour.MediaMode, "unrelated choices survive")
        # …and a choice made after the upgrade sticks
        again = settings.Settings.from_dict({"schema": settings.SCHEMA, "language": "tr"})
        self.assertEqual(again.language, "tr")


class PlasmaScriptTests(unittest.TestCase):
    def test_apply_script_escapes_and_marks(self):
        wp = library.Wallpaper("user:x", "x", "video", '/tmp/we"ird\'name .mp4', "user")
        script = plasma.build_apply_script(wp, settings.Behaviour())
        self.assertIn(f'd.wallpaperPlugin = "{PLUGIN_ID}"', script)
        self.assertIn('d.writeConfig("Source", "/tmp/we\\"ird\'name\\u2028.mp4");', script)
        self.assertIn('"WallpaperApplied", "1"', script)
        for k, v in asdict(settings.Behaviour()).items():
            self.assertIn(f'd.writeConfig("{k}", {json.dumps(v)});', script)

    def test_behaviour_script_only_touches_our_desktops(self):
        script = plasma.build_behaviour_script(settings.Behaviour())
        self.assertIn(f'if (d.wallpaperPlugin != "{PLUGIN_ID}") continue;', script)
        self.assertNotIn("wallpaperPlugin =", script)


class MediaTests(unittest.TestCase):
    def _np(self, player, status):
        return media.NowPlaying(player, status, "t", "a", "al", "")

    def test_pick_prefers_playing_then_spotify(self):
        a = self._np("firefox", "Paused")
        b = self._np("spotify", "Paused")
        c = self._np("mpv", "Playing")
        self.assertEqual(media.pick([a, b, c]).player, "mpv")
        self.assertEqual(media.pick([a, b]).player, "spotify")
        self.assertIsNone(media.pick([self._np("x", "Stopped")]))

    def test_from_props_joins_artists(self):
        np = media._from_props("org.mpris.MediaPlayer2.spotify", {
            "PlaybackStatus": "Playing",
            "Metadata": {"xesam:title": "Song", "xesam:artist": ["A", "B"],
                         "mpris:artUrl": "https://i.scdn.co/image/abc"},
        })
        self.assertEqual(np.player, "spotify")
        self.assertEqual(np.artist, "A, B")
        self.assertTrue(np.playing)


class HiresTests(unittest.TestCase):
    def test_youtube_ids(self):
        vid = "5OsIwKHppho"
        for url in (f"https://www.youtube.com/watch?v={vid}&list=RD&index=9",
                    f"https://music.youtube.com/watch?v={vid}",
                    f"https://youtu.be/{vid}?t=3",
                    f"https://www.youtube.com/shorts/{vid}"):
            self.assertEqual(hires.youtube_id(url), vid, url)
        self.assertIsNone(hires.youtube_id(f"https://evil.example/watch?v={vid}"))
        self.assertIsNone(hires.youtube_id("https://www.youtube.com/watch?v=../../etc"))

    def test_candidates(self):
        c = hires.candidates("file:///x.png", "https://www.youtube.com/watch?v=5OsIwKHppho")
        self.assertEqual(c[0], "https://i.ytimg.com/vi/5OsIwKHppho/maxresdefault.jpg")
        sp = "https://i.scdn.co/image/ab67616d00001e02" + "0" * 24
        self.assertTrue(all(u.startswith("https://i.scdn.co/image/ab67616d0000") for u in hires.candidates(sp, "")))
        self.assertEqual(hires.candidates("file:///x.png", "https://example.com/"), [])

    def test_key_matches_plugin_formula(self):
        """MediaLayer.qml computes Qt.md5(artUrl + "\\n" + track) + ".jpg"."""
        qml = (PLUGIN_DIR / "contents" / "ui" / "MediaLayer.qml").read_text()
        self.assertIn('Qt.md5(artUrl + "\\n" + track) + ".jpg"', qml)
        self.assertIn('"/maze-wallpaper/hires/"', qml)
        self.assertEqual(hires.cache_key("a", "ş"), __import__("hashlib").md5("a\nş".encode()).hexdigest())


class ThumbTests(unittest.TestCase):
    def test_image_thumbs(self):
        tmp = Path(tempfile.mkdtemp())
        old = thumbs.paths.THUMB_DIR
        thumbs.paths.THUMB_DIR = tmp / "thumbs"
        try:
            wp = library.Wallpaper("user:a", "a", "image", str(_png(tmp / "a.png", 300, 300)), "user")
            out = thumbs.ensure_thumb(wp)
            self.assertIsNotNone(out)
            img = QImage(str(out))
            self.assertEqual((img.width(), img.height()), (thumbs.THUMB_W, thumbs.THUMB_H))
        finally:
            thumbs.paths.THUMB_DIR = old


class I18nTests(unittest.TestCase):
    def test_tables_match(self):
        self.assertEqual(set(i18n.STRINGS["en"]), set(i18n.STRINGS["tr"]))

    def test_placeholders_match(self):
        for key, en in i18n.STRINGS["en"].items():
            tr = i18n.STRINGS["tr"][key]
            self.assertEqual(set(re.findall(r"{(\w+)}", en)), set(re.findall(r"{(\w+)}", tr)), key)


if __name__ == "__main__":
    unittest.main(verbosity=2)

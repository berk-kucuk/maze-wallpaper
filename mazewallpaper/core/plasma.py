"""Talking to Plasma: put a wallpaper on the desktop, and on the lock screen.

The desktop is changed through plasmashell's scripting interface
(org.kde.PlasmaShell.evaluateScript), the same one Maze's own
maze-apply-wallpaper uses. Script building is kept separate from sending so the
scripts can be tested without a running Plasma.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from mazewallpaper import PLUGIN_ID
from mazewallpaper.core.library import Wallpaper
from mazewallpaper.core.settings import Behaviour

_SERVICE = "org.kde.plasmashell"
_PATH = "/PlasmaShell"
_IFACE = "org.kde.PlasmaShell"


def _js(value) -> str:
    """A JS literal. json.dumps escapes everything a JS string needs,
    including U+2028/2029 because ensure_ascii is on."""
    return json.dumps(value)


def _write_lines(values: dict) -> str:
    return "\n".join(f"        d.writeConfig({_js(k)}, {_js(v)});" for k, v in values.items())


def build_apply_script(wp: Wallpaper, behaviour: Behaviour) -> str:
    """Switch every desktop (every screen) to Maze Wallpaper showing `wp`."""
    values = {"Kind": wp.kind, "Source": wp.source, **asdict(behaviour)}
    return f"""
var ds = desktops();
for (var i = 0; i < ds.length; i++) {{
    var d = ds[i];
    d.wallpaperPlugin = {_js(PLUGIN_ID)};
    d.currentConfigGroup = ["Wallpaper", {_js(PLUGIN_ID)}, "General"];
{_write_lines(values)}
    // maze-apply-wallpaper (maze-plasma-config) resets any desktop it has not
    // marked to Active Blur at login. Marking it here keeps the user's choice.
    d.currentConfigGroup = ["MazeLinux"];
    d.writeConfig("WallpaperApplied", "1");
    d.reloadConfig();
}}
print(ds.length);
"""


def build_behaviour_script(behaviour: Behaviour) -> str:
    """Update the behaviour keys on desktops that already show Maze Wallpaper,
    leaving desktops on other plugins alone."""
    return f"""
var ds = desktops();
var n = 0;
for (var i = 0; i < ds.length; i++) {{
    var d = ds[i];
    if (d.wallpaperPlugin != {_js(PLUGIN_ID)}) continue;
    d.currentConfigGroup = ["Wallpaper", {_js(PLUGIN_ID)}, "General"];
{_write_lines(asdict(behaviour))}
    d.reloadConfig();
    n++;
}}
print(n);
"""


def build_read_script() -> str:
    return f"""
var d = desktops()[0];
if (d) {{
    var out = {{ plugin: d.wallpaperPlugin }};
    if (d.wallpaperPlugin == {_js(PLUGIN_ID)}) {{
        d.currentConfigGroup = ["Wallpaper", {_js(PLUGIN_ID)}, "General"];
        out.kind = d.readConfig("Kind", "");
        out.source = d.readConfig("Source", "");
    }}
    print(JSON.stringify(out));
}}
"""


class PlasmaError(RuntimeError):
    pass


def evaluate(script: str) -> str:
    """Run a Plasma script and return what it printed."""
    from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        raise PlasmaError("no D-Bus session bus")
    iface = QDBusInterface(_SERVICE, _PATH, _IFACE, bus)
    if not iface.isValid():
        raise PlasmaError("plasmashell is not running")
    reply = iface.call("evaluateScript", script)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        raise PlasmaError(reply.errorMessage() or reply.errorName())
    args = reply.arguments()
    return str(args[0]) if args else ""


@dataclass
class Current:
    plugin: str = ""
    kind: str = ""
    source: str = ""

    @property
    def ours(self) -> bool:
        return self.plugin == PLUGIN_ID


def read_current() -> Current:
    try:
        out = evaluate(build_read_script()).strip()
        data = json.loads(out.splitlines()[-1]) if out else {}
    except (PlasmaError, ValueError, IndexError):
        return Current()
    return Current(str(data.get("plugin", "")), str(data.get("kind", "")), str(data.get("source", "")))


def apply(wp: Wallpaper, behaviour: Behaviour) -> int:
    """Returns the number of desktops changed."""
    out = evaluate(build_apply_script(wp, behaviour)).strip()
    try:
        return int(out.splitlines()[-1])
    except (ValueError, IndexError):
        return 0


def push_behaviour(behaviour: Behaviour) -> int:
    out = evaluate(build_behaviour_script(behaviour)).strip()
    try:
        return int(out.splitlines()[-1])
    except (ValueError, IndexError):
        return 0


# ── lock screen ──────────────────────────────────────────────────────────────
# The lock screen gets a still image through Plasma's stock Image plugin, never
# the live plugin: the greeter is the one place a wallpaper that fails to load
# leaves the user staring at a broken screen they cannot leave, and it has no
# windows to pause behind and no business showing what you were listening to.

def _kwriteconfig() -> str | None:
    return shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")


def apply_lock_screen(image: Path) -> None:
    tool = _kwriteconfig()
    if not tool:
        raise PlasmaError("kwriteconfig6 not found")
    url = image.resolve().as_uri()
    cmds = [
        [tool, "--file", "kscreenlockerrc", "--group", "Greeter",
         "--key", "WallpaperPlugin", "org.kde.image"],
        [tool, "--file", "kscreenlockerrc", "--group", "Greeter", "--group", "Wallpaper",
         "--group", "org.kde.image", "--group", "General", "--key", "Image", url],
        [tool, "--file", "kscreenlockerrc", "--group", "Greeter", "--group", "Wallpaper",
         "--group", "org.kde.image", "--group", "General", "--key", "PreviewImage", url],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise PlasmaError(r.stderr.strip() or f"{cmd[0]} failed")

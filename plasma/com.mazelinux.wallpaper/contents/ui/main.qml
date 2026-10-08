/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    Maze Wallpaper — the renderer.

    Two layers, bottom to top, both inside one blur layer:

      1. the wallpaper itself (image, GIF or looping video);
      2. the media layer: when media mode is on and something is playing over
         MPRIS (Spotify, a browser, mpv…), its cover art fades in over the
         wallpaper.

    While a window has focus the whole thing is blurred and dimmed ("active
    blur", the Maze desktop's signature).

    Live wallpapers pause whenever nobody can see them: behind a maximized or
    fullscreen window (configurable), behind active blur and behind the media
    layer. They can also pause to save power: on battery, on a low battery, or
    while the system is in power-saver.

    The library, imports and choosing what to show belong to the Maze Wallpaper
    app; it writes this plugin's configuration through Plasma scripting.
*/

import QtQuick
import QtQuick.Window
import QtQuick.Effects
import QtMultimedia
import org.kde.plasma.plasmoid
import org.kde.taskmanager as TaskManager
import org.kde.plasma.private.mpris as Mpris
import org.kde.plasma.plasma5support as P5Support

WallpaperItem {
    id: root

    // Versions up to 1.2 had built-in QML scenes ("scene" kind). They are
    // gone; a desktop still set to one gets Maze's default wallpaper rather
    // than a black screen.
    readonly property bool legacyScene: configuration.Kind === "scene"
    readonly property string kind: legacyScene ? "image" : (configuration.Kind || "image")
    readonly property string source: legacyScene ? "/usr/share/wallpapers/MazeOLED/contents/images/2560x1440.png"
                                                 : (configuration.Source || "")
    readonly property int fillMode: configuration.FillMode

    // ── Who can see the desktop? ────────────────────────────────────────────
    TaskManager.VirtualDesktopInfo { id: desktopInfo }
    TaskManager.ActivityInfo { id: activityInfo }

    TaskManager.TasksModel {
        id: tasksModel
        groupMode: TaskManager.TasksModel.GroupDisabled
        filterByVirtualDesktop: true
        filterByActivity: true
        // Only windows on this wallpaper's own screen: a fullscreen video on
        // the second monitor must not pause or blur the first one.
        filterByScreen: true
        screenGeometry: Qt.rect(root.Screen.virtualX, root.Screen.virtualY,
                                root.Screen.width, root.Screen.height)
        filterMinimized: true
        filterHidden: true
        virtualDesktop: desktopInfo.currentDesktop
        activity: activityInfo.currentActivity
    }

    property bool anyWindowActive: false
    property bool anyWindowCovering: false

    function recountWindows() {
        let active = false;
        let covering = false;
        for (let i = 0; i < windowWatch.count; ++i) {
            const w = windowWatch.objectAt(i);
            if (!w) continue;
            active = active || w.active;
            covering = covering || w.covering;
        }
        anyWindowActive = active;
        anyWindowCovering = covering;
    }

    Instantiator {
        id: windowWatch
        model: tasksModel
        delegate: QtObject {
            required property var model
            readonly property bool active: model.IsWindow === true && model.IsActive === true
            readonly property bool covering: model.IsWindow === true
                                             && (model.IsMaximized === true || model.IsFullScreen === true)
            onActiveChanged: root.recountWindows()
            onCoveringChanged: root.recountWindows()
        }
        onObjectAdded: root.recountWindows()
        onObjectRemoved: Qt.callLater(root.recountWindows)
    }

    // ── What is playing? ────────────────────────────────────────────────────
    Mpris.Mpris2Model {
        id: mpris
        onCurrentPlayerChanged: Qt.callLater(root.pickPlayer)
    }

    // Plasma's currentPlayer follows the focused window: click on a browser
    // with a paused tab and it becomes "current" while Spotify keeps playing,
    // and media mode went blank. The wallpaper picks for itself instead:
    //   1. the player it already shows, while that one is still playing
    //   2. Plasma's current player, if it is playing
    //   3. any player that is playing
    //   4. Plasma's current player (paused, or nothing)
    property var player: null

    function playing(p) {
        return !!p && p.playbackStatus === Mpris.PlaybackStatus.Playing;
    }

    function pickPlayer() {
        let next = null;
        if (playing(player) && stillListed(player)) {
            next = player;
        } else if (playing(mpris.currentPlayer)) {
            next = mpris.currentPlayer;
        } else {
            for (let i = 0; i < playerWatch.count; ++i) {
                const w = playerWatch.objectAt(i);
                if (w && !w.multiplexer && playing(w.container)) {
                    next = w.container;
                    break;
                }
            }
            if (!next) next = mpris.currentPlayer;
        }
        if (next !== player) player = next;
    }

    function stillListed(p) {
        for (let i = 0; i < playerWatch.count; ++i) {
            const w = playerWatch.objectAt(i);
            if (w && w.container === p) return true;
        }
        return p === mpris.currentPlayer;
    }

    Instantiator {
        id: playerWatch
        model: mpris
        delegate: QtObject {
            required property var model
            readonly property var container: model.container
            readonly property bool multiplexer: model.isMultiplexer === true
            readonly property int status: model.playbackStatus
            onStatusChanged: Qt.callLater(root.pickPlayer)
        }
        onObjectAdded: Qt.callLater(root.pickPlayer)
        onObjectRemoved: Qt.callLater(root.pickPlayer)
    }

    // A player's own status changes reach us through its container too.
    Connections {
        target: root.player
        ignoreUnknownSignals: true
        function onPlaybackStatusChanged() { Qt.callLater(root.pickPlayer); }
    }
    readonly property string artUrl: player ? (player.artUrl || "") : ""
    readonly property bool mediaPlaying: !!player && player.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool mediaPaused: !!player && player.playbackStatus === Mpris.PlaybackStatus.Paused
    readonly property bool mediaActive: configuration.MediaMode
                                        && artUrl !== ""
                                        && (mediaPlaying || (mediaPaused && !configuration.MediaOnlyPlaying))
    // Placement 1 replaces the wallpaper with the cover; placement 0 keeps
    // the wallpaper and adds a card in a corner.
    readonly property bool mediaShown: mediaActive && configuration.MediaPlacement === 1
    readonly property bool widgetShown: mediaActive && configuration.MediaPlacement !== 1

    // One line in the journal whenever what the media layer shows changes —
    // enough to answer "why is nothing on screen" without a debugger:
    //   journalctl --user -o cat | grep maze-wallpaper
    readonly property string mediaState: [
        "player=" + (player ? (player.identity || "?") : "none"),
        "status=" + (player ? player.playbackStatus : -1),
        "art=" + (artUrl ? artUrl.slice(-40) : "none"),
        "mode=" + configuration.MediaMode,
        "placement=" + configuration.MediaPlacement,
        "fullscreen=" + mediaShown + "/" + mediaLayer.ready,
        "widget=" + widgetShown + "/" + mediaWidget.ready,
        "lyrics=" + (lyrics.enabled ? lyrics.lines.length + (lyrics.synced ? "s" : "p") : "off")
    ].join(" ")
    onMediaStateChanged: console.info("maze-wallpaper:", mediaState)
    readonly property rect screenRect: tasksModel.screenGeometry
    onScreenRectChanged: console.info("maze-wallpaper: screen", screenRect.x, screenRect.y, screenRect.width, screenRect.height)

    // ── Playback position ───────────────────────────────────────────────────
    // MPRIS reports the position only when it jumps (seek, pause, new track),
    // so between reports it is extrapolated from the wall clock — and every
    // few seconds Plasma is asked to re-read it, which keeps synced lyrics
    // from drifting.
    property real positionMs: 0
    property real anchorPositionMs: 0
    property real anchorTime: 0

    function resyncPosition() {
        anchorPositionMs = player ? player.position / 1000 : 0;
        anchorTime = Date.now();
        positionMs = anchorPositionMs;
    }

    Connections {
        target: root.player
        ignoreUnknownSignals: true
        function onPositionChanged() { root.resyncPosition(); }
        function onTrackChanged() { root.resyncPosition(); }
    }
    onPlayerChanged: resyncPosition()
    onMediaPlayingChanged: resyncPosition()

    Timer {
        interval: 200
        repeat: true
        running: root.mediaPlaying && root.mediaActive
        onTriggered: {
            const rate = root.player && root.player.rate > 0 ? root.player.rate : 1;
            root.positionMs = root.anchorPositionMs + (Date.now() - root.anchorTime) * rate;
        }
    }
    Timer {
        interval: 3000
        repeat: true
        running: root.mediaPlaying && root.mediaActive && lyrics.available
        onTriggered: if (root.player) root.player.updatePosition()
    }

    // ── Lyrics ──────────────────────────────────────────────────────────────
    LyricsSource {
        id: lyrics
        enabled: root.configuration.MediaLyrics === true && root.mediaActive
        artist: root.player ? (root.player.artist || "") : ""
        title: root.player ? (root.player.track || "") : ""
        album: root.player ? (root.player.album || "") : ""
        lengthUs: root.player ? root.player.length : 0
    }

    // ── Power ───────────────────────────────────────────────────────────────
    // PowerDevil's data engine: AC, battery and the power profile, pushed on
    // change. Connected only while a power option needs it.
    readonly property bool watchPower: configuration.PauseOnBattery
                                       || configuration.BatteryThreshold > 0
                                       || configuration.FollowPowerProfile
    P5Support.DataSource {
        id: power
        engine: "powermanagement"
        connectedSources: root.watchPower ? ["AC Adapter", "Battery", "Power Profiles"] : []
    }
    readonly property var batteryData: power.data["Battery"] || ({})
    readonly property bool hasBattery: batteryData["Has Battery"] === true
    // No battery means mains power, whatever the AC source says.
    readonly property bool onBattery: hasBattery && !!power.data["AC Adapter"]
                                      && power.data["AC Adapter"]["Plugged in"] === false
    readonly property int batteryPercent: batteryData["Percent"] !== undefined ? batteryData["Percent"] : 100
    readonly property bool powerSaver: !!power.data["Power Profiles"]
                                       && power.data["Power Profiles"]["Current Profile"] === "power-saver"
    readonly property bool hiddenByPower: watchPower && (
        (configuration.PauseOnBattery && onBattery)
        || (onBattery && configuration.BatteryThreshold > 0 && batteryPercent < configuration.BatteryThreshold)
        || (configuration.FollowPowerProfile && powerSaver))

    // ── Pausing ─────────────────────────────────────────────────────────────
    readonly property bool hiddenByWindows: configuration.PauseMode === 1 ? anyWindowCovering
                                          : configuration.PauseMode === 2 ? anyWindowActive
                                          : false
    // Once active blur has fully set in, a still frame and a moving one look
    // the same through it, so the video stops; it starts again as soon as the
    // blur begins to lift.
    readonly property bool hiddenByBlur: configuration.PauseOnBlur && desktopLayer.blurAmount >= 1
    // The media layer is opaque once faded in, so the wallpaper under it is
    // invisible and has no reason to keep decoding frames.
    readonly property bool livePaused: hiddenByWindows || hiddenByBlur || hiddenByPower
                                       || (mediaShown && mediaLayer.opacity >= 1)
    onLivePausedChanged: console.info("maze-wallpaper: live", livePaused ? "paused" : "playing",
                                      "windows=" + hiddenByWindows, "blur=" + hiddenByBlur,
                                      "power=" + hiddenByPower)

    readonly property bool blurOn: configuration.ActiveBlur && anyWindowActive

    Rectangle {
        anchors.fill: parent
        color: "black"
    }

    // Everything visible goes through one blur layer, so active blur softens
    // whatever is on screen — the wallpaper or the cover over it.
    Item {
        id: desktopLayer
        anchors.fill: parent

        property real blurAmount: root.blurOn ? 1 : 0
        Behavior on blurAmount { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

        readonly property int radius: Math.max(1, Math.min(64, root.configuration.BlurRadius))
        readonly property real dim: root.configuration.ActiveDim / 100

        layer.enabled: blurAmount > 0
        layer.effect: MultiEffect {
            blurEnabled: true
            blurMax: desktopLayer.radius
            blur: desktopLayer.blurAmount
            autoPaddingEnabled: false
        }

        // ── 1. The wallpaper ────────────────────────────────────────────────
        Loader {
            id: contentLoader
            anchors.fill: parent
            sourceComponent: {
                switch (root.kind) {
                case "video":    return videoComponent;
                case "animated": return animatedComponent;
                default:         return imageComponent;
                }
            }
        }

        // ── 2. The media layer ──────────────────────────────────────────────
        MediaLayer {
            id: mediaLayer
            anchors.fill: parent
            artUrl: root.artUrl
            track: root.player ? root.player.track : ""
            artist: root.player ? root.player.artist : ""
            album: root.player ? root.player.album : ""
            style: root.configuration.MediaStyle
            showInfo: root.configuration.MediaShowInfo
            paused: root.mediaPaused
            lyricsLines: lyrics.lines
            lyricsSynced: lyrics.synced
            showLyrics: lyrics.enabled && lyrics.available
            positionMs: root.positionMs
            lengthMs: root.player ? root.player.length / 1000 : 0

            visible: opacity > 0
            opacity: root.mediaShown && ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 600; easing.type: Easing.InOutQuad } }
        }

        // ── 2b. …or a card in a corner, over the wallpaper ──────────────────
        MediaWidget {
            id: mediaWidget
            anchors.fill: parent
            backdropSource: contentLoader
            artUrl: root.artUrl
            track: root.player ? root.player.track : ""
            artist: root.player ? root.player.artist : ""
            album: root.player ? root.player.album : ""
            playing: root.mediaPlaying
            paused: root.mediaPaused
            position: root.positionMs * 1000
            length: root.player ? root.player.length : 0
            lyricsLines: lyrics.lines
            lyricsSynced: lyrics.synced
            showLyrics: lyrics.enabled && lyrics.available
            corner: root.configuration.MediaCorner
            animations: root.configuration.MediaAnimations
            // Motion on a desktop that saves power would undo the saving.
            stillForPower: root.hiddenByPower
            sizePercent: Math.max(60, Math.min(180, root.configuration.MediaWidgetSize))

            visible: opacity > 0
            opacity: root.widgetShown && ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
        }
    }

    // Dimming is a black veil, not MultiEffect.brightness: brightness
    // subtracts the same amount from every pixel, which pushes the dark parts
    // of Maze's mostly-black wallpapers straight to black. A veil scales
    // everything evenly, so the picture stays readable.
    Rectangle {
        anchors.fill: parent
        color: "black"
        opacity: desktopLayer.blurAmount * desktopLayer.dim
        visible: opacity > 0
    }

    Component {
        id: imageComponent
        Image {
            asynchronous: true
            cache: false
            smooth: true
            fillMode: root.fillMode
            sourceSize.width: root.width * Screen.devicePixelRatio
            sourceSize.height: root.height * Screen.devicePixelRatio
            source: root.fileUrl(root.source)
        }
    }

    Component {
        id: animatedComponent
        AnimatedImage {
            asynchronous: true
            cache: false
            fillMode: root.fillMode
            source: root.fileUrl(root.source)
            playing: !root.livePaused
        }
    }

    Component {
        id: videoComponent
        Item {
            MediaPlayer {
                id: videoPlayer
                source: root.fileUrl(root.source)
                loops: MediaPlayer.Infinite
                playbackRate: root.configuration.PlaybackRate > 0 ? root.configuration.PlaybackRate : 1.0
                videoOutput: videoOut
                audioOutput: AudioOutput {
                    muted: root.configuration.Muted
                    volume: root.configuration.Volume / 100
                }
                function sync() {
                    if (root.livePaused) pause(); else play();
                }
                onSourceChanged: sync()
                Component.onCompleted: sync()
            }
            Connections {
                target: root
                function onLivePausedChanged() { videoPlayer.sync(); }
            }
            VideoOutput {
                id: videoOut
                anchors.fill: parent
                fillMode: root.fillMode === 0 ? VideoOutput.Stretch
                        : root.fillMode === 1 ? VideoOutput.PreserveAspectFit
                        : VideoOutput.PreserveAspectCrop
            }
        }
    }

    // Plain paths and file:// URLs are both accepted, so a hand-edited config
    // and the app's own writes behave the same.
    function fileUrl(path) {
        if (!path) return "";
        if (path.indexOf("://") !== -1) return path;
        return "file://" + path;
    }
}

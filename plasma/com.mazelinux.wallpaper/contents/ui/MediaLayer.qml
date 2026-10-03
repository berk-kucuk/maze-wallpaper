/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    Now-playing cover art, drawn over the wallpaper.

    Two CoverSlides take turns: a new cover loads into the hidden one and only
    fades in once it has arrived, so a slow network never flashes an empty
    frame between songs.

    Resolution: browsers hand MPRIS a small copy of the page's artwork
    (YouTube: 336×188). The Maze Wallpaper media helper fetches the full-size
    image into ~/.cache/maze-wallpaper/hires/<md5(artUrl + "\n" + title)>.jpg
    (see mazewallpaper/core/hires.py). This layer shows the player's cover at
    once, then watches for that file for a while and cross-fades to it when it
    appears.
*/

import QtQuick
import QtCore

Item {
    id: layer

    property string artUrl: ""
    property string track: ""
    property string artist: ""
    property string album: ""
    property int style: 0
    property bool paused: false

    property bool showInfo: true

    // lyrics (see LyricsSource.qml)
    property var lyricsLines: []
    property bool lyricsSynced: false
    property bool showLyrics: false
    property real positionMs: 0
    property real lengthMs: 0

    // With lyrics, the cover moves to the left third and the lyrics take
    // the right half.
    readonly property real coverShift: showLyrics ? -width * 0.22 : 0

    // true once a cover is on screen
    readonly property bool ready: current !== null && current.ready

    property CoverSlide current: null
    // the url the layer wants on screen; a slide that finishes loading
    // anything else (a superseded track) is ignored
    property string wanted: ""

    readonly property int coverSize: Math.round(Math.min(width, height) * 0.42)
    readonly property int coverOffset: showInfo ? -Math.round(height * 0.05) : 0

    readonly property string hiresDir: StandardPaths.writableLocation(StandardPaths.GenericCacheLocation)
                                       + "/maze-wallpaper/hires/"
    property string hiresUrl: ""

    onArtUrlChanged: Qt.callLater(refresh)
    onTrackChanged: Qt.callLater(refresh)

    function refresh() {
        if (!artUrl) return;
        const hires = hiresDir + Qt.md5(artUrl + "\n" + track) + ".jpg";
        if (hires === hiresUrl) return;
        hiresUrl = hires;
        probe.attempts = 0;
        probe.check();
        show(artUrl);
    }

    function show(url) {
        if (current && current.url === url) {
            wanted = url;
            return;
        }
        wanted = url;
        const next = current === slideA ? slideB : slideA;
        next.url = url;
        promote(next);
    }

    function promote(slide) {
        if (slide.ready && slide.url === wanted) current = slide;
    }

    // Looks for the helper's high-resolution file. cache:false so each look
    // really asks the disk; a missing file is just an Error status.
    Image {
        id: probe
        visible: false
        asynchronous: true
        cache: false
        sourceSize: Qt.size(16, 16)
        property int attempts: 0

        function check() {
            source = "";
            source = layer.hiresUrl;
        }
        onStatusChanged: {
            if (status === Image.Ready && source.toString() === layer.hiresUrl) {
                retry.stop();
                layer.show(layer.hiresUrl);
            } else if (status === Image.Error && attempts < 5) {
                // 1, 2, 4, 8, 16 s: covers the helper's fetch without filling
                // the journal with "Cannot open" for songs it has nothing for.
                retry.interval = 1000 * Math.pow(2, attempts);
                retry.restart();
            }
        }
    }

    Timer {
        id: retry
        interval: 1000
        onTriggered: {
            probe.attempts++;
            probe.check();
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "black"
    }

    CoverSlide {
        id: slideA
        anchors.fill: parent
        style: layer.style
        coverShift: layer.coverShift
        paused: layer.paused
        coverSize: layer.coverSize
        coverOffset: layer.coverOffset
        opacity: layer.current === slideA ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }
        onReadyChanged: layer.promote(slideA)
    }

    CoverSlide {
        id: slideB
        anchors.fill: parent
        style: layer.style
        coverShift: layer.coverShift
        paused: layer.paused
        coverSize: layer.coverSize
        coverOffset: layer.coverOffset
        opacity: layer.current === slideB ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }
        onReadyChanged: layer.promote(slideB)
    }

    // ── track info ──────────────────────────────────────────────────────────
    Column {
        id: info
        visible: layer.showInfo && (layer.track !== "" || layer.artist !== "")
        spacing: 6
        width: layer.showLyrics ? layer.width * 0.36 : Math.min(layer.width * 0.8, 900)

        // Style 1 has no centred cover, so the text moves to the bottom-left
        // like a film title; otherwise it sits under the cover.
        readonly property real coverHeight: layer.current ? layer.current.coverHeight : layer.coverSize
        x: layer.style === 1 ? Math.round(layer.width * 0.05)
                             : Math.round((layer.width - width) / 2 + layer.coverShift)
        y: layer.style === 1 ? Math.round(layer.height * 0.9 - height)
                             : Math.round(layer.height / 2 + layer.coverOffset + coverHeight / 2 + layer.height * 0.04)

        readonly property int align: layer.style === 1 ? Text.AlignLeft : Text.AlignHCenter
        Behavior on x { NumberAnimation { duration: 600; easing.type: Easing.InOutCubic } }

        Text {
            width: parent.width
            horizontalAlignment: info.align
            text: layer.track
            color: "#f0f0f0"
            font.pixelSize: Math.max(18, Math.round(layer.height * 0.032))
            font.weight: Font.DemiBold
            font.family: "Inter"
            elide: Text.ElideRight
            style: Text.Raised
            styleColor: "#80000000"
        }
        Text {
            width: parent.width
            horizontalAlignment: info.align
            text: layer.album && layer.artist ? layer.artist + "  ·  " + layer.album
                                              : (layer.artist || layer.album)
            color: "#9a9a9a"
            font.pixelSize: Math.max(13, Math.round(layer.height * 0.019))
            font.family: "Inter"
            elide: Text.ElideRight
        }
    }

    // ── lyrics ──────────────────────────────────────────────────────────────
    LyricsView {
        id: lyricsView
        x: Math.round(layer.width * 0.52)
        width: Math.round(layer.width * 0.40)
        height: Math.round(layer.height * 0.72)
        anchors.verticalCenter: parent.verticalCenter
        lines: layer.lyricsLines
        synced: layer.lyricsSynced
        positionMs: layer.positionMs
        lengthMs: layer.lengthMs
        fontSize: Math.max(20, Math.round(layer.height * 0.034))
        alignment: Text.AlignLeft
        opacity: layer.showLyrics ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 500 } }
    }
}

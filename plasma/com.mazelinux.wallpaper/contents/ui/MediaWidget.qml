/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    Media mode as a widget: a frosted card in a corner of the wallpaper with
    the cover, the track and a progress line. The wallpaper stays as it is
    (and keeps playing, if it is live); only the card is new.

    The card's glass is the wallpaper itself: `backdropSource` (the wallpaper
    item) is sampled under the card, blurred and tinted. The desktop is not
    interactive, so the card is display-only — no buttons to pretend with.
*/

import QtQuick
import QtQuick.Effects
import "lyrics.js" as Lyrics

Item {
    id: widget

    property Item backdropSource: null
    property string artUrl: ""
    property string track: ""
    property string artist: ""
    property string album: ""
    property bool playing: false
    property bool paused: false
    property real position: 0      // µs, from MPRIS
    property real length: 0        // µs
    property int corner: 0         // 0 TR, 1 TL, 2 BR, 3 BL
    property int sizePercent: 100

    property var lyricsLines: []
    property bool lyricsSynced: false
    property bool showLyrics: false
    readonly property int lyricIndex: Lyrics.currentIndex(lyricsLines, lyricsSynced,
                                                           shownPosition / 1000, length / 1000)

    readonly property bool ready: cover.status === Image.Ready
    // The plugin has no access to the app's language; the system's is the
    // next best thing.
    readonly property bool tr: Qt.locale().name.startsWith("tr")

    // Sized from the screen, so it is the same visual weight on 1080p and 4K.
    readonly property real unit: Math.min(width, height) / 1080 * sizePercent / 100
    readonly property int cardW: Math.round(430 * unit)
    readonly property int cardH: Math.round(132 * unit)
    // Clear of a panel at either edge.
    readonly property int marginX: Math.round(Math.max(28, 48 * unit))
    readonly property int marginY: Math.round(Math.max(28, 64 * unit))

    // `position` already arrives extrapolated (main.qml, every 200 ms), the
    // same clock the full-screen lyrics use. Estimating again here on top of
    // it ran ahead by up to a second and was then pulled back by the next
    // update, so the lyric line flicked forward, back and forward again.
    readonly property real shownPosition: Math.min(length > 0 ? length : position, position)

    // m:ss, or h:mm:ss once the media runs an hour or more — for both the
    // elapsed time and the length, so the two read alike (0:05:12 / 1:23:45).
    readonly property bool longMedia: length >= 3600e6
    function fmt(us) {
        const t = Math.max(0, Math.floor(us / 1e6));
        const h = Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = t % 60;
        const ss = (s < 10 ? "0" : "") + s;
        if (!widget.longMedia)
            return Math.floor(t / 60) + ":" + ss;
        return h + ":" + (m < 10 ? "0" : "") + m + ":" + ss;
    }

    Item {
        id: card
        width: widget.cardW
        height: widget.cardH
        x: (widget.corner === 1 || widget.corner === 3) ? widget.marginX : widget.width - width - widget.marginX
        y: (widget.corner === 2 || widget.corner === 3) ? widget.height - height - widget.marginY : widget.marginY

        // A new track nudges in; a paused one fades back a little.
        opacity: widget.paused ? 0.75 : 1
        Behavior on opacity { NumberAnimation { duration: 300 } }

        RectangularShadow {
            anchors.fill: parent
            offset.y: Math.round(10 * widget.unit)
            radius: glassMask.radius
            blur: Math.round(36 * widget.unit)
            color: "#88000000"
        }

        // ── glass ───────────────────────────────────────────────────────
        ShaderEffectSource {
            id: under
            anchors.fill: parent
            visible: false
            sourceItem: widget.backdropSource
            sourceRect: Qt.rect(card.x, card.y, card.width, card.height)
            live: true
            recursive: false
        }
        Rectangle {
            id: glassMask
            anchors.fill: parent
            radius: Math.round(20 * widget.unit)
            visible: false
            layer.enabled: true
        }
        MultiEffect {
            anchors.fill: parent
            source: under
            blurEnabled: true
            blurMax: 48
            blur: 1.0
            saturation: 0.2
            maskEnabled: true
            maskSource: glassMask
            autoPaddingEnabled: false
        }
        Rectangle {
            anchors.fill: parent
            radius: glassMask.radius
            color: Qt.rgba(0.04, 0.04, 0.04, 0.58)
            border.color: Qt.rgba(1, 1, 1, 0.09)
            border.width: 1
        }

        // ── content ─────────────────────────────────────────────────────
        Item {
            id: coverBox
            x: Math.round(16 * widget.unit)
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(100 * widget.unit)
            height: width

            Image {
                id: cover
                anchors.fill: parent
                source: widget.artUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                smooth: true
                mipmap: true
                visible: false
                layer.enabled: true
                layer.smooth: true
            }
            Rectangle {
                id: coverMask
                anchors.fill: parent
                radius: Math.round(12 * widget.unit)
                visible: false
                layer.enabled: true
            }
            MultiEffect {
                anchors.fill: parent
                source: cover
                maskEnabled: true
                maskSource: coverMask
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
        }

        Column {
            anchors.left: coverBox.right
            anchors.leftMargin: Math.round(16 * widget.unit)
            anchors.right: parent.right
            anchors.rightMargin: Math.round(20 * widget.unit)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Math.round(4 * widget.unit)

            Row {
                spacing: Math.round(6 * widget.unit)
                // Three bars that move while playing — the only "live" cue.
                Repeater {
                    model: 3
                    Rectangle {
                        required property int index
                        width: Math.max(2, Math.round(3 * widget.unit))
                        height: Math.round(11 * widget.unit)
                        anchors.bottom: parent.bottom
                        radius: width / 2
                        color: "#00e676"
                        transformOrigin: Item.Bottom
                        scale: 0.4
                        SequentialAnimation on scale {
                            running: widget.playing && widget.visible
                            loops: Animation.Infinite
                            NumberAnimation { to: 1.0; duration: 380 + index * 120; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.35; duration: 420 + index * 90; easing.type: Easing.InOutSine }
                        }
                    }
                }
                Text {
                    text: widget.playing ? (widget.tr ? "ÇALIYOR" : "NOW PLAYING")
                                         : (widget.tr ? "DURAKLATILDI" : "PAUSED")
                    color: "#9a9a9a"
                    font.pixelSize: Math.max(9, Math.round(11 * widget.unit))
                    font.weight: Font.Bold
                    font.letterSpacing: 1.5
                    font.family: "Inter"
                }
            }

            Text {
                width: parent.width
                text: widget.track
                color: "#f5f5f5"
                font.pixelSize: Math.max(12, Math.round(19 * widget.unit))
                font.weight: Font.DemiBold
                font.family: "Inter"
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                text: widget.artist || widget.album
                color: "#b0b0b0"
                font.pixelSize: Math.max(10, Math.round(14 * widget.unit))
                font.family: "Inter"
                elide: Text.ElideRight
            }

            Item {
                width: parent.width
                height: Math.round(18 * widget.unit)
                visible: widget.length > 0

                Rectangle {
                    id: track
                    anchors.left: parent.left
                    anchors.right: elapsed.left
                    anchors.rightMargin: Math.round(10 * widget.unit)
                    anchors.verticalCenter: parent.verticalCenter
                    height: Math.max(2, Math.round(3 * widget.unit))
                    radius: height / 2
                    color: Qt.rgba(1, 1, 1, 0.15)
                    Rectangle {
                        height: parent.height
                        radius: parent.radius
                        width: parent.width * Math.max(0, Math.min(1, widget.shownPosition / widget.length))
                        color: "#f0f0f0"
                        Behavior on width { NumberAnimation { duration: 900 } }
                    }
                }
                Text {
                    id: elapsed
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: widget.fmt(widget.shownPosition) + " / " + widget.fmt(widget.length)
                    color: "#8a8a8a"
                    font.pixelSize: Math.max(9, Math.round(11 * widget.unit))
                    font.family: "Inter"
                    font.features: { "tnum": 1 }
                }
            }
        }
    }

    // ── lyrics strip ────────────────────────────────────────────────────────
    // The line being sung and the next one, in a second pane of glass that
    // sits on the side of the card away from the screen edge.
    Item {
        id: strip
        readonly property bool below: widget.corner === 0 || widget.corner === 1
        width: card.width
        height: Math.round(78 * widget.unit)
        x: card.x
        y: below ? card.y + card.height + Math.round(10 * widget.unit)
                 : card.y - height - Math.round(10 * widget.unit)
        opacity: widget.showLyrics ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 400 } }

        ShaderEffectSource {
            id: stripUnder
            anchors.fill: parent
            visible: false
            sourceItem: widget.backdropSource
            sourceRect: Qt.rect(strip.x, strip.y, strip.width, strip.height)
        }
        Rectangle {
            id: stripMask
            anchors.fill: parent
            radius: Math.round(16 * widget.unit)
            visible: false
            layer.enabled: true
        }
        MultiEffect {
            anchors.fill: parent
            source: stripUnder
            blurEnabled: true
            blurMax: 48
            blur: 1.0
            maskEnabled: true
            maskSource: stripMask
            autoPaddingEnabled: false
        }
        Rectangle {
            anchors.fill: parent
            radius: stripMask.radius
            color: Qt.rgba(0.04, 0.04, 0.04, 0.58)
            border.color: Qt.rgba(1, 1, 1, 0.09)
            border.width: 1
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: Math.round(18 * widget.unit)
            anchors.rightMargin: Math.round(18 * widget.unit)
            spacing: Math.round(4 * widget.unit)

            Text {
                id: nowLine
                width: parent.width
                text: widget.lyricIndex >= 0 ? (widget.lyricsLines[widget.lyricIndex].text || "♪") : "♪"
                color: "#ffffff"
                font.family: "Inter"
                font.weight: Font.Bold
                font.pixelSize: Math.max(12, Math.round(18 * widget.unit))
                elide: Text.ElideRight
                // a short fade on each new line
                onTextChanged: fadeIn.restart()
                NumberAnimation on opacity { id: fadeIn; from: 0.2; to: 1; duration: 300 }
            }
            Text {
                width: parent.width
                text: {
                    const i = widget.lyricIndex + 1;
                    return i < widget.lyricsLines.length ? widget.lyricsLines[i].text : "";
                }
                color: "#8a8a8a"
                font.family: "Inter"
                font.pixelSize: Math.max(10, Math.round(14 * widget.unit))
                elide: Text.ElideRight
            }
        }
    }
}

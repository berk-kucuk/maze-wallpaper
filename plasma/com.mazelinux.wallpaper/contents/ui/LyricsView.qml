/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    Scrolling lyrics: the current line bright and centred, the rest fading
    with distance, the list gliding to each new line.

    Synced (LRC) lyrics follow the playback position. Plain lyrics have no
    timestamps; they advance in proportion to how far into the song we are —
    approximate, and better than a wall of static text.
*/

import QtQuick
import QtQuick.Effects
import "lyrics.js" as Lyrics

Item {
    id: view

    property var lines: []
    property bool synced: false
    property real positionMs: 0
    property real lengthMs: 0
    property int fontSize: 32
    property int alignment: Text.AlignLeft

    readonly property int current: Lyrics.currentIndex(lines, synced, positionMs, lengthMs)

    ListView {
        id: list
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: fadeMask
        }
        model: view.lines
        interactive: false
        clip: true
        spacing: Math.round(view.fontSize * 0.55)
        currentIndex: Math.max(0, view.current)
        highlightRangeMode: ListView.StrictlyEnforceRange
        preferredHighlightBegin: height * 0.42
        preferredHighlightEnd: height * 0.42 + view.fontSize * 1.6
        highlightMoveDuration: 550
        highlightMoveVelocity: -1

        delegate: Text {
            required property var modelData
            required property int index
            readonly property int distance: Math.abs(index - view.current)

            width: ListView.view.width
            horizontalAlignment: view.alignment
            wrapMode: Text.WordWrap
            // empty LRC lines are instrumental breaks
            text: modelData.text || "♪"
            color: "#ffffff"
            font.family: "Inter"
            font.pixelSize: view.fontSize
            font.weight: index === view.current ? Font.Bold : Font.DemiBold
            opacity: index === view.current ? 1.0
                   : index < view.current ? Math.max(0.12, 0.35 - (distance - 1) * 0.08)
                   : Math.max(0.12, 0.5 - (distance - 1) * 0.1)
            scale: index === view.current ? 1.0 : 0.94
            transformOrigin: view.alignment === Text.AlignLeft ? Item.Left
                           : view.alignment === Text.AlignRight ? Item.Right : Item.Center
            Behavior on opacity { NumberAnimation { duration: 350 } }
            Behavior on scale { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
        }
    }

    // Fade the list out at the top and bottom edges — an alpha mask, so it
    // works over any backdrop.
    Rectangle {
        id: fadeMask
        anchors.fill: parent
        visible: false
        layer.enabled: true
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.2; color: "white" }
            GradientStop { position: 0.8; color: "white" }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }
}

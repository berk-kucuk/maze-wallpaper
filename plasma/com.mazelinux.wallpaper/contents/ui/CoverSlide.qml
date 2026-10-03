/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    One cover, in one of three styles:
      0  blurred, darkened cover filling the screen + the sharp cover centred
      1  the cover full-bleed, lightly darkened so the track info stays readable
      2  the sharp cover alone on true black (OLED)
*/

import QtQuick
import QtQuick.Effects

Item {
    id: slide

    property string url: ""
    property int style: 0
    property bool paused: false
    property int coverSize: 400
    property int coverOffset: 0
    property real coverShift: 0
    Behavior on coverShift { NumberAnimation { duration: 600; easing.type: Easing.InOutCubic } }

    readonly property bool ready: url !== "" && art.status === Image.Ready

    // Video thumbnails are 16:9; cropping them square cuts off half the
    // picture. Anything from square to 16:9 is shown at its own shape.
    readonly property real aspect: art.implicitHeight > 0
        ? Math.max(1, Math.min(16 / 9, art.implicitWidth / art.implicitHeight)) : 1
    readonly property real coverHeight: Math.round(coverSize * (aspect > 1.2 ? 0.85 : 1))

    // Fetches the cover at its full resolution (no sourceSize: covers are at
    // most a couple of thousand pixels, and scaling them to a fixed size on
    // load is what turns a 300 px cover into visible blocks). The visible
    // images below use the same source, so Qt's pixmap cache serves them this
    // copy — and `ready` only turns true once it exists.
    Image {
        id: art
        visible: false
        asynchronous: true
        cache: true
        source: slide.url
    }

    // ── backdrop ────────────────────────────────────────────────────────────
    Image {
        id: backdrop
        anchors.fill: parent
        visible: false
        layer.enabled: slide.style !== 2
        fillMode: Image.PreserveAspectCrop
        source: art.status === Image.Ready ? art.source : ""
        cache: true
    }

    MultiEffect {
        anchors.fill: parent
        visible: slide.style !== 2
        source: backdrop
        autoPaddingEnabled: false
        blurEnabled: slide.style === 0
        blurMax: 64
        blur: 1.0
        saturation: slide.style === 0 ? -0.15 : 0
        brightness: slide.style === 0 ? -0.35 : -0.15
    }

    // ── sharp cover ─────────────────────────────────────────────────────────
    Item {
        id: coverBox
        visible: slide.style !== 1
        height: slide.coverHeight
        width: Math.round(height * slide.aspect)
        anchors.centerIn: parent
        anchors.verticalCenterOffset: slide.coverOffset
        anchors.horizontalCenterOffset: slide.coverShift

        // Paused: shrink a touch and fade, the way a player dims a stopped track.
        scale: slide.paused ? 0.94 : 1.0
        opacity: slide.paused ? 0.7 : 1.0
        Behavior on scale { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 400 } }

        Image {
            id: sharp
            anchors.fill: parent
            fillMode: Image.PreserveAspectCrop
            source: art.status === Image.Ready ? art.source : ""
            cache: true
            smooth: true
            mipmap: true
            visible: false
            layer.enabled: true
            layer.smooth: true
        }

        Rectangle {
            id: roundMask
            anchors.fill: parent
            radius: Math.round(height * 0.035)
            antialiasing: true
            visible: false
            layer.enabled: true
        }

        // A separate shadow: MultiEffect ignores its mask while its own
        // shadow is on, which leaves the cover with square corners.
        RectangularShadow {
            anchors.fill: parent
            offset.y: Math.round(parent.height * 0.04)
            radius: roundMask.radius
            blur: Math.round(parent.height * 0.12)
            spread: 0
            color: "#cc000000"
        }

        MultiEffect {
            anchors.fill: parent
            source: sharp
            maskEnabled: true
            maskSource: roundMask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }
    }
}

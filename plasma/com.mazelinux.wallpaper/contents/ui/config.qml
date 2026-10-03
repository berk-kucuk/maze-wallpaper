/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    Plasma's own "Configure Desktop and Wallpaper" page for Maze Wallpaper.

    Picking and importing wallpapers is the Maze Wallpaper app's job; this page
    only carries the behaviour switches, so someone who lands here from the
    desktop's context menu can still turn media mode on without hunting for
    the app.
*/

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    id: page

    // Set by Plasma's wallpaper dialog on every config page; declared so the
    // dialog does not log "does not have a property" errors.
    property var configDialog
    property var wallpaperConfiguration

    property string cfg_Kind
    property string cfg_Source
    property int cfg_FillMode
    property bool cfg_Muted
    property int cfg_Volume
    property double cfg_PlaybackRate
    property int cfg_PauseMode
    property bool cfg_ActiveBlur
    property int cfg_BlurRadius
    property int cfg_ActiveDim
    property bool cfg_MediaMode
    property int cfg_MediaPlacement
    property int cfg_MediaCorner
    property int cfg_MediaWidgetSize
    property int cfg_MediaStyle
    property bool cfg_MediaShowInfo
    property bool cfg_MediaLyrics
    property bool cfg_MediaOnlyPlaying

    readonly property bool tr: Qt.locale().name.startsWith("tr")
    function t(en, trText) { return tr ? trText : en; }

    QQC2.Label {
        Kirigami.FormData.isSection: false
        Layout.fillWidth: true
        Layout.maximumWidth: Kirigami.Units.gridUnit * 26
        wrapMode: Text.WordWrap
        text: page.t("Choose wallpapers and add your own videos in the Maze Wallpaper app.",
                     "Duvar kâğıdı seçmek ve kendi videolarınızı eklemek için Maze Wallpaper uygulamasını kullanın.")
        opacity: 0.8
    }

    Item { Kirigami.FormData.isSection: true }

    QQC2.ComboBox {
        Kirigami.FormData.label: page.t("Fill:", "Doldurma:")
        model: [page.t("Stretch", "Uzat"), page.t("Fit", "Sığdır"), page.t("Crop", "Kırp")]
        currentIndex: Math.max(0, Math.min(2, page.cfg_FillMode))
        onActivated: index => page.cfg_FillMode = index
    }

    QQC2.ComboBox {
        Kirigami.FormData.label: page.t("Pause live wallpaper:", "Canlı duvar kâğıdını duraklat:")
        model: [page.t("Never", "Hiçbir zaman"),
                page.t("When a window is maximized", "Bir pencere ekranı kaplayınca"),
                page.t("When any window is focused", "Herhangi bir pencere odaktayken")]
        currentIndex: page.cfg_PauseMode
        onActivated: index => page.cfg_PauseMode = index
    }

    QQC2.CheckBox {
        Kirigami.FormData.label: page.t("Video sound:", "Video sesi:")
        text: page.t("Mute", "Sessiz")
        checked: page.cfg_Muted
        onToggled: page.cfg_Muted = checked
    }

    QQC2.Slider {
        Kirigami.FormData.label: page.t("Volume:", "Ses düzeyi:")
        enabled: !page.cfg_Muted
        from: 0; to: 100; stepSize: 5
        value: page.cfg_Volume
        onMoved: page.cfg_Volume = value
    }

    Item { Kirigami.FormData.isSection: true }

    QQC2.CheckBox {
        Kirigami.FormData.label: page.t("Active blur:", "Aktif bulanıklık:")
        text: page.t("Blur and dim while a window is focused", "Pencere odaktayken bulanıklaştır ve karart")
        checked: page.cfg_ActiveBlur
        onToggled: page.cfg_ActiveBlur = checked
    }

    QQC2.Slider {
        Kirigami.FormData.label: page.t("Blur strength:", "Bulanıklık:")
        enabled: page.cfg_ActiveBlur
        from: 8; to: 64; stepSize: 4
        value: page.cfg_BlurRadius
        onMoved: page.cfg_BlurRadius = value
    }

    QQC2.Slider {
        Kirigami.FormData.label: page.t("Dim:", "Karartma:")
        enabled: page.cfg_ActiveBlur
        from: 0; to: 80; stepSize: 5
        value: page.cfg_ActiveDim
        onMoved: page.cfg_ActiveDim = value
    }

    Item { Kirigami.FormData.isSection: true }

    QQC2.CheckBox {
        Kirigami.FormData.label: page.t("Media mode:", "Medya modu:")
        text: page.t("Show the cover of what is playing", "Çalan şarkının kapağını göster")
        checked: page.cfg_MediaMode
        onToggled: page.cfg_MediaMode = checked
    }

    QQC2.ComboBox {
        Kirigami.FormData.label: page.t("Show as:", "Gösterim:")
        enabled: page.cfg_MediaMode
        model: [page.t("Corner widget", "Köşe widget'ı"), page.t("Full screen", "Tam ekran")]
        currentIndex: page.cfg_MediaPlacement
        onActivated: index => page.cfg_MediaPlacement = index
    }

    QQC2.ComboBox {
        Kirigami.FormData.label: page.t("Corner:", "Köşe:")
        enabled: page.cfg_MediaMode && page.cfg_MediaPlacement === 0
        model: [page.t("Top right", "Sağ üst"), page.t("Top left", "Sol üst"),
                page.t("Bottom right", "Sağ alt"), page.t("Bottom left", "Sol alt")]
        currentIndex: page.cfg_MediaCorner
        onActivated: index => page.cfg_MediaCorner = index
    }

    QQC2.Slider {
        Kirigami.FormData.label: page.t("Widget size:", "Widget boyutu:")
        enabled: page.cfg_MediaMode && page.cfg_MediaPlacement === 0
        from: 60; to: 160; stepSize: 10
        value: page.cfg_MediaWidgetSize
        onMoved: page.cfg_MediaWidgetSize = value
    }

    QQC2.ComboBox {
        Kirigami.FormData.label: page.t("Full-screen style:", "Tam ekran stili:")
        enabled: page.cfg_MediaMode && page.cfg_MediaPlacement === 1
        model: [page.t("Blurred backdrop + cover", "Bulanık arka plan + kapak"),
                page.t("Full-screen cover", "Tam ekran kapak"),
                page.t("Cover on black (OLED)", "Siyah üzerinde kapak (OLED)")]
        currentIndex: page.cfg_MediaStyle
        onActivated: index => page.cfg_MediaStyle = index
    }

    QQC2.CheckBox {
        enabled: page.cfg_MediaMode
        text: page.t("Show track and artist", "Şarkı ve sanatçıyı göster")
        checked: page.cfg_MediaShowInfo
        onToggled: page.cfg_MediaShowInfo = checked
    }

    QQC2.CheckBox {
        enabled: page.cfg_MediaMode
        text: page.t("Scrolling lyrics (from lrclib.net)", "Kayan şarkı sözleri (lrclib.net'ten)")
        checked: page.cfg_MediaLyrics
        onToggled: page.cfg_MediaLyrics = checked
    }

    QQC2.CheckBox {
        enabled: page.cfg_MediaMode
        text: page.t("Only while playing (hide when paused)", "Yalnızca çalarken (duraklatınca gizle)")
        checked: page.cfg_MediaOnlyPlaying
        onToggled: page.cfg_MediaOnlyPlaying = checked
    }
}

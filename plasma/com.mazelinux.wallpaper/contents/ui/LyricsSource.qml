/*
    SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
    SPDX-License-Identifier: GPL-3.0-or-later

    Lyrics for the track that is playing, from LRCLIB (https://lrclib.net) —
    an open, free lyrics database with time-synced (LRC) lyrics, the same
    source most open-source desktop lyric tools use. Spotify's own lyrics sit
    behind a logged-in session cookie, which a wallpaper has no business
    holding.

    Off unless the user turns it on: enabling it sends the artist, title,
    album and length of what is playing to lrclib.net.

    Output:
      lines   [{ t: ms, text }]   sorted; t = -1 for every line when only
                                  unsynced (plain) lyrics exist
      synced  whether `lines` carry real timestamps
*/

import QtQuick

QtObject {
    id: src

    property bool enabled: false
    property string artist: ""
    property string title: ""
    property string album: ""
    property real lengthUs: 0

    property var lines: []
    property bool synced: false
    readonly property bool available: lines.length > 0

    // per-session memory, so skipping back to a song costs no request
    property var cache: ({})
    property int generation: 0

    readonly property string query: enabled && title ? [artist, title, album, Math.round(lengthUs / 1e6)].join("\u001f") : ""
    onQueryChanged: queryTimer.restart()

    // Players publish a new track's metadata in pieces; wait for it to settle.
    property Timer queryTimer: Timer {
        interval: 600
        onTriggered: src.lookup()
    }

    // ── cleanup for video titles ──────────────────────────────────────────
    // "Fontaines D.C. - Starburster (Official Video) [4K]" by channel
    // "Fontaines D.C." → artist "Fontaines D.C.", title "Starburster".
    function clean(artist, title) {
        let t = title.replace(/\s*[\(\[][^\)\]]*(official|video|audio|lyric|visuali[sz]er|mv|hd|4k|remaster|live)[^\)\]]*[\)\]]/gi, "")
                     .replace(/\s*\|.*$/, "")
                     .replace(/\s+(ft|feat)\.?\s.*$/i, "")
                     .trim();
        let a = artist.replace(/\s*-\s*topic$/i, "").replace(/VEVO$/, "").trim();
        const dash = t.match(/^(.+?)\s+[-–—]\s+(.+)$/);
        if (dash) {
            a = dash[1].trim();
            t = dash[2].trim();
        }
        return { artist: a, title: t };
    }

    function parseLrc(text) {
        const out = [];
        const re = /^\s*((?:\[\d+:\d+(?:[.:]\d+)?\])+)(.*)$/;
        for (const raw of text.split(/\r?\n/)) {
            const m = raw.match(re);
            if (!m) continue;
            const body = m[2].trim();
            const stamps = m[1].match(/\[(\d+):(\d+)(?:[.:](\d+))?\]/g);
            for (const st of stamps) {
                const p = st.match(/\[(\d+):(\d+)(?:[.:](\d+))?\]/);
                const frac = p[3] ? Number("0." + p[3]) : 0;
                out.push({ t: Math.round((Number(p[1]) * 60 + Number(p[2]) + frac) * 1000), text: body });
            }
        }
        out.sort((a, b) => a.t - b.t);
        return out;
    }

    function fromResult(r) {
        if (r && r.syncedLyrics) return { lines: parseLrc(r.syncedLyrics), synced: true };
        if (r && r.plainLyrics) {
            return {
                lines: r.plainLyrics.split(/\r?\n/).filter(l => l.trim() !== "").map(l => ({ t: -1, text: l.trim() })),
                synced: false
            };
        }
        return { lines: [], synced: false };
    }

    function finish(key, gen, result) {
        cache[key] = result;
        if (gen !== generation) return;   // the song changed while we waited
        lines = result.lines;
        synced = result.synced;
    }

    function request(url, gen, cb) {
        const xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE) return;
            if (gen !== src.generation) return;
            let data = null;
            if (xhr.status === 200) {
                try { data = JSON.parse(xhr.responseText); } catch (e) { data = null; }
            }
            cb(data);
        };
        xhr.open("GET", url);
        // LRCLIB asks clients to identify themselves.
        xhr.setRequestHeader("Lrclib-Client", "Maze Wallpaper (https://github.com/berk-kucuk/maze-wallpaper)");
        xhr.send();
    }

    function lookup() {
        generation++;
        const gen = generation;
        lines = [];
        synced = false;
        if (!query) return;
        const key = query;
        if (cache[key]) {
            finish(key, gen, cache[key]);
            return;
        }
        const c = clean(artist, title);
        const enc = encodeURIComponent;
        const base = "https://lrclib.net/api/";
        let get = base + "get?artist_name=" + enc(c.artist) + "&track_name=" + enc(c.title);
        if (album) get += "&album_name=" + enc(album);
        if (lengthUs > 0) get += "&duration=" + Math.round(lengthUs / 1e6);

        request(get, gen, function (exact) {
            if (exact && (exact.syncedLyrics || exact.plainLyrics)) {
                finish(key, gen, fromResult(exact));
                return;
            }
            // No exact match (common for video titles): search, and prefer a
            // synced result whose length is close to what is playing.
            const q = base + "search?track_name=" + enc(c.title) + (c.artist ? "&artist_name=" + enc(c.artist) : "");
            request(q, gen, function (list) {
                let best = null;
                if (Array.isArray(list)) {
                    const secs = lengthUs / 1e6;
                    const near = r => !secs || !r.duration || Math.abs(r.duration - secs) < 8;
                    best = list.find(r => r.syncedLyrics && near(r))
                        || list.find(r => r.syncedLyrics)
                        || list.find(r => r.plainLyrics) || null;
                }
                finish(key, gen, fromResult(best));
            });
        });
    }
}

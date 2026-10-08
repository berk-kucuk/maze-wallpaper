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
import "lyrics.js" as Lyrics

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

    // Each lookup gets a new generation; anything that answers for an older
    // one is dropped. Skipping through songs used to leave every old request
    // running, and Qt opens at most six connections to one host, so the song
    // actually playing queued behind requests for songs long gone.
    property int generation: 0
    property var want: ({})        // what this generation looks up: key, artist, title…
    property var inflight: []      // its open requests, as { kill() }
    property int attempt: 0
    property string owned: ""      // key this screen looks up on behalf of all screens

    readonly property string query: enabled && title ? [artist, title, album, Math.round(lengthUs / 1e6)].join("\u001f") : ""
    onQueryChanged: queryTimer.restart()

    // Players publish a new track's metadata in pieces; wait for it to settle.
    property Timer queryTimer: Timer {
        interval: 600
        onTriggered: src.lookup()
    }
    // LRCLIB answers in under a second; a request still open after this is
    // treated as failed rather than waited on forever.
    property Timer deadline: Timer {
        interval: 8000
        onTriggered: src.fail(src.generation, "timeout")
    }
    // Network errors, timeouts and rate limits are retried while the song
    // plays: after 2, 5 and 15 s.
    readonly property var backoff: [2000, 5000, 15000]
    property Timer retry: Timer {
        onTriggered: src.fetch(src.generation)
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

    // A screen removed mid-lookup must not leave the others waiting on it.
    Component.onDestruction: {
        abortAll();
        if (owned) Lyrics.settle(owned, null);
    }

    function show(result) {
        lines = result.lines;
        synced = result.synced;
    }

    function abortAll() {
        for (const r of inflight) r.kill();
        inflight = [];
    }

    // cb(status, json): status 0 for a network error, json null unless 200.
    function request(url, gen, cb) {
        const xhr = new XMLHttpRequest();
        let dead = false;
        const handle = { kill: function () { dead = true; xhr.abort(); } };
        inflight.push(handle);
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE || dead) return;
            const i = src.inflight.indexOf(handle);
            if (i >= 0) src.inflight.splice(i, 1);
            if (gen !== src.generation) return;
            let data = null;
            if (xhr.status === 200) {
                try { data = JSON.parse(xhr.responseText); } catch (e) { data = null; }
            }
            cb(xhr.status, data);
        };
        xhr.open("GET", url);
        // LRCLIB asks clients to identify themselves.
        xhr.setRequestHeader("Lrclib-Client", "Maze Wallpaper (https://github.com/berk-kucuk/maze-wallpaper)");
        xhr.send();
    }

    function lookup() {
        abortAll();
        retry.stop();
        deadline.stop();
        if (owned) {               // the other screens must not wait on a song we dropped
            Lyrics.settle(owned, null);
            owned = "";
        }
        generation++;
        attempt = 0;
        lines = [];
        synced = false;
        if (!query) return;
        const gen = generation;
        const c = clean(artist, title);
        want = { key: query, artist: c.artist, title: c.title, album: album,
                 secs: lengthUs > 0 ? Math.round(lengthUs / 1e6) : 0 };
        const hit = Lyrics.cached(want.key, Date.now());
        if (hit) {
            show(hit);
            return;
        }
        const busy = Lyrics.join(want.key, function (result) {
            if (gen !== src.generation) return;
            if (result === Lyrics.FAILED) return;   // it already retried for everyone
            if (result) show(result);
            else src.fetch(gen);   // that screen went away mid-lookup; take over
        });
        if (busy) return;
        owned = want.key;
        fetch(gen);
    }

    function fetch(gen) {
        if (gen !== generation) return;
        deadline.restart();
        const enc = encodeURIComponent;
        const base = "https://lrclib.net/api/";
        let get = base + "get?artist_name=" + enc(want.artist) + "&track_name=" + enc(want.title);
        if (want.album) get += "&album_name=" + enc(want.album);
        if (want.secs) get += "&duration=" + want.secs;

        request(get, gen, function (status, exact) {
            if (status === 200 && exact && (exact.syncedLyrics || exact.plainLyrics || exact.instrumental)) {
                done(gen, fromResult(exact));
                return;
            }
            // 404 is a real answer ("no exact match", common for video
            // titles); anything else is a failure worth retrying.
            if (status !== 200 && status !== 404) {
                fail(gen, "get " + status);
                return;
            }
            // Search, and prefer a synced result whose length is close to
            // what is playing.
            const q = base + "search?track_name=" + enc(want.title) + (want.artist ? "&artist_name=" + enc(want.artist) : "");
            request(q, gen, function (status, list) {
                if (status !== 200 || !Array.isArray(list)) {
                    fail(gen, "search " + status);
                    return;
                }
                const near = r => !want.secs || !r.duration || Math.abs(r.duration - want.secs) < 8;
                const best = list.find(r => r.syncedLyrics && near(r))
                    || list.find(r => r.syncedLyrics)
                    || list.find(r => r.plainLyrics) || null;
                done(gen, fromResult(best));
            });
        });
    }

    function done(gen, result) {
        if (gen !== generation) return;
        deadline.stop();
        Lyrics.store(want.key, result, Date.now());
        Lyrics.settle(want.key, result);
        owned = "";
        show(result);
        console.info("maze-wallpaper: lyrics", result.lines.length ? result.lines.length + (result.synced ? " synced" : " plain") + " lines"
                                                                     : "none on LRCLIB", "for", want.title);
    }

    function fail(gen, why) {
        if (gen !== generation) return;
        deadline.stop();
        abortAll();
        if (attempt < backoff.length) {
            retry.interval = backoff[attempt++];
            retry.restart();
            console.info("maze-wallpaper: lyrics", why, "for", want.title, "- retrying in", retry.interval / 1000, "s");
            return;
        }
        Lyrics.settle(want.key, Lyrics.FAILED);
        owned = "";
        console.warn("maze-wallpaper: lyrics", why, "for", want.title, "- giving up until the song plays again");
    }
}

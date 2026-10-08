// SPDX-FileCopyrightText: 2026 Berk Küçük <berkkucukk@proton.me>
// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

// Index of the line being sung at positionMs, or -1 before the first.
// Synced (LRC) lines: the last one whose timestamp has passed — a binary
// search, since songs run to 100+ lines and this re-evaluates several times
// a second. Plain lines carry no times: they advance in proportion to how
// far into the song we are.
function currentIndex(lines, synced, positionMs, lengthMs) {
    const n = lines ? lines.length : 0;
    if (n === 0) return -1;
    if (!synced) {
        if (lengthMs <= 0) return 0;
        return Math.min(n - 1, Math.floor(positionMs / lengthMs * n));
    }
    let lo = 0, hi = n - 1, ans = -1;
    while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (lines[mid].t <= positionMs + 150) { ans = mid; lo = mid + 1; } else { hi = mid - 1; }
    }
    return ans;
}

// ── shared lookup state ──────────────────────────────────────────────────────
// plasmashell runs one wallpaper per screen, and this file is a .pragma
// library: every screen shares one copy of what follows. A song is looked up
// once, not once per monitor, which also halves the load on LRCLIB.

// Only definitive answers are kept: lyrics, or LRCLIB saying it has none. A
// "none" is retried after a while, since the database keeps growing; network
// errors and rate limits are never stored, so they cannot stick to a song.
const NEGATIVE_MS = 30 * 60 * 1000;
var _results = {};   // key -> { lines, synced, at }
var _waiting = {};   // key -> [function(result | null)] while a lookup runs

function cached(key, now) {
    const r = _results[key];
    if (!r) return null;
    if (r.lines.length === 0 && now - r.at > NEGATIVE_MS) {
        delete _results[key];
        return null;
    }
    return r;
}

function store(key, result, now) {
    _results[key] = { lines: result.lines, synced: result.synced, at: now };
}

// What settle() hands the waiting screens when the lookup failed for good
// (after its retries); null instead means the screen doing it went away.
const FAILED = "failed";

// True when another screen is already looking `key` up: `fn` then gets its
// result, FAILED, or null (look it up yourself then).
// False means the caller does the lookup and must call settle() at the end.
function join(key, fn) {
    if (_waiting[key]) {
        _waiting[key].push(fn);
        return true;
    }
    _waiting[key] = [];
    return false;
}

function settle(key, result) {
    const fns = _waiting[key] || [];
    delete _waiting[key];
    for (const fn of fns) {
        try { fn(result); } catch (e) { /* that screen's wallpaper is gone */ }
    }
}

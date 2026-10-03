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

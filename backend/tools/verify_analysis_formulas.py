"""Verifikasi rumus klasifikasi & akurasi terhadap nilai emas Lichess.

Ticket: "Pipeline analisa Stockfish" (#12), ADR-0009.

Riset menemukan unit test Lichess sendiri (`AccuracyPercentTest.scala`) yang
memberi nilai emas siap pakai. Skrip ini mengimplementasikan rumus dari ADR-0009
dan memeriksanya terhadap nilai emas itu -- supaya klaim "terverifikasi" di ADR
benar-benar sudah diuji, bukan sekadar disalin.

Nilai emas (dari AccuracyPercentTest.scala):
    compute(Nil)                       -> None            (game kosong)
    compute(List(15))                  -> None            (1 ply)
    compute(List(15, 15))              -> putih ~100, hitam ~100
    compute(List.fill(20)(15) :+ -900) -> putih 50+-5, hitam 100+-1
    List.fill(50)(List(-135,15)).flat  -> keduanya 54+-8
    List.fill(50)(List(-435,15)).flat  -> keduanya 20+-8

Dijalankan dengan `python -I`.
"""

from __future__ import annotations

import math
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WP_MULTIPLIER = -0.00368208
CP_CEILING = 1000
A1, K1, B1 = 103.1668100711649, 0.04354415386753951, 3.166924740191411


def squeeze(x, lo, hi):
    return max(min(x, hi), lo)


def cp_to_win_percent(cp: int) -> float:
    """Win% pada skala 0-100, dengan clamp cp ke +-1000 lebih dulu."""
    cp = max(-CP_CEILING, min(CP_CEILING, cp))
    wc = 2.0 / (1.0 + math.exp(WP_MULTIPLIER * cp)) - 1.0
    wc = max(-1.0, min(1.0, wc))
    return 50.0 + 50.0 * wc


def move_accuracy(before: float, after: float) -> float:
    if after >= before:
        return 100.0
    win_diff = before - after
    raw = A1 * math.exp(-K1 * win_diff) + (-B1)
    return max(0.0, min(100.0, raw + 1.0))


def _stddev(xs):
    if not xs:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _weighted_mean(pairs):
    if not pairs:
        return None
    v = sum(a * w for a, w in pairs)
    w = sum(w for _, w in pairs)
    return v / w if w != 0 else None


def _harmonic_mean(xs):
    if not xs:
        return None
    return len(xs) / sum(1.0 / max(1.0, x) for x in xs)


def game_accuracy(win_percents, start_is_white=True):
    """win_percents: [initial_wp, wp_setelah_ply1, ...] pada skala 0-100."""
    n = len(win_percents) - 1
    window = squeeze(n // 10, 2, 8)
    lead = min(window, len(win_percents)) - 2
    windows = [win_percents[:window]] * lead + [
        win_percents[i:i + window] for i in range(len(win_percents) - window + 1)
    ]
    weights = []
    for w in windows:
        if any(x is None for x in w):
            weights.append(0.0)
        else:
            weights.append(squeeze(_stddev(w), 0.5, 12))

    per_color = {True: [], False: []}
    for i, (pair, weight) in enumerate(zip(zip(win_percents, win_percents[1:]), weights)):
        before, after = pair
        if before is None or after is None:
            continue
        is_white = ((i % 2 == 0) == start_is_white)
        b, a = (before, after) if is_white else (after, before)
        per_color[is_white].append((move_accuracy(b, a), weight))

    out = {}
    for side, entries in per_color.items():
        wm = _weighted_mean(entries)
        hm = _harmonic_mean([acc for acc, _ in entries])
        out[side] = None if (wm is None or hm is None) else (wm + hm) / 2
    if out[True] is None or out[False] is None:
        return None
    return out


def compute(cps, start_is_white=True):
    """cps = eval tiap langkah (centipawn, POV pelangkah). 15 = nilai awal Lichess."""
    wps = [cp_to_win_percent(15)] + [cp_to_win_percent(c) for c in cps]
    return game_accuracy(wps, start_is_white)


# ── Uji terhadap nilai emas Lichess ────────────────────────────────────────
RESULTS = []


def check(label, actual, expected, tol=None):
    if expected is None:
        ok = actual is None
        detail = f"{actual}"
    else:
        if actual is None:
            ok, detail = False, "None"
        else:
            ok = abs(actual - expected) <= (tol or 0)
            detail = f"{actual:.2f} (harap {expected}+-{tol})"
    RESULTS.append((label, ok))
    print(f"  [{'OK ' if ok else 'GAGAL'}] {label:52s} {detail}")


print("=== Nilai emas dari AccuracyPercentTest.scala (Lichess) ===")
check("compute(Nil) -> None (game kosong)", compute([]), None)
check("compute([15]) -> None (1 ply)", compute([15]), None)
r = compute([15, 15])
check("compute([15,15]) putih ~100", r[True] if r else None, 100, 1)
check("compute([15,15]) hitam ~100", r[False] if r else None, 100, 1)
r = compute([15] * 20 + [-900])
check("fill(20)(15)+[-900] putih ~50", r[True] if r else None, 50, 5)
check("fill(20)(15)+[-900] hitam ~100", r[False] if r else None, 100, 1)
r = compute([v for _ in range(50) for v in (-135, 15)])
check("fill(50)([-135,15]) keduanya ~54 (putih)", r[True] if r else None, 54, 8)
check("fill(50)([-135,15]) keduanya ~54 (hitam)", r[False] if r else None, 54, 8)
r = compute([v for _ in range(50) for v in (-435, 15)])
check("fill(50)([-435,15]) keduanya ~20 (putih)", r[True] if r else None, 20, 8)
check("fill(50)([-435,15]) keduanya ~20 (hitam)", r[False] if r else None, 20, 8)

print()
print("=== Win-chance: nilai kunci ===")
for cp in (0, 100, 300, 1000, -1000):
    print(f"  cp={cp:>6} -> win% {cp_to_win_percent(cp):7.3f}")
print(f"  mate (via +-1000cp) -> {cp_to_win_percent(1000):.3f}% / "
      f"{cp_to_win_percent(-1000):.3f}%")

print()
print("=== Klasifikasi: selisih win-chance dari sudut pandang pelangkah ===")


def classify(prev_cp, curr_cp, mover_is_white=True):
    """Klasifikasi dari selisih win-chance, dibalik ke sudut pandang PELANGKAH.

    Catatan POV -- sumber bug klasik. Di Lichess:

        delta = (curr_wc - prev_wc).pipe(d => info.color.fold(-d, d))

    `info.color` adalah warna pemain YANG AKAN MELANGKAH di posisi `info`,
    yaitu LAWAN dari pelangkah yang baru saja bergerak. Jadi untuk pelangkah
    PUTIH (`info.color` = hitam), delta = -(curr - prev) = prev - curr.

    Ringkasnya: delta positif berarti win-chance PELANGKAH turun, yaitu
    langkah yang buruk. Itulah yang dibandingkan dengan ambang 0.1/0.2/0.3.
    """
    prev_wc = (cp_to_win_percent(prev_cp) / 50.0) - 1.0
    curr_wc = (cp_to_win_percent(curr_cp) / 50.0) - 1.0
    raw = curr_wc - prev_wc
    # Dibalik ke sudut pandang pelangkah: positif = pelangkah kehilangan.
    d = raw if not mover_is_white else -raw
    for thr, name in ((0.3, "Blunder"), (0.2, "Mistake"), (0.1, "Inaccuracy")):
        if d >= thr:
            return name, d
    return "—", d


for prev, curr, who in ((0, -350, "putih"), (0, -350, "hitam"),
                        (0, -150, "putih"), (0, -60, "putih"),
                        (800, 400, "putih")):
    name, d = classify(prev, curr, who == "putih")
    print(f"  {who:5s}: {prev:>5}cp -> {curr:>5}cp  delta={d:+.4f}  {name}")

print()
print("=== Kasus yang membuktikan perlunya tangga mate ===")
# Dari mate paksa (97.545%) menjadi +900cp (96.49%)
mate_wc = (cp_to_win_percent(1000) / 50.0) - 1.0
after_wc = (cp_to_win_percent(900) / 50.0) - 1.0
d = mate_wc - after_wc
print(f"  Mate paksa -> +9,0 pion: delta win-chance = {d:.4f}")
print(f"  Ambang Inaccuracy = 0.1000  ->  {'TIDAK terklasifikasi' if d < 0.1 else 'terklasifikasi'}")
print("  => membuang skakmat paksa lolos tanpa penilaian; karena itu ADR-0009")
print("     memakai tangga MateCreated/MateLost tersendiri.")

print()
print("=== Posisi sudah kalah telak (mengapa tidak butuh filter) ===")
for prev, curr in ((-2000, -3000), (-1500, -2500), (-800, -1800)):
    d = abs(((cp_to_win_percent(curr) / 50.0) - 1.0) - ((cp_to_win_percent(prev) / 50.0) - 1.0))
    print(f"  {prev:>6}cp -> {curr:>6}cp  delta={d:.6f}  "
          f"{'di bawah ambang 0.1' if d < 0.1 else 'DI ATAS ambang'}")

print()
gagal = [r for r in RESULTS if not r[1]]
print(f"RINGKASAN: {len(RESULTS) - len(gagal)}/{len(RESULTS)} uji emas Lichess LOLOS")
if gagal:
    for label, _ in gagal:
        print(f"  GAGAL: {label}")
    sys.exit(1)

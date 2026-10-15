"""Benchmark Stockfish pada anggaran node yang diusulkan.

Ticket: "Pipeline analisa Stockfish" (#12), pertanyaan Q5.

Riset #3 hanya memberi ESTIMASI waktu ke depth 18/20 ("tidak ada benchmark
resmi"). Karena Q5 memilih `go nodes`, yang perlu diukur bukan depth, melainkan
berapa detik yang benar-benar dihabiskan ~1 juta node pada posisi nyata, dan
berapa besar variasi antar-posisi.

Dijalankan dengan `python -I` supaya tidak memuat modul dari cwd.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import chess
import chess.engine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENGINE = Path(sys.argv[1]).resolve()
THREADS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
HASH_MB = int(sys.argv[3]) if len(sys.argv) > 3 else 128

# Posisi uji: campuran pembukaan, middlegame taktis, dan endgame.
POSITIONS = {
    "pembukaan (setelah 1.e4 e5 2.Nf3)": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
    "middlegame taktis (Najdorf)": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
    "posisi tajam (kompleks)": "r1bqkb1r/pp1n1ppp/2n1p3/3pP3/3P4/2N2N2/PP3PPP/R1BQKB1R w KQkq - 0 8",
    "endgame raja-bidak": "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1",
    "endgame menara": "8/5pk1/6p1/8/8/6P1/5PK1/3R4 w - - 0 1",
}

BUDGETS = [300_000, 1_000_000, 3_000_000]

print(f"Engine   : {ENGINE}")
print(f"Threads  : {THREADS}   Hash: {HASH_MB} MB")
print()

engine = chess.engine.SimpleEngine.popen_uci(str(ENGINE))
try:
    engine.configure({"Threads": THREADS, "Hash": HASH_MB})
    name = engine.id.get("name", "?")
    print(f"Teridentifikasi: {name}")
    print()

    for budget in BUDGETS:
        print(f"=== go nodes {budget:,} ===")
        times = []
        for label, fen in POSITIONS.items():
            board = chess.Board(fen)
            t0 = time.perf_counter()
            info = engine.analyse(board, chess.engine.Limit(nodes=budget))
            dt = time.perf_counter() - t0
            times.append(dt)
            score = info["score"].white()
            depth = info.get("depth", "?")
            nodes = info.get("nodes", 0)
            nps = int(nodes / dt) if dt > 0 else 0
            print(f"  {label:38s} {dt:6.2f}s  depth={depth:>3} nps={nps:>9,}  eval={score}")
        print(f"  --> median {statistics.median(times):.2f}s, "
              f"min {min(times):.2f}s, max {max(times):.2f}s")
        print()

    # Proyeksi durasi game penuh
    print("=== PROYEKSI DURASI GAME PENUH (81 posisi untuk game 40 langkah) ===")
    for budget in BUDGETS:
        board = chess.Board()
        t0 = time.perf_counter()
        engine.analyse(board, chess.engine.Limit(nodes=budget))
        per_pos = time.perf_counter() - t0
        print(f"  {budget:>10,} node/posisi -> ~{per_pos:.2f}s x 81 = "
              f"~{per_pos * 81 / 60:.1f} menit/game  |  8 game turnamen = "
              f"~{per_pos * 81 * 8 / 60:.0f} menit antrian")
finally:
    engine.quit()
    print("\nEngine ditutup dengan bersih.")

"""PROTOTYPE — cek logika room tanpa server. Bukan bagian runtime.

Jalankan:  .venv\\Scripts\\python.exe -I tests\\prototype_check.py
"""

from __future__ import annotations

import sys

import chess

from chessbot.prototype_activity import Room

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK   {label}")
    else:
        FAIL += 1
        print(f"  GAGAL {label}  {detail}")


print("== validasi langkah otoritatif ==")

r = Room(instance_id="t1")

# 1. Langkah legal diterima.
e = r.apply_move(chess.WHITE, "e2", "e4", None)
check("e2e4 diterima", e["san"] == "e4", e["san"])
check("FEN bergerak", r.board.fen().startswith("rnbqkbnr/pppppppp/8/8/4P3"), r.board.fen())
check("giliran pindah ke hitam", r.board.turn == chess.BLACK)

# 2. Giliran salah ditolak.
try:
    r.apply_move(chess.WHITE, "d2", "d4", None)
    check("putih melangkah dua kali ditolak", False)
except ValueError as exc:
    check("putih melangkah dua kali ditolak", "giliran" in str(exc), str(exc))

# 3. Langkah ilegal ditolak (bidak tak bisa mundur).
try:
    r.apply_move(chess.BLACK, "e7", "e5", None)
    r.apply_move(chess.WHITE, "e4", "e2", None)
    check("bidak mundur ditolak", False)
except chess.IllegalMoveError:
    check("bidak mundur ditolak", True)

# 4. Kotak sampah ditolak dengan pesan ramah.
try:
    r.apply_move(chess.WHITE, "z9", "e4", None)
    check("kotak sampah ditolak", False)
except ValueError as exc:
    check("kotak sampah ditolak", "tidak dikenal" in str(exc), str(exc))

# 5. Kotak tujuan legal — terbatas pada sisi yang gilirannya.
#    Room bersih: setelah 1.e4, giliran hitam, bidak e7 bisa maju satu atau dua.
rl = Room(instance_id="t-legal")
rl.apply_move(chess.WHITE, "e2", "e4", None)
targets = rl.legal_targets("e7")
check("target legal dari e7 (giliran hitam)", "e6" in targets and "e5" in targets, str(targets))
check("bidak putih e4 tidak punya target (bukan gilirannya)", rl.legal_targets("e4") == [], str(rl.legal_targets("e4")))
check("target dari kotak kosong = kosong", rl.legal_targets("a3") == [], str(rl.legal_targets("a3")))

print("== skakmat (scholar's mate) ==")

r2 = Room(instance_id="t2")
for frm, to in [
    ("e2", "e4"), ("e7", "e5"), ("f1", "c4"), ("b8", "c6"),
    ("d1", "h5"), ("g8", "f6"), ("h5", "f7"),
]:
    r2.apply_move(r2.board.turn, frm, to, None)

check("skakmat terdeteksi", r2.status == "checkmate", r2.status)
check("pemenang putih", r2.winner == "white", str(r2.winner))
check("alasan = skakmat", r2.end_reason == "skakmat", str(r2.end_reason))

# 6. Langkah setelah game berakhir ditolak.
try:
    r2.apply_move(r2.board.turn, "a7", "a6", None)
    check("langkah setelah skakmat ditolak", False)
except ValueError as exc:
    check("langkah setelah skakmat ditolak", "berakhir" in str(exc), str(exc))

print("== promosi ==")

r3 = Room(instance_id="t3")
r3.board = chess.Board("8/P6k/8/8/8/8/8/K7 w - - 0 1")
e3 = r3.apply_move(chess.WHITE, "a7", "a8", "q")
check("promosi ke ratu", e3["san"].startswith("a8=Q"), e3["san"])
check("promosi tercatat", e3["promotion"] == "q", str(e3["promotion"]))

print("== remis materi tidak cukup ==")

r4 = Room(instance_id="t4")
r4.board = chess.Board("7k/8/8/8/8/8/8/K6N w - - 0 1")
r4.board.push_uci("h1f2")
r4._settle_outcome()
check("materi tidak cukup = remis", r4.status == "draw", r4.status)

print("== muatan state ==")

r5 = Room(instance_id="t5")
r5.white.discord_id = "u1"
r5.white.username = "Putih"
r5.black.is_bot = True
p = r5.payload_for(None)
for key in ("fen", "turn", "status", "history", "players", "yourColor", "lastMove"):
    check(f"payload punya '{key}'", key in p)
check("penonton yourColor = None", p["yourColor"] is None, str(p["yourColor"]))
check("bot terlihat di players", p["players"]["black"]["isBot"] is True)

print()
print(f"lulus {PASS}, gagal {FAIL}")
sys.exit(1 if FAIL else 0)

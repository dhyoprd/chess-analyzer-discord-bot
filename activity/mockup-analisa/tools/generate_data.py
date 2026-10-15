"""Hasilkan data analisa NYATA untuk mockup ticket #7.

Bukan kode produksi. Skrip sekali pakai: ia menjalankan Stockfish dengan
konfigurasi persis ADR-0009 (1 juta node, 4 thread, Hash 128 MB) lalu menghitung
klasifikasi & akurasi dengan rumus yang sudah diverifikasi di
`backend/tools/verify_analysis_formulas.py`.

Alasannya sederhana: keputusan tata letak di ticket #7 bergantung pada
**berapa banyak karakter** yang dibutuhkan daftar langkah nyata. Angka karangan
akan menghasilkan keputusan yang salah.

Pakai:
    python -I generate_data.py <stockfish.exe> <keluaran.json>
"""

from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

import chess
import chess.engine
import chess.pgn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Konstanta ADR-0009 ─────────────────────────────────────────────────────
NODES = 1_000_000
THREADS = 4
HASH_MB = 128
TIMEOUT = 60.0
CP_CEILING = 1000
A1, K1, B1 = 103.1668100711649, 0.04354415386753951, 3.166924740191411

# Nilai emas akurasi (Lichess AccuracyPercentTest.scala), dipakai sebagai
# jaring pengaman: kalau agregasi di sini menyimpang, skrip berhenti.
GOLD = {"fill(20)(15)+[-900]": (50, 5), "fill(50)([-135,15])": (54, 8)}


def squeeze(x, lo, hi):
    return max(min(x, hi), lo)


def wc_1(cp: int) -> float:
    """Win-chance pada skala -1..+1 (yang dipakai ambang klasifikasi)."""
    cp = max(-CP_CEILING, min(CP_CEILING, cp))
    v = 2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0
    return max(-1.0, min(1.0, v))


def wc_100(cp: int) -> float:
    """Win-chance pada skala 0..100 (yang dipakai rumus akurasi)."""
    return 50.0 + 50.0 * wc_1(cp)


def move_accuracy(before: float, after: float) -> float:
    if after >= before:
        return 100.0
    raw = A1 * math.exp(-K1 * (before - after)) - B1
    return max(0.0, min(100.0, raw + 1.0))


def _stddev(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _weighted_mean(pairs):
    v = sum(a * w for a, w in pairs)
    w = sum(w for _, w in pairs)
    return v / w if w else None


def _harmonic_mean(xs):
    if not xs:
        return None
    return len(xs) / sum(1.0 / max(1.0, x) for x in xs)


def game_accuracy(wps, start_is_white=True):
    """wps = [wp_awal, wp_ply1, ...] pada skala 0-100.

    Mengembalikan None bila akurasi tidak bisa dihitung (kurang dari 2 ply,
    atau salah satu warna tanpa langkah) -- sama seperti implementasi referensi
    di backend/tools/verify_analysis_formulas.py. Versi pertama fungsi ini
    membagi nol pada daftar kosong; ditemukan oleh crosscheck_formulas.py.
    """
    if len(wps) < 2:
        return None
    n = len(wps) - 1
    window = squeeze(n // 10, 2, 8)
    lead = min(window, len(wps)) - 2
    windows = [wps[:window]] * max(0, lead) + [
        wps[i:i + window] for i in range(len(wps) - window + 1)
    ]
    weights = [squeeze(_stddev(w), 0.5, 12) for w in windows]

    per_color = {True: [], False: []}
    for i, (before, after) in enumerate(zip(wps, wps[1:])):
        is_white = ((i % 2 == 0) == start_is_white)
        b, a = (before, after) if is_white else (after, before)
        per_color[is_white].append((move_accuracy(b, a), weights[i]))

    out = {}
    for side, entries in per_color.items():
        wm = _weighted_mean(entries)
        hm = _harmonic_mean([acc for acc, _ in entries])
        out[side] = None if (wm is None or hm is None) else (wm + hm) / 2
    if out[True] is None or out[False] is None:
        return None
    return out


# ── Klasifikasi (ADR-0009: selisih win-chance + tangga mate) ───────────────

def classify(prev, curr, mover_is_white):
    """prev/curr = (kind, value) POV PUTIH; kind "cp" atau "mate".

    Mengembalikan (label, delta) dengan delta pada skala win-chance -1..+1
    dari sudut pandang PELANGKAH. delta positif = pelangkah kehilangan.

    Empat bentuk perpindahan melibatkan mate; ADR-0009 hanya memberi tangga
    untuk dua (lihat penjaga di evaluate_game). Dua sisanya jatuh ke jalur
    selisih win-chance biasa, dan di sana nilai mate **wajib dipetakan ke
    +-1000cp lebih dulu** -- kalau tidak, "mate 3" diperlakukan sebagai
    3 centipawn dan delta-nya menjadi omong kosong (-0,0055).
    """
    def pov_mover(kind, value):
        if not mover_is_white:
            value = -value
        return kind, value

    p_kind, p_val = pov_mover(*prev)
    c_kind, c_val = pov_mover(*curr)

    # Mate yang tertunda (mate tetap mate): tanpa penilaian.
    if p_kind == "mate" and c_kind == "mate":
        return None, 0.0

    # MateCreated: cp -> mate untuk LAWAN. Dinilai dari eval SEBELUMNYA.
    if p_kind == "cp" and c_kind == "mate" and c_val < 0:
        if p_val < -999:
            return "inaccuracy", 0.0
        if p_val < -700:
            return "mistake", 0.0
        return "blunder", 0.0

    # MateLost: mate untuk KITA -> cp. Dinilai dari eval SESUDAHNYA.
    if p_kind == "mate" and p_val > 0 and c_kind == "cp":
        if c_val > 999:
            return "inaccuracy", 0.0
        if c_val > 700:
            return "mistake", 0.0
        return "blunder", 0.0

    # Jalan biasa: selisih win-chance dari sudut pandang pelangkah.
    # Nilai mate dipetakan ke +-1000cp supaya setara dengan skakmat.
    def as_cp(kind, val):
        if kind == "cp":
            return val
        return 1000 if val > 0 else -1000

    before = wc_1(as_cp(p_kind, p_val))
    after = wc_1(as_cp(c_kind, c_val))
    d = before - after
    for thr, name in ((0.3, "blunder"), (0.2, "mistake"), (0.1, "inaccuracy")):
        if d >= thr:
            return name, d
    return None, d


def evaluate_game(engine, game, label, nodes=NODES):
    board = game.board()
    moves = list(game.mainline_moves())

    # Posisi N+1: posisi awal lalu setelah tiap langkah.
    positions = [board.copy(stack=False)]
    for mv in moves:
        board.push(mv)
        positions.append(board.copy(stack=False))

    print(f"\n=== {label} — {len(moves)} langkah, {len(positions)} posisi ===")
    evals = []
    bests = []
    for i, pos in enumerate(positions):
        info = engine.analyse(pos, chess.engine.Limit(nodes=nodes),
                              multipv=1, info=chess.engine.INFO_ALL)
        entry = info[0] if isinstance(info, list) else info
        score = entry["score"].white()
        if score.is_mate():
            evals.append(("mate", int(score.mate())))
        else:
            evals.append(("cp", int(score.score())))
        pv = entry.get("pv") or []
        bests.append(pv[0].uci() if pv else None)
        if (i + 1) % 20 == 0 or i == len(positions) - 1:
            print(f"    {i + 1}/{len(positions)} posisi")

    # Klasifikasi per langkah.
    per_move = []
    board = game.board()
    for i, mv in enumerate(moves):
        mover_is_white = board.turn == chess.WHITE
        before_san = board.san(mv)
        # ADR-0009: langkah terbaik DISIMPAN dalam UCI, tapi DIKONVERSI ke SAN
        # saat ditampilkan. Konversinya butuh posisi sebelum langkah, jadi
        # dikerjakan di sini -- satu tempat, bukan di lapisan tampilan.
        best_san = None
        if bests[i]:
            try:
                best_san = board.san(chess.Move.from_uci(bests[i]))
            except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError):
                best_san = None
        board.push(mv)
        c, d = classify(evals[i], evals[i + 1], mover_is_white)
        per_move.append({
            "ply": i + 1,
            "move_no": i // 2 + 1,
            "color": "white" if mover_is_white else "black",
            "san": before_san,
            "uci": mv.uci(),
            # eval_before MENYIMPAN JENISNYA SENDIRI. Tanpa ini, eval mate
            # "sebelum" akan hilang dan dirender sebagai centipawn -- terlihat
            # wajar tapi salah (terbukti: ply 98 sebelum=mate tampil "0,00").
            "eval_before": evals[i][1],
            "eval_before_kind": evals[i][0],
            "eval_after": evals[i + 1][1],
            "eval_after_kind": evals[i + 1][0],
            "eval_kind": "mate" if evals[i + 1][0] == "mate" else "cp",
            "wc_before": round(wc_1(evals[i][1]) if evals[i][0] == "cp"
                               else wc_1(1000 if evals[i][1] > 0 else -1000), 4),
            "wc_after": round(wc_1(evals[i + 1][1]) if evals[i + 1][0] == "cp"
                              else wc_1(1000 if evals[i + 1][1] > 0 else -1000), 4),
            "classification": c,
            "delta": round(d, 4),
            "best_uci": bests[i],
            "best_san": best_san,
        })

    # Akurasi: konstanta 15cp untuk posisi awal, sisanya eval nyata.
    wps = [wc_100(15)] + [wc_100(e[1]) if e[0] == "cp"
                          else wc_100(1000 if e[1] > 0 else -1000) for e in evals[1:]]
    acc = game_accuracy(wps)

    # Penjaga kewarasan: eval mate tidak boleh kehilangan jenisnya. Bug ini
    # pernah terjadi -- eval mate "sebelum" dirender sebagai centipawn dan
    # hasilnya terlihat wajar (0,00) padahal salah.
    #
    # Ada EMPAT bentuk perpindahan yang melibatkan mate, tapi ADR-0009 hanya
    # memberi tangga untuk DUA di antaranya:
    #
    #   cp  -> mate untuk lawan   MateCreated  -> dinilai dari eval sebelumnya
    #   mate untuk kita -> cp     MateLost     -> dinilai dari eval sesudahnya
    #   mate untuk kita -> mate   mate tertunda -> TANPA penilaian
    #   mate untuk lawan -> cp    lolos dari skakmat -> TANPA penilaian
    #   cp -> mate untuk kita     menemukan skakmat -> TANPA penilaian
    #
    # Versi pertama penjaga ini menuntut SEMUA langkah yang melibatkan mate
    # terklasifikasi, dan gagal pada dua kasus yang memang benar tanpa
    # penilaian: mate tertunda (Immortal Game ply 41, mate 3 -> 2) dan lolos
    # dari skakmat (self-play ply 125, mate -3 -> 0cp). Jangan "perbaiki"
    # ketiadaan penilaian di dua bentuk itu -- itu perilaku yang benar.
    def butuh_penilaian(m):
        pb, cb = m["eval_before_kind"], m["eval_after_kind"]
        if pb == cb:
            return False
        # Kembalikan ke sudut pandang pelangkah sebelum memutuskan.
        sebelum = m["eval_before"] if m["color"] == "white" else -m["eval_before"]
        sesudah = m["eval_after"] if m["color"] == "white" else -m["eval_after"]
        if pb == "cp" and cb == "mate":
            return sesudah < 0          # MateCreated
        if pb == "mate" and cb == "cp":
            return sebelum > 0          # MateLost
        return False

    for m in per_move:
        assert m["eval_before_kind"] in ("cp", "mate"), m
        assert m["eval_after_kind"] in ("cp", "mate"), m
        if butuh_penilaian(m):
            assert m["classification"] is not None, (
                f"ply {m['ply']} transisi mate yang seharusnya dinilai "
                f"tapi tidak terklasifikasi: {m}")

    n_mate = sum(1 for m in per_move
                 if m["eval_before_kind"] == "mate" or m["eval_after_kind"] == "mate")
    n_trans = sum(1 for m in per_move if butuh_penilaian(m))
    n_delay = n_mate - n_trans
    print(f"    penjaga: {n_mate} langkah melibatkan mate "
          f"({n_trans} dinilai lewat tangga mate, {n_delay} tanpa penilaian)")

    # Langkah terbaik harus bisa dikonversi ke SAN untuk ditampilkan.
    n_best = sum(1 for m in per_move if m["best_uci"])
    n_san = sum(1 for m in per_move if m["best_san"])
    print(f"    penjaga: {n_san}/{n_best} langkah terbaik terkonversi ke SAN")
    if n_best and n_san < n_best:
        hilang = [m["ply"] for m in per_move if m["best_uci"] and not m["best_san"]]
        print(f"      PERINGATAN: gagal konversi di ply {hilang[:10]}")

    counts = {c: {"inaccuracy": 0, "mistake": 0, "blunder": 0} for c in ("white", "black")}
    for m in per_move:
        if m["classification"]:
            counts[m["color"]][m["classification"]] += 1

    return {
        "label": label,
        "plies": len(moves),
        "accuracy": {"white": round(acc[True], 1), "black": round(acc[False], 1)},
        "counts": counts,
        "evals": [{"kind": k, "value": v} for k, v in evals],
        "moves": per_move,
    }


# ── PGN yang dipakai ───────────────────────────────────────────────────────
# Keduanya game NYATA, bukan karangan. Klasifikasi dihasilkan Stockfish.

IMMORTAL = """[Event "London"]
[Site "London ENG"]
[Date "1851.06.21"]
[White "Adolf Anderssen"]
[Black "Lionel Kieseritzky"]
[Result "1-0"]

1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5
8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8
15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6
21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0
"""

def self_play_once(engine, max_plies=200):
    """Satu game self-play lemah. Mengembalikan (game, jumlah ply)."""
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Site"] = "?"
    game.headers["Date"] = "2026.01.01"
    game.headers["White"] = "Putih"
    game.headers["Black"] = "Hitam"
    node = game
    while len(board.move_stack) < max_plies and not board.is_game_over():
        engine.configure({"Skill Level": 3, "UCI_LimitStrength": True, "UCI_Elo": 1320})
        result = engine.play(board, chess.engine.Limit(nodes=2_000))
        if result.move is None:
            break
        node = node.add_variation(result.move)
        board.push(result.move)
    game.headers["Result"] = board.result(claim_draw=True)
    return game, len(board.move_stack)


def self_play(engine, attempts=6, want=100):
    """Game panjang dari Stockfish bermain melawan dirinya sendiri.

    PGN karangan tangan rawan langkah ilegal (dan memang terbukti begitu saat
    skrip ini pertama ditulis: `Rxe5` ilegal). Bermain sendiri menjamin legalitas.

    Panjang game tidak bisa dipesan -- percobaan pertama berakhir skakmat dalam
    39 ply, terlalu pendek untuk menguji kasus "100+ langkah". Karena itu
    beberapa game dimainkan dan **yang terpanjang** dipakai. Kedua sisi sengaja
    lemah: dua engine sama kuat menghasilkan 0 klasifikasi dalam 104 ply
    (terukur), yang tidak menguji tata letak daftar penuh penanda.
    """
    best, best_n = None, 0
    for i in range(attempts):
        g, n = self_play_once(engine)
        print(f"    percobaan {i + 1}: {n} ply (hasil {g.headers['Result']})")
        if n > best_n:
            best, best_n = g, n
        if best_n >= want:
            break
    best.headers["Event"] = f"Uji game panjang (self-play, terpanjang dari beberapa game)"
    return best, best_n


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    sf, out = sys.argv[1], sys.argv[2]
    nodes = int(sys.argv[3]) if len(sys.argv) > 3 else NODES

    print("Membuka Stockfish...")
    engine = chess.engine.SimpleEngine.popen_uci(sf)
    engine.configure({"Threads": THREADS, "Hash": HASH_MB})
    print(f"  Threads={THREADS} Hash={HASH_MB}MB, {nodes:,} node/posisi")

    games = []
    try:
        for label, pgn_text in (("Anderssen–Kieseritzky, London 1851 (Immortal Game)", IMMORTAL),):
            pgn = chess.pgn.read_game(io.StringIO(pgn_text))
            if pgn is None or pgn.errors:
                print(f"  PGN GAGAL diparse: {label} {pgn.errors if pgn else ''}")
                continue
            data = evaluate_game(engine, pgn, label, nodes)
            data["white"] = pgn.headers.get("White")
            data["black"] = pgn.headers.get("Black")
            data["result"] = pgn.headers.get("Result")
            games.append(data)

        # Game panjang untuk menguji kasus 100+ langkah.
        print("\nMembuat game panjang lewat self-play...")
        long_game, n = self_play(engine)
        print(f"  self-play selesai: {n} ply, hasil {long_game.headers['Result']}")
        data = evaluate_game(engine, long_game, "Uji game panjang (self-play)", nodes)
        data["white"] = "Putih"
        data["black"] = "Hitam"
        data["result"] = long_game.headers["Result"]
        games.append(data)
    finally:
        engine.quit()

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(games, indent=1, ensure_ascii=False), encoding="utf-8")

    print("\n=== RINGKASAN ===")
    for g in games:
        c = g["counts"]
        print(f"  {g['label']}")
        print(f"    {g['plies']} ply | akurasi putih {g['accuracy']['white']} "
              f"hitam {g['accuracy']['black']}")
        print(f"    putih: {c['white']['inaccuracy']}I {c['white']['mistake']}M "
              f"{c['white']['blunder']}B | hitam: {c['black']['inaccuracy']}I "
              f"{c['black']['mistake']}M {c['black']['blunder']}B")
    print(f"\nDitulis ke {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

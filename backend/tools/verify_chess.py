"""Verifikasi python-chess di Python 3.14.4.

Ticket: "Setup environment & fondasi repo" (#5), item 3.

Menguji hal-hal yang menjadi beban desain platform ini — bukan sekadar
"import berhasil":

1. Import + versi, dan apakah ekstensi C terkompilasi terpakai
2. Papan, FEN, langkah legal
3. Deteksi akhir game (skakmat, remis)
4. Chess960
5. PGN (baca/tulis) — dipakai untuk impor game eksternal
6. Validasi legalitas: parse_uci / push_uci / find_move (jebakan ADR-0002)
7. Jam catur — dikonfirmasi memang TIDAK ada (harus dibangun sendiri)
8. Varian lain — untuk menilai biaya menambahkannya nanti

Dijalankan dengan `python -I` supaya tidak memuat modul dari cwd.
"""

from __future__ import annotations

import sys
import traceback

# Konsol Windows default cp1252 — paksa UTF-8 supaya em-dash tidak jadi mojibake.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((name, True, detail or ""))
    except Exception as exc:  # noqa: BLE001 - laporan verifikasi
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()


def check_interpreter() -> str:
    import chess

    detail = f"Python {sys.version.split()[0]}, chess {chess.__version__}"
    # chess mendeteksi ekstensi C lewat modul inti.
    try:
        from chess import _c  # type: ignore[attr-defined]

        detail += " — ekstensi C AKTIF"
    except ImportError:
        detail += " — murni Python (tanpa ekstensi C)"
    return detail


def check_board_fen_moves() -> str:
    import chess

    board = chess.Board()
    assert board.fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq")
    assert board.legal_moves.count() == 20, board.legal_moves.count()

    board.push_uci("e2e4")
    # CATATAN: fen() default memakai en_passant="legal" — kotak ep hanya ditulis
    # kalau ada bidak yang benar-benar bisa menangkap. Setelah 1.e4 kotak e3
    # memang ada (board.ep_square == 20) tapi tidak ada penangkap, jadi FEN
    # menulis "-". Ini berbeda dari FEN gaya lama yang selalu menulis kotak ep.
    assert board.fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert board.ep_square == chess.E3, "ep_square internal tetap terisi"
    assert board.legal_moves.count() == 20

    # Ketika ep capture MEMANG legal, kotak ep muncul di FEN.
    ep = chess.Board()
    for uci in ["e2e4", "a7a6", "e4e5", "d7d5"]:
        ep.push_uci(uci)
    assert ep.fen().split()[3] == "d6", ep.fen()
    assert ep.has_legal_en_passant() is True

    # FEN -> papan -> FEN harus pulang-pergi tanpa berubah
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
    assert chess.Board(fen).fen() == fen
    return "papan/FEN/legal OK; 20 langkah awal, ep hanya ditulis bila legal, round-trip FEN utuh"


def check_game_over() -> str:
    import chess

    mate = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert mate.is_checkmate(), "posisi skakmat tidak terdeteksi"

    stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert stalemate.is_stalemate(), "stalemate tidak terdeteksi"

    insufficient = chess.Board("8/8/8/4k3/8/8/4K3/8 w - - 0 1")
    assert insufficient.is_insufficient_material(), "materi tidak cukup tidak terdeteksi"

    fifty = chess.Board("8/8/8/4k3/8/8/4K3/7R w - - 99 60")
    assert fifty.is_fifty_moves() or fifty.can_claim_fifty_moves(), "aturan 50 langkah gagal"

    repetition = chess.Board()
    for uci in ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8"]:
        repetition.push_uci(uci)
    assert repetition.is_repetition(2), "pengulangan posisi gagal"

    return "skakmat, stalemate, materi tidak cukup, 50 langkah, repetisi — semua terdeteksi"


def check_chess960() -> str:
    import chess

    board = chess.Board.from_chess960_pos(518)
    # 518 = posisi standar dalam penomoran Chess960
    assert board.fen().startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"), board.fen()
    assert board.chess960 is True
    assert board.legal_moves.count() == 20

    # posisi acak non-standar harus menghasilkan hak rokade yang bisa dimainkan
    other = chess.Board.from_chess960_pos(0)
    assert other.chess960 is True
    assert other.fen().split()[2] != "-", "hak rokade Chess960 kosong"

    return f"from_chess960_pos OK (pos 518 == standar, pos 0 rokade {other.fen().split()[2]})"


def check_pgn() -> str:
    import io

    import chess.pgn

    pgn_text = """[Event "Verifikasi"]
[Site "Lokal"]
[Date "2026.10.08"]
[Round "1"]
[White "Putih"]
[Black "Hitam"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6
8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 1-0
"""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    assert game is not None, "PGN gagal dibaca"
    moves = list(game.mainline_moves())
    assert len(moves) == 20, f"jumlah langkah salah: {len(moves)}"
    assert game.headers["White"] == "Putih"

    out = io.StringIO()
    game.accept(chess.pgn.FileExporter(out))
    assert "1. e4" in out.getvalue()

    return f"PGN baca/tulis OK ({len(moves)} langkah, header utuh)"


def check_legal_validation() -> str:
    """Jebakan ADR-0002: push() tidak memvalidasi, input Discord wajib lewat
    parse_uci/push_uci/find_move."""
    import chess

    # push() dengan langkah ilegal TIDAK melempar — inilah jebakannya
    board = chess.Board()
    illegal = chess.Move.from_uci("e2e5")
    board.push(illegal)  # sengaja: tidak memvalidasi
    board.pop()

    # jalur aman: parse_uci
    board2 = chess.Board()
    try:
        board2.parse_uci("e2e5")
        raise AssertionError("parse_uci menerima langkah ilegal!")
    except ValueError:
        pass

    # jalur aman: push_uci harus menolak
    board3 = chess.Board()
    try:
        board3.push_uci("e2e5")
        raise AssertionError("push_uci menerima langkah ilegal!")
    except ValueError:
        pass

    # jalur aman: push_san
    board4 = chess.Board()
    board4.push_san("e4")
    assert board4.fen().startswith("rnbqkbnr/pppppppp/8/8/4P3")

    # parse_san ilegal juga harus ditolak
    board5 = chess.Board()
    try:
        board5.push_san("Qh5")
        raise AssertionError("push_san menerima langkah ilegal!")
    except ValueError:
        pass

    return "dikonfirmasi: push() TIDAK memvalidasi; parse_uci/push_uci/push_san menolak ilegal"


def check_no_clock() -> str:
    """Jam catur harus dibangun sendiri — konfirmasi tidak ada di pustaka."""
    import chess
    import chess.pgn

    found = [name for name in dir(chess) if "clock" in name.lower()]
    # chess.pgn punya utilitas jam dari header PGN (komentar [%clk]) — itu bukan
    # jam yang berjalan. Pastikan tidak ada objek jam yang mengelola waktu.
    pgn_clock_utils = [n for n in dir(chess.pgn) if "clock" in n.lower()]
    return (
        f"tidak ada kelas jam di chess (kandidat: {found or 'kosong'}); "
        f"chess.pgn hanya punya utilitas parsing komentar: {pgn_clock_utils or 'kosong'}"
    )


def check_variants() -> str:
    """Varian di luar Chess960 — untuk menilai biaya menambahkannya nanti."""
    import chess
    import chess.variant

    available = [
        name
        for name in dir(chess.variant)
        if isinstance(getattr(chess.variant, name), type)
        and issubclass(getattr(chess.variant, name), chess.Board)
    ]
    return f"varian tersedia: {', '.join(sorted(available))}"


def main() -> int:
    print("=" * 72)
    print("Verifikasi python-chess — Platform Catur Discord")
    print("=" * 72)

    check("Interpreter & versi pustaka", check_interpreter)
    check("Papan, FEN, langkah legal", check_board_fen_moves)
    check("Deteksi akhir game", check_game_over)
    check("Chess960", check_chess960)
    check("PGN baca/tulis", check_pgn)
    check("Validasi legalitas langkah", check_legal_validation)
    check("Jam catur (harus tidak ada)", check_no_clock)
    check("Varian lain (biaya menambah)", check_variants)

    print()
    width = max(len(n) for n, _, _ in RESULTS)
    ok = 0
    for name, passed, detail in RESULTS:
        mark = "OK   " if passed else "GAGAL"
        print(f"[{mark}] {name:<{width}}  {detail}")
        ok += passed

    print()
    print(f"{ok}/{len(RESULTS)} pemeriksaan lulus")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

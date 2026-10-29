"""Buktikan render papan menghasilkan PNG yang benar — dari PIKsel, bukan mata.

ADR-0017 mewajibkan pemeriksaan ini, dan alasan kewajibannya konkret: sesi #7
menemukan sepuluh bug yang "terlihat wajar saat dilihat". Papan catur punya mode
kegagalan yang sama — FEN terbalik, warna kotak tertukar, sorotan di petak salah
semuanya menghasilkan gambar yang tampak bagus di thumbnail 64 px.

Yang diperiksa:

1. Ukuran PNG persis 320x320 (batas `size=` chess.svg)
2. Orientasi putih-di-bawah: a1 gelap, h1 terang, a8 terang, h8 gelap
3. Papan kosong hanya punya dua warna kotak
4. Bidak muncul di petak yang FEN sebut, dan petak lain tetap polos
5. Warna bidak sesuai kasus FEN (putih vs hitam)
6. Sorotan langkah terakhir menyentuh petak asal & tujuan saja
7. Palet mockup #7 bisa dipasang lewat `colors=`
8. Campuran warna sorotan mockup (emas 38%) bisa dinyatakan sebagai hex solid

Pakai, dari akar repo:

    backend/.venv/Scripts/python.exe -I backend/tools/verify_board_render.py

Butuh `chess` dan `resvg-py` (keduanya dependensi langsung backend sejak
ADR-0017).
"""

from __future__ import annotations

import struct
import sys
import zlib

import chess
import chess.svg
import resvg_py

SIZE = 320
SQ = SIZE // 8  # 40 px per kotak
EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"

# Palet mockup #7 (dipakai ulang ADR-0017). Nilai dari
# activity/mockup-analisa/index.html --sq-l / --sq-d / --sq-hi.
MOCK_LIGHT = "#b9c2cf"
MOCK_DARK = "#5b6472"
MOCK_HIGHLIGHT = "#d4af37"
MOCK_HIGHLIGHT_ALPHA = 0.38


# ── pembacaan PNG tanpa Pillow ─────────────────────────────────────────────
def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "keluaran bukan PNG"
    return struct.unpack(">II", data[16:24])


def _png_rgba(data: bytes) -> tuple[int, int, bytes]:
    """Dekode PNG RGBA 8-bit.

    Kelima filter PNG harus didukung. resvg memakai campuran Sub/Up/Average/
    Paeth, dan filter yang tidak ditangani membuat pemeriksaan piksel
    diam-diam salah — bukan gagal, tapi melaporkan angka yang keliru.
    """
    w, h = _png_size(data)
    pos, idat, color_type = 8, b"", None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            color_type = payload[9]
        elif ctype == b"IDAT":
            idat += payload
        pos += 12 + length
    assert color_type == 6, f"bukan RGBA (color_type={color_type})"
    raw = zlib.decompress(idat)

    bpp, stride = 4, w * 4
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1 : p + 1 + stride])
        p += 1 + stride
        if f == 1:  # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif f == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:  # Average
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:  # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif f != 0:
            raise AssertionError(f"filter PNG {f} tidak dikenal")
        out += line
        prev = line
    return w, h, bytes(out)


# ── render & geometri ──────────────────────────────────────────────────────
def render(fen: str, last_move: str | None = None, colors: dict | None = None):
    board = chess.Board(fen)
    mv = chess.Move.from_uci(last_move) if last_move else None
    svg = chess.svg.board(
        board, size=SIZE, lastmove=mv, coordinates=False, colors=colors or {}
    )
    return _png_rgba(bytes(resvg_py.svg_to_bytes(svg_string=svg)))


def square_xy(file: str, rank: int, inset: int = 6) -> tuple[int, int]:
    """Piksel SUDUT DALAM kotak.

    Sengaja bukan titik tengah: bidak selalu digambar di tengah, jadi sampel
    tengah mengukur bidaknya, bukan warna kotaknya. Ini persis kesalahan yang
    membuat pemeriksaan pertama sesi ini lulus-palsu di posisi awal.
    """
    return "abcdefgh".index(file) * SQ + inset, (8 - rank) * SQ + inset


def px(rgba: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * SIZE + x) * 4
    return tuple(rgba[i : i + 3])


def square_signature(rgba: bytes, file: str, rank: int) -> bytes:
    """Isi kotak sebagai byte — untuk mendeteksi ada/tidaknya bidak, tanpa
    peduli bentuk glyph-nya."""
    x0, y0 = "abcdefgh".index(file) * SQ, (8 - rank) * SQ
    return b"".join(
        rgba[(y * SIZE + x0) * 4 : (y * SIZE + x0) * 4 + SQ * 4]
        for y in range(y0, y0 + SQ)
    )


def count_extremes(rgba: bytes, file: str, rank: int) -> tuple[int, int]:
    """(piksel sangat gelap, sangat terang) dalam satu kotak.

    `chess.svg` menggambar bidak sebagai glyph = isi + garis tepi. Bidak putih
    = isi terang + tepi gelap, bidak hitam sebaliknya, jadi RASIO keduanya yang
    membedakan — bukan luminansi rata-rata, dan bukan ambang mutlak: palet
    bawaan `chess.svg` punya kotak "gelap" berwarna coklat terang (209,139,71),
    bukan hitam, sehingga ambang 128 salah.
    """
    x0, y0 = "abcdefgh".index(file) * SQ, (8 - rank) * SQ
    dark = light = 0
    for y in range(y0, y0 + SQ):
        for x in range(x0, x0 + SQ):
            i = (y * SIZE + x) * 4
            v = (rgba[i] * 299 + rgba[i + 1] * 587 + rgba[i + 2] * 114) // 1000
            dark += v < 60
            light += v > 235
    return dark, light


def lum(c: tuple[int, int, int]) -> int:
    return (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000


def blend(fg: str, bg: str, alpha: float) -> tuple[int, int, int]:
    """Warna solid hasil campuran `fg` di atas `bg` pada `alpha`."""
    f = tuple(int(fg[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(bg[i : i + 2], 16) for i in (1, 3, 5))
    return tuple(round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"  {'OK   ' if cond else 'GAGAL'}  {name}{'  ' + detail if detail else ''}")
        if not cond:
            fails.append(name)

    print("1. Ukuran PNG = 320x320 persis")
    w, h, empty = render(EMPTY_FEN)
    check("lebar 320", w == SIZE, str(w))
    check("tinggi 320", h == SIZE, str(h))
    _, _, start = render(chess.STARTING_FEN)

    print("\n2. Orientasi putih-di-bawah (papan kosong, sudut dalam)")
    a1, h1 = px(empty, *square_xy("a", 1)), px(empty, *square_xy("h", 1))
    a8, h8 = px(empty, *square_xy("a", 8)), px(empty, *square_xy("h", 8))
    check("a1 lebih gelap dari h1", lum(a1) < lum(h1), f"a1={a1} h1={h1}")
    check("a8 lebih terang dari h8", lum(a8) > lum(h8), f"a8={a8} h8={h8}")
    check("a1 == h8 (dua kotak gelap)", a1 == h8, f"{a1} vs {h8}")
    check("h1 == a8 (dua kotak terang)", h1 == a8, f"{h1} vs {a8}")

    print("\n3. Papan kosong: tepat dua warna kotak")
    corners = {px(empty, *square_xy(f, r)) for f in "abcdefgh" for r in range(1, 9)}
    check("tepat 2 warna", len(corners) == 2, str(sorted(corners)))

    print("\n4. Bidak muncul di petak yang FEN sebut")
    kings = "8/8/4K3/8/8/8/1k6/8 w - - 0 1"  # putih e6, hitam b2
    _, _, two_kings = render(kings)
    for f, r, occupied in (
        ("e", 6, True), ("b", 2, True),
        ("a", 1, False), ("h", 8, False), ("d", 4, False),
    ):
        same = square_signature(two_kings, f, r) == square_signature(empty, f, r)
        check(f"{f}{r} {'berisi bidak' if occupied else 'tetap kosong'}",
              (not same) if occupied else same)

    print("\n5. Warna bidak sesuai kasus FEN")
    for label, f, r, light_dominant in (
        ("raja putih e6 didominasi terang", "e", 6, True),
        ("raja hitam b2 didominasi gelap", "b", 2, False),
    ):
        dark, light = count_extremes(two_kings, f, r)
        check(label, (light > dark) == light_dominant, f"terang={light} gelap={dark}")

    print("\n6. Sorotan langkah terakhir menyentuh asal & tujuan saja")
    _, _, no_hi = render(chess.STARTING_FEN)
    _, _, with_hi = render(chess.STARTING_FEN, last_move="e2e4")
    for f, r, highlighted in (
        ("e", 2, True), ("e", 4, True),
        ("a", 3, False), ("d", 2, False),
    ):
        same = square_signature(with_hi, f, r) == square_signature(no_hi, f, r)
        check(f"{f}{r} {'tersorot' if highlighted else 'tidak tersentuh'}",
              (not same) if highlighted else same)

    print("\n7. Palet mockup #7 bisa dipasang lewat colors=")
    _, _, mock = render(EMPTY_FEN, colors={
        "square light": MOCK_LIGHT, "square dark": MOCK_DARK,
    })
    got = {px(mock, *square_xy(f, r)) for f in "abcdefgh" for r in range(1, 9)}
    check(f"terang {MOCK_LIGHT} hadir",
          tuple(int(MOCK_LIGHT[i : i + 2], 16) for i in (1, 3, 5)) in got)
    check(f"gelap {MOCK_DARK} hadir",
          tuple(int(MOCK_DARK[i : i + 2], 16) for i in (1, 3, 5)) in got)

    print("\n8. Campuran sorotan mockup (emas 38%) sebagai hex solid")
    # chess.svg mewarnai petak sorotan dengan `fill=` SOLID, sementara mockup #7
    # memakai emas ber-alpha di atas warna kotak. Dua campuran itu harus
    # dihitung di muka, bukan diserahkan ke rasterizer.
    for name, base in (("terang", MOCK_LIGHT), ("gelap", MOCK_DARK)):
        expected = blend(MOCK_HIGHLIGHT, base, MOCK_HIGHLIGHT_ALPHA)
        hexcol = "#{:02x}{:02x}{:02x}".format(*expected)
        _, _, hi = render(EMPTY_FEN, last_move="e2e4", colors={
            "square light": MOCK_LIGHT, "square dark": MOCK_DARK,
            "square light lastmove": hexcol,
            "square dark lastmove": hexcol,
        })
        # e2 gelap? e2 = file e (index 4) + rank 2 -> (4+2) genap -> terang.
        got_e2 = px(hi, *square_xy("e", 2))
        check(f"sorotan di kotak {name} = {hexcol}", got_e2 == expected,
              f"dapat {got_e2}, harap {expected}")

    print()
    if fails:
        print(f"GAGAL: {len(fails)} -> {', '.join(fails)}")
        return 1
    print("LULUS: semua pemeriksaan piksel lolos")
    return 0


if __name__ == "__main__":
    sys.exit(main())

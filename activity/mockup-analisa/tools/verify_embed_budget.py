"""Uji apakah rancangan embed ticket #7 benar-benar muat di batas Discord.

Batas resmi (discord-api-docs, developers/resources/message.mdx):
    - 6000 karakter gabungan (title + description + field.name + field.value
      + footer.text + author.name) untuk SEMUA embed dalam satu pesan
    - 25 field per embed
    - 10 embed per pesan
    - title 256, description 4096, field.name 256, field.value 1024,
      footer.text 2048, author.name 256

Body ticket #7 menyebut batas "2000 karakter". Itu keliru -- 2000 adalah batas
`content` pesan, bukan embed. Skrip ini memakai angka yang benar dan mengukur
rancangan terhadapnya.

Tujuannya bukan menguji kode produksi (belum ada), melainkan membuktikan klaim
tata letak: bahwa daftar langkah penuh **tidak muat** untuk game panjang, dan
bahwa "hanya kesalahan" **muat**. Itulah dasar keputusan di ticket #7.

Pakai: python -I verify_embed_budget.py <data.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Batas resmi Discord
LIMIT_TOTAL = 6000
LIMIT_FIELDS = 25
LIMIT_TITLE = 256
LIMIT_DESC = 4096
LIMIT_FIELD_NAME = 256
LIMIT_FIELD_VALUE = 1024

MARK = {"inaccuracy": "?!", "mistake": "?", "blunder": "??"}
MINUS = "−"  # U+2212, sama dengan yang dipakai mockup


def fmt_eval(kind, value):
    if kind == "mate":
        return f"#{value}" if value > 0 else f"#{MINUS}{abs(value)}"
    p = value / 100
    s = f"{abs(p):.2f}".replace(".", ",")
    return f"{'+' if p > 0 else MINUS if p < 0 else ''}{s}"


def fmt_acc(v):
    return f"{v:.1f}".replace(".", ",") + "%"


def full_move_list(game):
    """Daftar langkah LENGKAP, gaya notasi catur."""
    out = []
    moves = game["moves"]
    for i in range(0, len(moves), 2):
        w = moves[i]
        b = moves[i + 1] if i + 1 < len(moves) else None
        def r(m):
            if not m:
                return ""
            return m["san"] + (MARK[m["classification"]] if m["classification"] else "")
        out.append(f"{w['move_no']}.{r(w)}{' ' + r(b) if b else ''}")
    return " ".join(out)


def notable_list(game, kinds=("blunder", "mistake")):
    out = []
    moves = game["moves"]
    for i in range(0, len(moves), 2):
        w = moves[i]
        b = moves[i + 1] if i + 1 < len(moves) else None
        def r(m):
            if not m or m["classification"] not in kinds:
                return None
            return m
        rw, rb = r(w), r(b)
        if not rw and not rb:
            continue
        s = f"{w['move_no']}."
        if rw:
            s += rw["san"] + MARK[rw["classification"]]
        if rb:
            s += " " + rb["san"] + MARK[rb["classification"]]
        out.append(s)
    return " ".join(out)


def blunder_lines(game):
    bl = [m for m in game["moves"] if m["classification"] == "blunder"]
    # Tampilkan SAN (ADR-0009: disimpan UCI, ditampilkan SAN), UCI sebagai cadangan.
    return "\n".join(
        f"{m['move_no']}{'.' if m['color'] == 'white' else '…'} {m['san']} → {m.get('best_san') or m['best_uci'] or '—'}"
        for m in bl) or "—"


def measure(parts):
    """parts: list of (kind, label, text). kind menentukan batas per-field."""
    total = 0
    problems = []
    for kind, label, text in parts:
        total += len(text)
        lim = {"title": LIMIT_TITLE, "description": LIMIT_DESC,
               "field.name": LIMIT_FIELD_NAME, "field.value": LIMIT_FIELD_VALUE,
               "footer": LIMIT_DESC, "author": LIMIT_TITLE}.get(kind)
        if lim and len(text) > lim:
            problems.append(f"{label}: {len(text)} > batas {kind} {lim}")
    if total > LIMIT_TOTAL:
        problems.append(f"TOTAL {total} > {LIMIT_TOTAL}")
    nfields = sum(1 for k, _, _ in parts if k == "field.name")
    if nfields > LIMIT_FIELDS:
        problems.append(f"{nfields} field > {LIMIT_FIELDS}")
    return total, nfields, problems


RESULTS = []


def check(label, ok, detail):
    RESULTS.append((label, ok))
    print(f"  [{'OK   ' if ok else 'GAGAL'}] {label}")
    print(f"          {detail}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    games = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    print("=" * 74)
    print("BATAS DISCORD YANG DIPAKAI (dari discord-api-docs)")
    print("=" * 74)
    print(f"  6000 karakter gabungan per pesan · 25 field/embed · 10 embed/pesan")
    print(f"  title {LIMIT_TITLE} · description {LIMIT_DESC} · field.name {LIMIT_FIELD_NAME} "
          f"· field.value {LIMIT_FIELD_VALUE}")
    print(f"  (body ticket #7 menyebut 2000 -- itu batas `content`, bukan embed)")

    for g in games:
        print()
        print("=" * 74)
        print(f"GAME: {g['label']}")
        print(f"  {g['plies']} ply · akurasi putih {fmt_acc(g['accuracy']['white'])} "
              f"hitam {fmt_acc(g['accuracy']['black'])}")
        print("=" * 74)

        full = full_move_list(g)
        notable = notable_list(g)
        bl = blunder_lines(g)
        acc_line = (f"Putih {g['white']} — {fmt_acc(g['accuracy']['white'])}\n"
                    f"Hitam {g['black']} — {fmt_acc(g['accuracy']['black'])}")

        print("\n  Ukuran bahan mentah:")
        print(f"    daftar langkah LENGKAP   : {len(full):>6} karakter")
        print(f"    daftar blunder+kesalahan : {len(notable):>6} karakter")
        print(f"    daftar blunder saja      : {len(bl):>6} karakter")
        print(f"    baris akurasi            : {len(acc_line):>6} karakter")

        # ── Varian A: akurasi + momen kritis ──────────────────────────────
        moments = notable_list(g, kinds=("blunder", "mistake", "inaccuracy"))
        a_parts = [
            ("title", "title", f"{g['white']} vs {g['black']}"),
            ("description", "description", acc_line),
            ("field.name", "field: Pembukaan", "Pembukaan"),
            ("field.value", "field: Pembukaan.v", "C33 — King's Gambit Diterima"),
            ("field.name", "field: Momen kritis", "Momen kritis"),
            ("field.value", "field: Momen kritis.v", moments),
            ("field.name", "field: Hasil", "Hasil"),
            ("field.value", "field: Hasil.v", "Putih menang"),
            ("footer", "footer", "Stockfish 19 · 1.000.000 node/posisi · 4 thread"),
        ]
        total_a, nf_a, prob_a = measure(a_parts)
        print(f"\n  Varian A (akurasi + momen kritis):")
        print(f"    total {total_a} / {LIMIT_TOTAL} ({total_a / LIMIT_TOTAL * 100:.1f}%) · "
              f"{nf_a} field")
        check(f"A muat untuk game {g['plies']} ply", not prob_a,
              "; ".join(prob_a) if prob_a else f"sisa {LIMIT_TOTAL - total_a} karakter")

        # ── Varian C: hanya blunder + urutan bermasalah ───────────────────
        c_parts = [
            ("title", "title", f"{g['white']} vs {g['black']}"),
            ("description", "description", acc_line),
            ("field.name", "field: Blunder", "Blunder"),
            ("field.value", "field: Blunder.v", bl),
            ("field.name", "field: Urutan", "Urutan langkah"),
            ("field.value", "field: Urutan.v", notable),
            ("footer", "footer", "Hanya kesalahan yang ditampilkan · Stockfish 19"),
        ]
        total_c, nf_c, prob_c = measure(c_parts)
        print(f"\n  Varian C (blunder + urutan bermasalah):")
        print(f"    total {total_c} / {LIMIT_TOTAL} ({total_c / LIMIT_TOTAL * 100:.1f}%) · "
              f"{nf_c} field")
        check(f"C muat untuk game {g['plies']} ply", not prob_c,
              "; ".join(prob_c) if prob_c else f"sisa {LIMIT_TOTAL - total_c} karakter")

        # ── Pembanding: daftar LENGKAP di dalam embed ─────────────────────
        d_parts = [
            ("title", "title", f"{g['white']} vs {g['black']}"),
            ("description", "description", acc_line),
            ("field.name", "field: Urutan langkah", "Urutan langkah"),
            ("field.value", "field: Urutan langkah.v", full),
        ]
        total_d, nf_d, prob_d = measure(d_parts)
        print(f"\n  Pembanding (daftar langkah LENGKAP di dalam embed):")
        print(f"    total {total_d} / {LIMIT_TOTAL} ({total_d / LIMIT_TOTAL * 100:.1f}%)")
        fits = not prob_d
        print(f"    -> {'MUAT' if fits else 'TIDAK MUAT'}")
        if prob_d:
            for p in prob_d:
                print(f"       {p}")

        # ── PEMENANG: struktur B + daftar langkah penuh + semua blunder ────
        # Pilihan pemilik proyek menggabungkan dua hal yang belum pernah ada
        # bersama: struktur varian B (papan + hitungan) DAN daftar langkah
        # penuh DAN seluruh blunder. Gabungan inilah yang harus diukur --
        # masing-masing bagian muat sendirian, tapi pertanyaannya apakah
        # gabungannya muat.
        bl_all = "\n".join(
            f"{m['move_no']}{'.' if m['color'] == 'white' else '…'} {m['san']} → "
            f"{m.get('best_san') or m['best_uci'] or '—'}"
            for m in g["moves"] if m["classification"] == "blunder") or "—"
        # Deskripsi yang SAMA PERSIS dengan yang dipakai mockup varian B,
        # TERMASUK penanda markdown **tebal**. Discord menghitung karakter
        # penanda itu sebagai bagian dari field.value -- jadi mengabaikannya
        # membuat verifikator melaporkan angka lebih kecil daripada mockup
        # (1.693 vs 1.705) dan kedua jalur tidak bisa dibandingkan.
        desc_b = (f"**Putih** {g['white']} — {fmt_acc(g['accuracy']['white'])}\n"
                  f"**Hitam** {g['black']} — {fmt_acc(g['accuracy']['black'])}\n\n"
                  f"Akurasi dihitung dari seluruh {g['plies']} langkah. "
                  f"Klik **Buka Papan** untuk melihat eval bar dan menelusuri tiap langkah.")

        w_parts = [
            ("title", "title", f"{g['white']} vs {g['black']}"),
            ("description", "description", desc_b),
            ("field.name", "field: Putih", "Putih"),
            ("field.value", "field: Putih.v",
             f"{g['counts']['white']['inaccuracy']} ?!  "
             f"{g['counts']['white']['mistake']} ?  "
             f"{g['counts']['white']['blunder']} ??"),
            ("field.name", "field: Hitam", "Hitam"),
            ("field.value", "field: Hitam.v",
             f"{g['counts']['black']['inaccuracy']} ?!  "
             f"{g['counts']['black']['mistake']} ?  "
             f"{g['counts']['black']['blunder']} ??"),
            ("field.name", "field: Blunder", "Blunder"),
            ("field.value", "field: Blunder.v", bl_all),
            ("field.name", "field: Urutan", "Urutan langkah"),
            ("field.value", "field: Urutan.v", full),
            ("footer", "footer", "Stockfish 19 · 1.000.000 node/posisi"),
        ]
        total_w, nf_w, prob_w = measure(w_parts)
        n_bl = sum(1 for m in g["moves"] if m["classification"] == "blunder")
        print(f"\n  PEMENANG (struktur B + daftar penuh + {n_bl} blunder):")
        print(f"    total {total_w} / {LIMIT_TOTAL} ({total_w / LIMIT_TOTAL * 100:.1f}%) · "
              f"{nf_w} field")
        for kind, label, text in w_parts:
            lim = {"field.value": LIMIT_FIELD_VALUE, "description": LIMIT_DESC,
                   "title": LIMIT_TITLE, "field.name": LIMIT_FIELD_NAME}.get(kind)
            if lim and len(text) > 0.8 * lim:
                print(f"      ! {label}: {len(text)} / {lim} "
                      f"({len(text) / lim * 100:.0f}% dari batas)")
        check(f"Pemenang muat untuk game {g['plies']} ply", not prob_w,
              "; ".join(prob_w) if prob_w else f"sisa {LIMIT_TOTAL - total_w} karakter")

    # ── Di ply berapa daftar penuh benar-benar menabrak batas? ────────────
    # Ini pertanyaan yang sebenarnya menentukan: kalau daftar penuh muat
    # sampai jauh di atas panjang game normal, maka memangkasnya adalah
    # keputusan keterbacaan, BUKAN keputusan batas karakter.
    print()
    print("=" * 74)
    print("DI PLY BERAPA DAFTAR PENUH MENABRAK BATAS?")
    print("=" * 74)
    print("  Batas yang mengikat adalah field.value = 1024, bukan total 6000.")
    print("  Rata-rata panjang satu ply (dari game di atas):")
    per_ply = []
    for g in games:
        n = len(full_move_list(g))
        if g["plies"]:
            per_ply.append(n / g["plies"])
    avg = sum(per_ply) / len(per_ply) if per_ply else 0
    print(f"    {avg:.2f} karakter/ply (termasuk penanda klasifikasi)")
    for lim, name in ((LIMIT_FIELD_VALUE, "field.value"), (LIMIT_DESC, "description")):
        ply = int(lim / avg) if avg else 0
        print(f"    -> daftar penuh menabrak {name} ({lim}) sekitar "
              f"ply {ply} (~{(ply // 2) + 1} langkah penuh)")
    print()
    print("  Artinya: game normal (<= 150 ply) memuat daftar penuh tanpa")
    print("  pemangkasan. Memangkas daftar langkah adalah pilihan KETERBACAAN,")
    print("  bukan keharusan teknis.")
    print()
    # Uji batas: daftar sintetis pada berbagai panjang.
    print("  Uji batas dengan daftar sintetis (rata-rata karakter/ply di atas):")
    for ply in (100, 150, 200, 300):
        synth = " ".join(f"{(i // 2) + 1}.Nf3 Nc6" for i in range(0, ply, 2))
        ok = len(synth) <= LIMIT_FIELD_VALUE
        print(f"    {ply:>4} ply -> {len(synth):>6} karakter  "
              f"{'muat' if ok else 'MELEBIHI'} field.value {LIMIT_FIELD_VALUE}")

    print()
    print("=" * 74)
    print("RINGKASAN")
    print("=" * 74)
    gagal = [r for r in RESULTS if not r[1]]
    print(f"  {len(RESULTS) - len(gagal)}/{len(RESULTS)} uji lolos")
    if gagal:
        for label, _ in gagal:
            print(f"    GAGAL: {label}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

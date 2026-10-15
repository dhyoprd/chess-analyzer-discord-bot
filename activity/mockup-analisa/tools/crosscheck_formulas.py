"""Buktikan rumus di generate_data.py identik dengan rumus yang sudah terverifikasi.

`generate_data.py` memuat salinan rumus klasifikasi & akurasi supaya bisa
dijalankan berdiri sendiri. Salinan adalah tempat bug bersembunyi: kalau ia
menyimpang dari `backend/tools/verify_analysis_formulas.py` (yang lulus 10/10
nilai emas unit test Lichess), maka seluruh angka di mockup ticket #7 salah
walau terlihat wajar.

Skrip ini menjalankan KEDUA implementasi atas nilai emas yang sama dan
membandingkan hasilnya satu per satu.

Pakai: python -I crosscheck_formulas.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent          # .../activity/mockup-analisa/tools
REPO = HERE.parents[2]                          # .../ticket-07-mockup


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Nilai emas dari AccuracyPercentTest.scala (Lichess), sama dengan yang dipakai
# verify_analysis_formulas.py.
GOLD = [
    ("compute(Nil) -> None", [], None),
    ("compute([15]) -> None (1 ply)", [15], None),
    ("compute([15,15]) putih ~100", [15, 15], (100, 1)),
    ("fill(20)(15)+[-900] putih ~50", [15] * 20 + [-900], (50, 5)),
    ("fill(50)([-135,15]) ~54", [v for _ in range(50) for v in (-135, 15)], (54, 8)),
    ("fill(50)([-435,15]) ~20", [v for _ in range(50) for v in (-435, 15)], (20, 8)),
]


def main():
    # Modul referensi: backend/tools/verify_analysis_formulas.py
    ref_path = REPO / "backend" / "tools" / "verify_analysis_formulas.py"
    if not ref_path.exists():
        print(f"TIDAK DITEMUKAN: {ref_path}")
        return 1

    print("Memuat kedua implementasi...")
    ref = load(ref_path, "ref_formulas")
    gen = load(HERE / "generate_data.py", "gen_data")
    print(f"  referensi : {ref_path.relative_to(REPO)}")
    print(f"  diuji     : tools/generate_data.py")
    print()

    print("=" * 72)
    print("PERBANDINGAN ATAS NILAI EMAS LICHESS")
    print("=" * 72)
    gagal = 0
    for label, cps, expect in GOLD:
        a = ref.compute(cps)
        b = gen.game_accuracy([gen.wc_100(15)] + [gen.wc_100(c) for c in cps])
        if expect is None:
            ok = a is None and b is None
            detail = f"ref={a} gen={b}"
        else:
            want, tol = expect
            ok = (a is not None and b is not None
                  and abs(a[True] - want) <= tol and abs(b[True] - want) <= tol
                  and abs(a[True] - b[True]) < 0.01)
            detail = (f"ref putih={a[True]:.2f} gen putih={b[True]:.2f} "
                      f"(harap {want}+-{tol})")
        gagal += not ok
        print(f"  [{'OK   ' if ok else 'GAGAL'}] {label}")
        print(f"          {detail}")

    print()
    print("=" * 72)
    print("PERBANDINGAN KLASIFIKASI (termasuk perangkap POV)")
    print("=" * 72)
    # Label harapan dihitung dari ambang ADR-0009 (0,1/0,2/0,3), bukan ditebak.
    # Versi pertama daftar ini salah menulis tiga harapan (mis. 0cp -> -150cp
    # berdelta 0,2693, yang MEMANG mistake karena >= 0,2). Yang penting di sini
    # adalah kedua implementasi sepakat; labelnya harus diturunkan dari ambang.
    KASUS = [
        ((0, -350), True, "blunder"),      # delta 0,5679 >= 0,3
        ((0, -350), False, None),          # dibalik: pelangkah hitam tidak rugi
        ((0, -150), True, "mistake"),      # delta 0,2693 >= 0,2
        ((0, -60), True, "inaccuracy"),    # delta 0,1100 >= 0,1
        ((800, 400), True, "mistake"),     # delta 0,2731 >= 0,2
        ((-54, 200), False, "blunder"),    # delta 0,4515 >= 0,3
    ]
    for (prev, curr), is_white, want in KASUS:
        _, d_ref = ref.classify(prev, curr, is_white)
        got, d_gen = gen.classify(("cp", prev), ("cp", curr), is_white)
        # Dua syarat: label sesuai ambang, DAN kedua implementasi sepakat.
        #
        # Delta dibandingkan dengan TOLERANSI, bukan == . Keduanya menghitung
        # win-chance lewat jalur yang berbeda secara aljabar tapi setara:
        # referensi lewat (50 + 50x)/50 - 1, generator langsung x. Untuk nilai
        # tertentu keduanya berbeda di bit terakhir, dan == gagal walaupun
        # hasilnya sama sampai 4 desimal.
        ok = got == want and abs(d_ref - d_gen) < 1e-9
        gagal += not ok
        who = "putih" if is_white else "hitam"
        print(f"  [{'OK   ' if ok else 'GAGAL'}] {who:5s} {prev:>5}cp -> {curr:>5}cp "
              f"= {str(got):>10} (harap {str(want):>10})  delta ref={d_ref:+.4f} gen={d_gen:+.4f}")

    print()
    print("=" * 72)
    if gagal:
        print(f"  {gagal} KETIDAKCOCOKAN -- angka mockup TIDAK bisa dipercaya")
        return 1
    print("  SEMUA COCOK -- angka di mockup memakai rumus yang sama dengan ADR-0009")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

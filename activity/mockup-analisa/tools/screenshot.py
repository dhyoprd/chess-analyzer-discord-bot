"""Tangkap layar mockup ticket #7 dengan Chrome headless.

Menguji sekaligus: kalau ada error JavaScript, halaman tidak akan terender dan
tangkapan layarnya kosong -- jadi skrip ini juga berfungsi sebagai pemeriksaan
"mockup benar-benar jalan", bukan sekadar penghasil gambar.

Pakai: python -I screenshot.py <chrome.exe> <index.html> <keluar-dir>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (nama, query) -- semua kombinasi yang layak dilihat manusia.
# Tangkapan skenario memakai varian B karena itulah yang DIPILIH; A dan C
# tetap diambil untuk kedua permukaan supaya alternatif yang ditolak tetap
# terdokumentasi sebagai sumber primer.
SHOTS = [
    ("embed-A", "variant=A&surface=embed&scenario=normal"),
    ("embed-B", "variant=B&surface=embed&scenario=normal"),
    ("embed-C", "variant=C&surface=embed&scenario=normal"),
    ("activity-A", "variant=A&surface=activity&scenario=normal"),
    ("activity-B", "variant=B&surface=activity&scenario=normal"),
    ("activity-C", "variant=C&surface=activity&scenario=normal"),
    ("embed-panjang", "variant=B&surface=embed&scenario=long"),
    ("embed-komputer", "variant=B&surface=embed&scenario=engine"),
    ("embed-ditinggalkan", "variant=B&surface=embed&scenario=abandoned"),
    ("embed-impor", "variant=B&surface=embed&scenario=import"),
    ("embed-1ply", "variant=B&surface=embed&scenario=oneply"),
]


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    chrome = str(Path(sys.argv[1]).resolve())
    page = Path(sys.argv[2]).resolve()
    outdir = Path(sys.argv[3]).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    url_base = page.as_uri()

    # WAJIB: profil terpisah per pemanggilan. Tanpa ini Chrome meneruskan
    # perintah ke instans yang sudah berjalan, keluar dengan kode 0, dan
    # tidak menulis berkas apa pun -- gagal secara senyap. Sudah diuji.
    prof = (outdir.parent / ".chrome-profil").resolve()
    prof.mkdir(parents=True, exist_ok=True)

    # WAJIB: SEMUA path absolut. Chrome menggantung (bukan gagal) bila
    # --screenshot atau --user-data-dir diberi path relatif. Sudah diuji.
    ok = 0
    for name, query in SHOTS:
        out = (outdir / f"{name}.png").resolve()
        if out.exists():
            out.unlink()
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--user-data-dir={prof}",
            "--hide-scrollbars", "--force-device-scale-factor=1",
            "--window-size=1240,1500",
            f"--screenshot={out}",
            f"{url_base}?{query}",
        ]
        # PENTING: JANGAN pakai capture_output=True. Di Windows, Chrome
        # mewariskan pipe ke proses anak yang hidup lebih lama, sehingga
        # subprocess.run menunggu selamanya walau Chrome-nya sudah keluar
        # (sudah diuji: menggantung sampai timeout). Alihkan ke DEVNULL.
        try:
            r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=90)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = "TIMEOUT"
        size = out.stat().st_size if out.exists() else 0
        good = size > 12000
        ok += good
        print(f"  [{'OK   ' if good else 'KECIL'}] {name:22s} {size:>8,} byte", flush=True)
        if not good:
            print(f"          rc={rc}", flush=True)

    print(f"\n  {ok}/{len(SHOTS)} tangkapan layar berhasil", flush=True)
    return 0 if ok == len(SHOTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

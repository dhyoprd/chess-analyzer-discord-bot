"""Jalankan semua pemeriksaan mockup ticket #7 dalam satu perintah.

Pakai: python -I run_all.py <stockfish.exe>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # activity/mockup-analisa
REPO = HERE.parents[2]                  # .../ticket-07-mockup
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DATA = ROOT / "data" / "analisa-nyata.json"


def find_python():
    """Cari venv backend.

    Venv ada di CHECKOUT UTAMA, bukan di worktree -- `.venv` tidak ikut ke
    worktree baru. Jadi: coba worktree dulu, lalu checkout utama (dua tingkat
    di atas `.claude/worktrees/<nama>`), lalu Python yang sedang berjalan.
    """
    kandidat = [
        REPO / "backend" / ".venv" / "Scripts" / "python.exe",
        REPO.parents[2] / "backend" / ".venv" / "Scripts" / "python.exe",
    ]
    for p in kandidat:
        if p.exists():
            return p
    return Path(sys.executable)


def step(n, title, cmd, optional=False):
    print()
    print("=" * 74)
    print(f"  {n}. {title}")
    print("=" * 74)
    r = subprocess.run([str(c) for c in cmd])
    ok = r.returncode == 0
    if not ok and optional:
        print(f"  (dilewati -- langkah opsional, rc={r.returncode})")
        return True
    print(f"  -> {'LULUS' if ok else 'GAGAL'}")
    return ok


def main():
    sf = sys.argv[1] if len(sys.argv) > 1 else None
    PY = find_python()
    print(f"Menggunakan Python: {PY}")

    hasil = []
    if sf:
        hasil.append(step(1, "Hasilkan data analisa (Stockfish, 1 juta node)",
                          [PY, "-I", HERE / "generate_data.py", sf, DATA]))
    else:
        print("(tanpa argumen stockfish.exe -- langkah 1 dilewati)")

    hasil.append(step(2, "Rumus identik dengan ADR-0009",
                      [PY, "-I", HERE / "crosscheck_formulas.py"]))
    hasil.append(step(3, "Anggaran embed terhadap batas resmi Discord",
                      [PY, "-I", HERE / "verify_embed_budget.py", DATA]))
    hasil.append(step(4, "Data JSON -> JS untuk mockup",
                      [PY, "-I", HERE / "to_js.py", DATA, ROOT / "data" / "analisa-nyata.js"]))
    hasil.append(step(5, "Tangkapan layar (butuh Chrome)",
                      [PY, "-I", HERE / "screenshot.py", CHROME, ROOT / "index.html",
                       ROOT / "docs" / "tangkapan"], optional=True))

    print()
    print("=" * 74)
    lulus = sum(1 for h in hasil if h)
    print(f"  RINGKASAN: {lulus}/{len(hasil)} langkah lulus")
    print("=" * 74)
    return 0 if all(hasil) else 1


if __name__ == "__main__":
    raise SystemExit(main())

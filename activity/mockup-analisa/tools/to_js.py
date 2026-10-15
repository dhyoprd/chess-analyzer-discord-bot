"""Ubah data analisa JSON jadi berkas .js yang bisa dimuat <script> langsung.

Mockup sengaja satu berkas HTML yang bisa dibuka dengan klik ganda -- tanpa
server, tanpa build. Itu berarti datanya harus jadi variabel global, bukan
diambil lewat fetch() (fetch dari file:// diblokir CORS).

Pakai: python -I to_js.py <masuk.json> <keluar.js>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    src, dst = sys.argv[1], sys.argv[2]
    games = json.loads(Path(src).read_text(encoding="utf-8"))
    payload = json.dumps(games, ensure_ascii=False, separators=(",", ":"))

    header = (
        "/* PROTOTYPE (ticket #7) — data analisa NYATA, dihasilkan Stockfish 19.\n"
        "   Konfigurasi: 1.000.000 node/posisi, Threads=4, Hash=128 MB (ADR-0009).\n"
        "   Dibuat oleh tools/generate_data.py, diubah oleh tools/to_js.py.\n"
        "   JANGAN edit tangan — jalankan ulang generatornya. */\n"
    )
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(f"{header}window.ANALISA_DATA = {payload};\n", encoding="utf-8")

    total_moves = sum(g["plies"] for g in games)
    print(f"Ditulis {dst}: {len(games)} game, {total_moves} ply, "
          f"{Path(dst).stat().st_size:,} byte")
    for g in games:
        print(f"  - {g['label']}: {g['plies']} ply, akurasi "
              f"{g['accuracy']['white']}/{g['accuracy']['black']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

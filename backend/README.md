# Backend — Platform Catur Discord

Backend **otoritatif** (ADR-0002): sumber kebenaran posisi papan, riwayat langkah,
dan jam catur. Activity hanya mengirim *niat* langkah; backend yang memvalidasi.

Python 3.14 + FastAPI + `python-chess` + Stockfish.

## Menyiapkan lingkungan

```powershell
cd backend
uv sync --all-extras          # bikin .venv dari uv.lock
```

`uv` mengelola Python-nya sendiri; `uv.lock` memaku 45 paket. Python minimum
**3.14** (lihat ADR-0004 untuk alasan 3.14 dan bukan 3.13).

## Memverifikasi lingkungan

Dua skrip ini adalah gerbang kelayakan — jalankan setelah mengubah dependensi.

```powershell
.venv\Scripts\python.exe -I tools\verify_chess.py     # python-chess: papan, FEN, Chess960, PGN, legalitas
.venv\Scripts\python.exe -I tools\verify_backend.py   # ekosistem: pydantic, FastAPI, discord.py, aiosqlite, websockets, Stockfish
```

`-I` (isolated) wajib: mencegah Python memuat modul dari direktori kerja.

## Binary Stockfish

Stockfish **tidak** ada di PATH dan **tidak** di-commit (98 MB). Letaknya di
`../engine/stockfish.exe`, diunduh dari GitHub Releases:

```
https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip
```

Stockfish 19 hanya merilis binary **universal** — tidak ada lagi pilihan
`avx2`/`bmi2`. Ia mendeteksi fitur CPU sendiri. Jalur selalu absolut
(`engine/stockfish.exe`), jangan andalkan PATH.

## Tata letak

```
backend/
  src/chessbot/     paket aplikasi
  tests/            pytest
  tools/            skrip verifikasi lingkungan (bukan bagian runtime)
  pyproject.toml    dependensi langsung
  uv.lock           resolusi terkunci
```

## Catatan yang mudah terulang

- Distribusi PyPI bernama **`chess`**; `python-chess` hanyalah alias. Impor tetap `import chess`.
- `board.push()` **tidak** memvalidasi legalitas. Semua input dari Discord wajib
  lewat `parse_uci()`, `push_uci()`, `push_san()`, atau `find_move()`.
- `SimpleEngine` tidak punya `setoption()` — pakai `engine.configure({...})`.
- Jam catur **tidak ada** di `python-chess` dan harus dibangun seluruhnya.

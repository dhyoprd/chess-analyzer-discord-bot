# Python 3.14 untuk backend

## Konteks

`python-chess` mendeklarasikan dukungan sampai Python 3.13 di classifier-nya; 3.14 tidak disebut. Mesin pengembangan ini punya 3.14.4 dan 3.14.3 terpasang, sementara 3.12 tersedia lewat `uv`. Pilihan versi Python adalah keputusan yang menyentuh `uv.lock`, `Dockerfile`, dan setiap dependensi — sulit dibalik setelah kode menumpuk, dan mengejutkan bagi siapa pun yang membaca classifier `python-chess`.

Keraguan sebenarnya bukan pada `python-chess` — pustaka itu murni Python dan jelas akan jalan. Keraguan ada pada **ekosistem sekitarnya**: `pydantic-core` adalah ekstensi Rust, dan wheel-nya harus tersedia untuk 3.14; hal yang sama berlaku untuk `Pillow`, `httptools`, dan `watchfiles`.

## Keputusan

Backend memakai **Python 3.14** (`requires-python = ">=3.14"`). Tidak ada penurunan versi.

## Alasan

Keraguan itu **diuji langsung, bukan diasumsikan**. Seluruh tumpukan dipasang dan dipakai untuk pekerjaan nyata di 3.14.4:

| Paket | Versi | Yang benar-benar dijalankan |
|---|---|---|
| `chess` | 1.11.2 | Papan, FEN, langkah legal, skakmat, Chess960, PGN baca/tulis |
| `pydantic` / `pydantic-core` | 2.13.5 / 2.46.5 | Validasi yang menolak input buruk, serialisasi JSON |
| `fastapi` | 0.142.4 | App + request HTTP nyata lewat `TestClient` |
| `uvicorn` | 0.54.0 | Konstruksi `Server` dengan config valid |
| `discord-py` | 2.7.1 | `Client`, `Intents`, `Embed`; shim `audioop-lts` aktif |
| `aiosqlite` | 0.22.1 | Tabel, insert, select, `PRAGMA foreign_keys=ON` |
| `websockets` | 17.2 | Server + klien loopback, kirim/terima pesan |
| `Pillow` | 12.3.0 | Membuat gambar dan menggambar |
| Stockfish 19 | — | Langkah terbaik, eval, MultiPV=3, `UCI_Elo` 1320–3190 |

Semua lulus (`backend/tools/verify_backend.py`, 9/9). Satu-satunya kegagalan yang muncul adalah `httpx2` yang belum terpasang — dependensi khusus `TestClient`, bukan masalah 3.14.

Dua temuan yang menguatkan keputusan ini:

- **`python-chess` murni Python.** Tidak ada ekstensi C sama sekali, jadi ketiadaan wheel untuk 3.14 tidak relevan — tidak ada yang perlu dikompilasi kecuali dirinya sendiri, dan ia berhasil dibangun dari sdist.
- **`pydantic-core` punya wheel 3.14.** Ini risiko terbesar yang disebut di kabut peta, dan terbukti tidak nyata.

## Konsekuensi

- `python-chess` belum menguji 3.14. Bila ia merilis versi yang memecahkan 3.14, kita yang menemukannya lebih dulu. Mitigasi: `uv.lock` memaku versi, dan `verify_chess.py` adalah gerbang yang menangkap regresi.
- `python-chess` tidak punya wheel untuk 3.14 sehingga dipasang dari sdist. Tidak berbahaya karena murni Python, tapi berarti pemasangan butuh build backend. Pemasangan berikutnya sebaiknya dari `uv.lock`, bukan `uv pip install` langsung.
- Mesin ini punya 3.14.3 juga; pin ke **3.14.4** secara eksplisit agar lingkungan reproducible.
- Bila nanti pindah ke VPS, image dasarnya harus `python:3.14` — sudah tercermin di `backend/Dockerfile`.
- Kabut "Python 3.13 vs 3.14 untuk backend" **selesai** dan bisa dihapus dari peta.

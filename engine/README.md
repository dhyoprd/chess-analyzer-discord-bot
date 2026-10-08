# Engine — binary Stockfish

Stockfish **tidak di-commit** (98 MB). Unduh dan taruh di sini:

```powershell
curl -L -o stockfish.zip https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip
Expand-Archive stockfish.zip -DestinationPath .
Move-Item stockfish\stockfish-windows-x86-64-universal.exe stockfish.exe
Remove-Item -Recurse stockfish, stockfish.zip
```

## Isi direktori ini

| Berkas | Di-commit? | Keterangan |
|---|---|---|
| `stockfish.exe` | ❌ | Binary Stockfish 19 (~98 MB, NNUE tertanam). Diabaikan `.gitignore`. |
| `STOCKFISH-LICENSE.txt` | ✅ | GPL-3.0 — kewajiban distribusi, harus ikut repo. |
| `STOCKFISH-AUTHORS.txt` | ✅ | Kredit pengembang Stockfish. |

## Fakta yang sudah diverifikasi

- Stockfish 19 (`sf_19`, rilis 5 Sep 2026) hanya merilis binary **universal** —
  tidak ada lagi varian `avx2`/`bmi2`/`avx512`. Binary mendeteksi fitur CPU sendiri.
- Nama berkas di dalam arsip: `stockfish-windows-x86-64-universal.exe`.
- `UCI_Elo` berkisar **1320–3190**. Lantai 1320 berarti preset 800/1200 tidak
  bisa dicapai lewat opsi bawaan — lihat ticket "Konfigurasi mode lawan komputer".
- NNUE **tertanam** di dalam exe; tidak ada berkas `.nnue` terpisah untuk diunduh.
- Jangan andalkan PATH. Selalu lewatkan jalur absolut dari konfigurasi.

## Lisensi

Stockfish adalah **GPL-3.0**. Karena kita mendistribusikan binary-nya di repo
publik, kewajiban copyleft melekat. Ini kandidat ADR di peta (lihat kabut
"Peran lisensi GPL-3.0+"). `python-chess` juga GPL-3.0+.

# Dev lokal & deployment di Windows: proses native, tunnel bernama, tanpa Docker

## Konteks

Ticket [Dev lokal & deployment di Windows](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/13) harus menentukan bagaimana platform dijalankan sehari-hari dan bagaimana ia hidup kembali setelah komputer restart — susunan layanan, alur dev, tunnel, auto-start, rahasia, backup, dan jalur migrasi ke VPS. Sembilan belas pertanyaan, lima ronde.

Dua temuan riset membalik arah keputusan di tengah jalan:

- **Docker Desktop tidak bisa start tanpa sesi login.** Ia aplikasi per-pengguna. Lebih jauh, VM WSL2 **mematikan dirinya saat idle** (`vmIdleTimeout`, bawaannya 60 detik), dan Microsoft sendiri menyatakan WSL *"may make it challenging for production-related scenarios"*. Layanan 24/7 di dalam container punya dua mode kegagalan yang saling bebas di mesin ini.
- **Premis "Stockfish memaksa backend ke host" ternyata salah.** Binary Windows memang tidak bisa jalan di container Linux, tapi binary **Linux**-nya jalan baik: mendeteksi arsitektur yang sama (`x86-64-avxvnni`) dan **~1,4x lebih cepat** daripada binary Windows di mesin ini. Containerisasi **tidak** menambah ongkos.

Docker tetap dibuang — tapi atas dasar yang benar: bukan karena Stockfish, melainkan karena Docker Desktop tidak bisa headless dan WSL2 mematikan dirinya saat idle.

## Keputusan

**Tidak ada container. Semuanya proses native Windows.**

- **Satu proses Python** menjalankan bot Discord dan FastAPI sekaligus — keduanya asyncio, satu event loop. Analisa Stockfish tetap di thread sendiri (ADR-0009).
- **Backend menyajikan bundel Activity hasil build** sebagai berkas statis. Saat dev, tunnel menunjuk Vite (port 3000) yang mem-proxy `/api` ke backend; saat produksi, tunnel menunjuk backend langsung. Satu origin, tanpa CORS.
- **`docker-compose.yml` dan `backend/Dockerfile` dibuang** dari jalur aktif.
- **Frontend Activity dilayani lewat tunnel yang sama**, bukan di cloud. Peta sebelumnya mengunci "frontend di cloud" dengan alasan "butuh HTTPS publik" — tunnel juga memenuhinya, dan satu origin jauh lebih murah.

**Tunnel: domain sendiri + named tunnel.**

- Beli domain, pasang di Cloudflare (gratis), buat **named tunnel**. Hostname menjadi permanen.
- **Quick tunnel ditolak.** Tiap restart namanya berganti, dan mapping URL di Developer Portal **tidak punya API** — Portal satu-satunya permukaan. Lupa memperbaikinya terbaca sebagai bug, bukan konfigurasi basi.
- Named tunnel juga menghapus tunggu propagasi 60-90 detik: record DNS dibuat sekali dan bertahan saat tunnel berhenti.
- **Application URL Override tetap MATI.** HMR tetap menembak port 443 lewat `server.ws.clientPort`.

**Aplikasi Discord kedua khusus dev.**

- Token, client ID, database, dan port terpisah. Bot produksi tetap melayani saat dev berjalan.
- Akibat wajib: **dev dan produksi tidak boleh berbagi port maupun database.**

**Auto-start lewat Task Scheduler.**

- Dua entri: bot dan tunnel. Trigger *at startup*, "run whether user is logged on or not", sebagai akun pengguna.
- `ExecutionTimeLimit` bawaannya **PT72H** wajib dimatikan — proses panjang akan dibunuh setelah tiga hari.
- Pembaruan lewat `deploy.ps1`: hentikan task → `git pull` → mulai task lagi.

**Tata letak berkas.**

| Apa | Di mana |
|---|---|
| Config produksi (`.env`) | `C:\ChessPlatform\.env` — **di luar** semua checkout |
| Database produksi | `C:\ChessPlatform\data\chess.db` — di luar semua checkout |
| Log | `C:\ChessPlatform\logs\` dengan rotasi ukuran |
| Backup | `C:\ChessPlatform\backups\` + salinan ke folder cloud-sync |
| Binary Stockfish | Satu lokasi kanonik di luar checkout, `STOCKFISH_PATH` absolut |
| Rahasia dev | `backend/.env` + `activity/.env`, per komponen |
| Data dev | Di dalam worktree masing-masing |

- **Checkout produksi murni kode.** `git clean -xdf` di sana tidak bisa menghapus token, rating, atau log.
- **Migrasi Alembic dijalankan otomatis saat start**, sebelum melayani.
- **Backup memakai API backup SQLite**, bukan salin berkas — database berjalan mode WAL, dan menyalin berkas hidup bisa menghasilkan salinan rusak.

**Jalur migrasi VPS.**

- Tanpa Docker: `uv sync` + unit systemd + binary Stockfish Linux. Node tidak dibutuhkan di VPS karena Activity dilayani sebagai berkas statis.
- Konfigurasi tetap lewat environment variable, jadi bentuk ini tetap portabel.

## Alasan

- **Proses native menghapus seluruh rantai WSL.** Docker Desktop tidak bisa start tanpa login; WSL2 mematikan dirinya saat idle. Proses native tidak punya kedua masalah itu, dan Task Scheduler terdokumentasi Microsoft untuk berjalan tanpa sesi login.
- **Satu proses karena satu event loop.** `discord.py` dan uvicorn sama-sama asyncio; memisahkannya menuntut IPC untuk sinyal "game selesai → analisa" yang ADR-0009 sudah janjikan sebagai pemanggilan langsung.
- **Backend menyajikan berkas statis karena satu origin lebih murah.** Tanpa CORS, tanpa dua URL yang harus dijaga sinkron, dan tanpa proses tambahan yang bisa basi.
- **Named tunnel karena chore-nya berulang dan senyap.** Ongkosnya domain; sisi Cloudflare gratis. Yang dibeli adalah tidak adanya langkah manual yang gagal tanpa suara.
- **Aplikasi Discord kedua karena satu token tidak boleh dua koneksi gateway.** Tanpa pemisahan, mengembangkan berarti mematikan bot produksi — dan jam game yang sedang berjalan ikut berhenti.
- **Config dan data di luar checkout karena checkout adalah tempat `git` bekerja.** Menaruh state di dalamnya berarti setiap operasi pembersihan adalah kesempatan kehilangan rating.
- **Binary Stockfish di luar checkout karena ia artefak lokal 103 MB yang gitignored.** Di dalam checkout, tiap worktree baru harus mengunduhnya lagi — masalah yang sudah berulang di beberapa sesi.

## Konsekuensi

- **`docker-compose.yml` dan `backend/Dockerfile` harus dihapus saat implementasi.** Selama masih ada, keduanya menyiratkan jalur yang sudah ditolak.
- **`.env.example` harus diperbarui saat implementasi**: `STOCKFISH_PATH` kini menunjuk lokasi kanonik di luar checkout, bukan `engine/stockfish.exe`; jalur container (`/app/engine/stockfish`) tidak berlaku lagi; dan variabel baru untuk jalur data, log, serta port perlu ditambahkan supaya dev dan produksi bisa berdampingan.
- **ADR-0003 diamendemen**: konsekuensinya menyebut "orkestrasi Docker Compose" sebagai jalur migrasi VPS. Jalur itu kini `uv sync` + systemd.
- **ADR-0004 diamendemen**: konsekuensinya menyebut `backend/Dockerfile` sebagai cerminan Python 3.14. Rujukan itu hilang bersama Dockerfile-nya.
- **Dev dan produksi wajib berbeda port dan database.** Dua app Discord, dua `.env`, dua database.
- **Bot produksi dan API berbagi nasib.** Satu exception fatal menjatuhkan keduanya. Restart otomatis Task Scheduler yang menutupinya, dan ADR-0002 sudah mewajibkan state pulih setelah restart.
- **Task Scheduler menyimpan password akun sebagai LSA secret.** Di mesin satu-pengguna ini, penyerang yang bisa membacanya sudah punya admin.
- **Isi database ikut ke folder cloud-sync.** Hanya nama pemain dan rating; tidak ada token.
- **Named tunnel menuntut pembelian domain** — satu-satunya pengeluaran uang di proyek ini.
- **Container hanya melihat 8 core, bukan 28**, karena `.wslconfig` menyetel `processors=8`. Tidak lagi relevan karena Docker dibuang, tapi relevan kalau VPS nanti memakai container.
- **`.wslconfig` mesin ini memuat `pageReporting=true` di bawah `[wsl2]`**, yang tampaknya bukan kunci yang dikenal — kunci terdokumentasi adalah `autoMemoryReclaim` di bawah `[experimental]`. Di luar lingkup ticket ini; dicatat supaya tidak hilang.

## Fakta terverifikasi (jangan ulangi)

- **Linux Stockfish jalan di container di mesin ini.** Aset: `stockfish-linux-x86-64-universal.tar.gz` dari rilis `sf_19`, 81.388.977 byte, SHA256 `9defc0d4e55d49c65a6d042f3e571a39fcea499ade6dbe741b53b8c65e03611f` (cocok dengan digest rilis). Binary di dalamnya ELF 103 MB, **NNUE tertanam** — deployment satu berkas. Nama aset `ubuntu`/`avx2` **tidak ada** di rilis sf_19.
- **Terukur**: `bench` 51 posisi, Hash 128, Threads 4, 1 juta node → Linux container **8,5-9,0 detik** (5,5-5,8 Mnps); Windows native **11,6-12,7 detik** (3,9-4,2 Mnps). Per posisi: Linux median 246 ms, Windows median 256 ms. Angka Windows **melayang naik** selama sesi karena mesin sedang berbeban, jadi klaim yang jujur adalah **"tidak ada penalti containerisasi"**, bukan "Linux 40% lebih cepat".
- **Jebakan `go nodes` lewat stdin ber-pipa.** Mengirim `go nodes 1000000` lalu `quit` sekaligus mengembalikan `bestmove a2a3`, depth 1, nodes 0 — jawaban salah yang **terlihat masuk akal**. `go` memulai pencarian secara asinkron dan `quit` langsung menghentikannya. Harness harus menahan stdin terbuka dan menunggu `bestmove`.
- **Argumen `bench` berurutan**: `bench [hash] [threads] [limit] [fenFile] [limitType]`. `bench 128 4 1000000 nodes` menganggap `nodes` sebagai nama berkas FEN; yang benar `bench 128 4 1000000 default nodes`.
- **Mengalihkan stderr tanpa mengurasnya membuat engine menemui jalan buntu** saat buffer pipa ~4 KB penuh.
- **Docker Desktop di mesin ini ada di `D:\Program\Docker Desktop.exe`**, bukan jalur bawaannya.
- **Mesin ini praktis tidak pernah tidur** — nol kejadian sleep dalam 21 hari, timeout sleep AC sudah `0`. Sumber downtime yang nyata adalah reboot Windows Update.
- **`cloudflared service install` berjalan di Windows dan bertahan reboot**, nama service `Cloudflared`, tapi butuh admin, penyalinan `cert.pem` + kredensial ke `C:\Windows\System32\config\systemprofile\.cloudflared\`, dan sunting registry `ImagePath`. Tidak dipakai; tunnel dijalankan lewat Task Scheduler.
- **`VITE_HMR_PORT` bukan fitur Vite.** Tidak ada variabel itu di dokumentasi Vite; namanya konvensi komunitas, jadi `vite.config.ts` yang harus membacanya. Bentuk yang didokumentasikan adalah `server.ws.clientPort`.

## Ditunda

- **Nama domain dan registrar belum dipilih.**
- **Pembuatan app Discord kedua belum dilakukan.**

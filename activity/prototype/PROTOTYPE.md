# PROTOTYPE — kerangka Activity + sinkronisasi langkah

> ⚠️ **KODE BUANGAN.** Ini menjawab satu pertanyaan, lalu dibuang. Tidak ada
> penyimpanan, tidak ada jam catur, tidak ada analisa, tidak ada penanganan
> error yang layak. Jangan diangkat ke produksi apa adanya.
>
> Ticket: [Prototype: kerangka Activity + sinkronisasi langkah](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/6)
> (peta: [Peta: Platform Catur Discord](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/1))

## Pertanyaan yang dijawab

> Apakah papan drag-and-drop + sinkronisasi dua pemain benar-benar bisa dipakai
> di dalam iframe Discord?

Ini de-risk terbesar di peta. Riset menemukan **belum pernah ada Activity catur
publik** — nol hasil pencarian. Kalau drag-and-drop di dalam iframe ternyata
tidak nyaman, seluruh desain interaksi harus dipikirkan ulang **sebelum**
dibangun sungguhan. Karena itu prototype ini ada.

## Yang dibuktikan

| # | Yang diuji | Di mana |
|---|---|---|
| 1 | Activity terbuka dari Discord lewat tunnel, menampilkan papan | `src/App.tsx` |
| 2 | Papan menggambar posisi dari FEN | `src/fen.ts` |
| 3 | Klik bidak → tujuan legal tersorot → klik tujuan → terkirim | `src/Board.tsx` |
| 4 | Backend memvalidasi, mengembalikan FEN baru, papan ter-update | `backend/src/chessbot/prototype_activity.py` |
| 5 | OAuth Discord jalan — Activity tahu ID Discord pemain | `src/auth.ts` |
| 6 | Dua klien di instance sama saling melihat langkah (WebSocket) | `useGame.ts` + `prototype_activity.py` |

**Sengaja tidak ada:** jam catur, Chess960, lawan komputer sungguhan, turnamen,
analisa, tema visual, tata letak mobile.

## Cara menjalankan

### Sekali saja — siapkan

```powershell
cd backend; uv sync --all-extras          # sekali, kalau .venv belum ada
cd ..\activity\prototype; npm install     # sekali, kalau node_modules belum ada
```

### Uji cepat di browser (tanpa Discord)

Tidak butuh app Discord, tidak butuh tunnel. Ini cara tercepat menilai
drag-and-drop:

```powershell
cd activity\prototype
.\run-prototype.ps1
```

Lalu buka:
- Jendela 1: `http://localhost:3000/?debug=1&room=uji1&name=Putih`
- Jendela 2: `http://localhost:3000/?debug=1&room=uji1&name=Hitam`

Instance **sama** (`room=uji1`) = satu game. Langkah di satu jendela langsung
muncul di jendela lain.

> **Punya satu akun saja?** Centang **"Lawan simulasi"** di panel kanan. Kursi
> hitam diisi bot yang melangkah acak, jadi alur giliran tetap bisa dinilai
> sendirian. (Ini memang ditambahkan khusus karena pengujian dilakukan dengan
> satu akun.)

### Uji sesungguhnya di dalam Discord

```powershell
cd activity\prototype
.\run-prototype.ps1 -Tunnel
```

Skrip akan mencetak hostname tunnel dan perintah URL Mapping yang harus
dimasukkan ke Developer Portal. Lihat bagian **Menyiapkan app Discord** di bawah.

> Hostname quick tunnel butuh **~60-90 detik** sebelum bisa di-resolve. Tunnel
> melaporkan "siap" jauh sebelum DNS mengenal namanya — kegagalan resolve awal
> itu **normal**, bukan kegagalan. Sudah diverifikasi di ticket #5.

## Menyiapkan app Discord (belum ada)

Belum ada Discord Application untuk proyek ini. Urutan pembuatannya:

1. **Buat app** — [Developer Portal](https://discord.com/developers/applications)
   → New Application. Catat **Application ID** (= client ID).
2. **Aktifkan Activities** — tab *Activities* → Enable Activities.
   - **URL Mapping**: `PREFIX /` → `TARGET <hostname-tunnel>`
     - target **tanpa** `https://`, dan **harus direktori** (bukan berkas)
   - **Application URL Override: MATIKAN.** Dokumentasi menyebut dua kali
     "should not be enabled" untuk alur tunnel.
3. **Client secret** — tab *OAuth2* → Reset Secret. Isi ke `backend/.env`:
   ```
   DISCORD_CLIENT_ID=<application id>
   DISCORD_CLIENT_SECRET=<secret>
   ```
   dan `activity/prototype/.env`:
   ```
   VITE_DISCORD_CLIENT_ID=<application id>
   ```
   (Salin dari `.env.example` di masing-masing tempat. Repo ini publik — `.env`
   sudah di-`.gitignore`.)
4. **Install ke server** — tab *Installation* → Install Link. Buka link itu di
   server Discord Anda. Tidak perlu verifikasi app untuk pemakaian server sendiri.
5. **Buka Activity** — di voice channel, klik ikon Activity dan pilih app ini.

## Tangkapan layar

`docs/tangkapan-layar.png` — hasil render sungguhan di Chrome headless setelah
`1.e4`. Perhatikan: **"giliran hitam"** ditampilkan, dan panel riwayat berisi
`1. e4 (e2e4)`. Tangkapan ini juga memperlihatkan penegakan giliran bekerja —
klik berikutnya pada bidak hitam diabaikan karena bukan giliran pemain ini.

## Yang sudah terverifikasi (sebelum Anda mencoba)

Semua di bawah ini dijalankan sungguhan, bukan klaim dari dokumen.

| Uji | Hasil | Perintah |
|---|---|---|
| Logika room tanpa server | **25/25 lulus** | `python -I tests\prototype_check.py` |
| Protokol WebSocket end-to-end, langsung ke backend | **36/36 lulus** | `python -I tests\prototype_smoke.py http://127.0.0.1:8000` |
| Protokol WebSocket **lewat proxy Vite** | **36/36 lulus** | `python -I tests\prototype_smoke.py http://127.0.0.1:3000` |
| Render papan di browser sungguhan | **11/11 lulus** | `python -I tests\prototype_render.py <python> <chrome>` |

Yang dibuktikan uji-uji itu:

- **WebSocket melewati proxy** — upgrade `ws://` diteruskan Vite ke backend.
  Ini kendala terbesar, dan **bekerja** dengan URL relatif + `ws: true`.
  Tidak perlu `patchUrlMappings`.
- **Sinkronisasi dua klien** — langkah di satu koneksi muncul di koneksi lain.
- **Penegakan giliran** — melangkah dua kali ditolak (`refused`), langkah ilegal
  ditolak (`illegal`), penonton tidak bisa melangkah (`spectator`).
- **Skakmat lewat protokol** — skenario scholar's mate berakhir `checkmate`,
  pemenang `white`, alasan `skakmat`.
- **Papan tergambar** — 64 kotak, 32 bidak, di kotak yang benar dari FEN.
- **Klik-untuk-melangkah** — pilih bidak → tujuan legal tersorot → klik tujuan →
  langkah terkirim → server mengonfirmasi → papan ter-update.
- **Lawan simulasi** — kursi kosong diisi bot dan bot melangkah sendiri, jadi
  pengujian satu akun tetap bisa menilai alur giliran.

**Yang BELUM terverifikasi:** drag-and-drop di dalam iframe Discord sungguhan,
dan kenyamanan sebenarnya. Itu **hanya bisa dinilai manusia** — itulah sisa
pekerjaan ticket ini. Drag-and-drop belum bisa diotomasi; klik sudah.

## Yang perlu Anda nilai

Saat mencoba, perhatikan — **"wah, itu seharusnya tidak mungkin"** dan
**"huh, saya kira X akan beda"** adalah temuan yang paling berharga:

- **Drag-and-drop** — apakah bidak mengikuti kursor dengan enak di dalam iframe?
  Apakah ada jeda yang terasa? Coba juga jalur **klik-klik** (klik bidak, klik
  tujuan) — mana yang lebih enak?
- **Latensi** — langkah terasa langsung atau menunggu server? Ada label
  "menunggu server…" saat langkah belum dikonfirmasi.
- **Sinkronisasi** — langkah di satu jendela muncul di jendela lain tanpa
  refresh?
- **Sorotan tujuan legal** — cukup jelas? Terlalu ramai?
- **Skala** — papan cukup besar di dalam Activity? Di layar sempit?
- **Penolakan** — coba langkah ilegal (seret bidak ke kotak acak). Pesan
  "Ditolak server" muncul dan papan kembali ke posisi benar?

## Arsitektur yang dibuktikan

```
Discord (iframe)
  └─ Activity (Vite + React)  ── WebSocket ──►  Backend (FastAPI)
       drag & klik                 /api/ws        python-chess = OTORITATIF
       optimistic UI               /api/token     validasi via find_move()
       gambar dari FEN             /api/sehat
```

**Satu tunnel, satu origin.** Tunnel menunjuk ke Vite; Vite mem-proxy `/api`
(REST **dan** WebSocket) ke backend Python. Pola ini disalin dari preseden
multiplayer resmi (`colyseus/discord-activity`). Konsekuensinya: Activity
memakai URL **relatif**, jadi satu jalur kode bekerja baik di dalam Discord
maupun di browser biasa — tanpa `patchUrlMappings`.

**Backend otoritatif (ADR-0002).** Activity mengirim *niat* langkah; backend
memvalidasi dengan `board.find_move()` (yang **memeriksa** legalitas, berbeda
dari `board.push()`) dan menyiarkan state baru. Activity menggambar langkah
secara optimistis untuk kelancaran, lalu membatalkannya kalau server menolak.

## Kendala yang ikut terverifikasi di sini

- **WebSocket lewat proxy Discord** bekerja dengan Vite `ws: true` dan URL
  relatif. Tidak perlu `patchUrlMappings`.
- **`allowedHosts` Vite** harus memuat `.trycloudflare.com` — hostname quick
  tunnel berubah tiap restart.
- **HMR lewat tunnel** harus menembak port 443 (`VITE_HMR_PORT=443`), bukan 3000.

## Berkas

```
backend/
  src/chessbot/prototype_activity.py   FastAPI + room + WS + lawan simulasi
  tests/prototype_check.py             cek logika room tanpa server (25 cek)

activity/prototype/
  src/App.tsx          kerangka + panel samping
  src/Board.tsx        papan drag-and-drop + klik-klik
  src/fen.ts           parsing FEN seadanya
  src/auth.ts          SDK Discord + jalur debug browser
  src/useGame.ts       WebSocket + optimistic UI
  run-prototype.ps1    nyalakan semuanya
```

## Setelah pertanyaan terjawab

Prototype ini dibuang; yang diselamatkan hanya **jawabannya** dan bagian logika
yang terbukti benar. Keputusan yang menunggu reaksi:

- **Modalitas langkah** — drag, klik, atau keduanya? (ticket #8, terblokir #6 ini)
- **Bentuk visual & tema papan** — kabut peta, menunggu prototype ini.
- **Sinkronisasi waktu nyata** — bagaimana konflik diselesaikan kalau kedua
  pemain melangkah bersamaan. Kabut peta, menunggu prototype ini.

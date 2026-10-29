# Render papan untuk thumbnail embed: `chess.svg` + `resvg-py`

## Konteks

Ticket [Jalur render papan untuk thumbnail embed](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/23) menanyakan bagaimana backend menghasilkan **gambar papan** untuk embed. Ia tergraduasi dari kabut peta oleh ticket [Mockup: tampilan hasil analisa](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/7): keputusan **varian B "papan dulu"** menempatkan thumbnail papan di dalam embed, dan thumbnail Discord menerima **gambar**, bukan HTML. Mockup #7 membuktikan tata letaknya; ia tidak membuktikan cara membuat gambarnya.

Tiga hal sudah terkunci sebelum ticket ini dan tidak dibuka ulang:

- **Papan di Activity sudah tergambar dari FEN tanpa server** — dibuktikan #6 (`src/fen.ts` + `Board.tsx`, 11/11 uji render lulus). Itu tidak membantu embed, yang butuh PNG.
- **Discord tidak merender SVG inline** — terverifikasi #2, dan dikonfirmasi ulang riset ini dari dokumentasi primer: ekstensi yang diizinkan untuk gambar embed hanya `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`.
- **Pillow 12.3.0 jalan di Python 3.14** (riset #5) dan `pyproject.toml` menyimpan extra `render = ["pillow>=12.3"]` untuk jalur itu.

Yang belum diputuskan adalah **jalurnya**, dan biayanya nyata: render berjalan setelah analisa Stockfish selesai, di jalur yang ADR-0009 tetapkan sebagai **antrean FIFO satu worker**. Jalur render yang lambat atau bisa menggantung menahan setiap game di belakangnya.

## Keputusan

**`chess.svg.board()` dari python-chess, dirasterisasi `resvg-py`, menjadi PNG yang dilampirkan ke pesan analisa.**

### Jalur render

- **`chess.svg.board()`** menghasilkan SVG. API-nya stabil (`chess 1.11.2`, tidak berubah sejak 1.10.0) dan sudah menyediakan semua yang dibutuhkan: `size` (px persis pada `width`/`height`, `viewBox` tetap 390), `orientation`, `lastmove`, `check`, `colors`, `coordinates`.
- **`resvg-py>=0.5`** merasterisasinya. Wheel `abi3-win_amd64` 1,18 MB, tanpa native install, **12,8 ms/gambar** (end-to-end `board()` + render + tulis = **14,0 ms median**, p95 14,6).
- **Chromium headless ditolak.** Ia terverifikasi bekerja di mesin ini, tapi **362 ms** — **26× lebih lambat** — dan menambah proses eksternal ke jalur kritis. Ia juga satu-satunya kandidat yang sudah punya riwayat menggantung di mesin ini (path relatif → menggantung, bukan gagal), dan `--user-data-dir` wajib, dengan kegagalan senyap tanpa itu.
- **Pillow ditolak.** Jalur itu berarti menggambar 64 kotak dan menempel 12 aset bidak sendiri — kerja yang tidak perlu ketika `chess.svg` sudah menggambarnya dengan benar, plus pertanyaan lisensi set bidak yang tidak perlu dijawab.

Rasterizer lain diuji dan gugur karena **menghasilkan gambar yang salah**, bukan karena lambat:

| Rasterizer | Hasil |
|---|---|
| `pyvips` | Benar, 6,9 ms — tapi 34,7 MB dan `pyvips-binary` harus dipin terpisah; `pyvips` saja gagal `import` |
| `skia-python` | **Hex 8-digit dirender hitam** (`#ff0000cc` → RGB(0,0,0)); 83,7 MB + numpy/openblas |
| `pymupdf` | **`radialGradient` jadi hitam pekat** (kotak `check=`); 191–215 MB; AGPL-3.0 |
| `cairosvg` | **Gagal total** — wheel tidak membawa Cairo: `no library called "cairo-2" was found` |
| `svglib` | **Crash** `AttributeError: 'NoneType' object has no attribute 'moveTo'` begitu ada `check=`; ukuran selalu 192×192 |
| `resvg` 0.2.0 | Rusak — 1,5 KB gambar diagonal acak. **Paket berbeda dari `resvg-py`**, jangan tertukar |
| `chess-board` | Tidak bisa di-install — `pygame` 2.6.1 tidak punya wheel `cp314-win_amd64` |

Tidak ada pustaka Python yang langsung mengubah FEN menjadi PNG dengan layak.

### Apa yang digambar

- **Posisi akhir game.** Deterministik dan langsung menjawab "game ini berakhir bagaimana". Bukan blunder terburuk: embed sudah memuat **seluruh** blunder beserta notasinya (#7), jadi papan tidak perlu mengulanginya, dan pertanyaan "sebelum atau sesudah blunder?" hanya menambah ambiguitas.
- **Selalu putih di bawah.** Orientasi dari sudut pemenang membuat papan berganti arah antar-game dan memaksa pembaca menghitung ulang. Pembaca embed adalah seluruh channel, bukan satu pemain.
- **Sorot langkah terakhir, tanpa koordinat.** Langkah terakhir adalah jawaban atas "kenapa game ini berakhir" — pada skakmat, ia langkah pembunuhnya. Koordinat `a`–`h`/`1`–`8` dibuang karena di ukuran thumbnail ia menjadi noda tak terbaca.
- **Sorotan bersifat opsional.** Tanda tangannya `last_move: tuple[str, str] | None`; bila langkah terakhir tidak terbaca, papan tetap digambar tanpa sorotan. Yang diragukan di sini hanya hiasan, bukan isi.
- **Semua jenis game, tanpa pengecualian** — lawan komputer, impor, turnamen. Papan adalah fungsi dari FEN akhir, dan setiap game yang dianalisa punya FEN akhir. **Game 1-ply juga digambar**: syaratnya "ada FEN akhir", bukan "ada akurasi".
- **320×320 px**, `size=320`. `chess.svg` mengeluarkan PNG 320×320 **persis** pada ukuran itu — tidak ada penskalaan tambahan.

### Pengiriman

- **Lampiran pesan**, dirujuk `thumbnail.url = "attachment://papan.png"`. Terverifikasi dari dokumentasi primer: *"Images can also be referenced in embeds using the `attachment://filename` URL"*, dan `.png` termasuk ekstensi yang diizinkan. Tidak menambah permukaan publik — tidak ada direktori gambar, tidak ada URL kedaluwarsa.
- **Tetap `thumbnail`, bukan `image`**, sesuai #7. Papan adalah penanda identitas game, bukan alat baca; gambar penuh akan mendorong daftar blunder dan urutan langkah ke bawah.
- **Alt text berisi FEN.** Pembaca layar mendapat posisi persisnya, bukan deskripsi kabur. Ini juga satu-satunya tempat FEN muncul di permukaan Discord.
- **Hanya pesan analisa** yang membawa papan. Pengumuman hasil game (ADR-0015) tetap teks murni dan tetap **segera** — menunggu render berarti hasil game tertahan oleh hiasan.

### Alur dan kegagalan

- **Render berjalan di dalam worker analisa**, tepat sebelum pesan hasil disusun. Satu tempat, satu urutan, tanpa koordinasi baru antar-komponen. Terukur 14 ms, jadi tidak bisa memicu kelaparan antrean.
- **Timeout keras 10 detik.** Chromium yang membuat kekhawatiran ini nyata sudah tidak dipakai, jadi faktor 700× terhadap biaya terukur memang longgar — dan itu murah.
- **Gagal render → embed tetap terkirim tanpa thumbnail, dicatat keras.** Gambar adalah hiasan; analisa adalah isinya. Sejalan dengan penalaran ADR-0016 soal `Pemain <id>`: yang diragukan hanya label, bukan angka.
- **Berkas sementara, dihapus setelah kirim sukses.** Discord menyimpan lampirannya sendiri; salinan lokal adalah arsip kedua tanpa pembaca, dan ADR-0010 menempatkan data produksi di luar checkout — setiap berkas baru di sana adalah kewajiban backup baru.

### Bentuk kode

- **Satu fungsi murni**: `render_board_png(fen, last_move) -> bytes`. Tanpa kelas, tanpa konfigurasi, tanpa status. Palet dan ukuran adalah konstanta modul.
- **Hanya menggambar papan.** Tanpa layanan render umum, tanpa parameter HTML, tanpa endpoint HTTP. ADR-0012 sudah **menolak** grafik PNG untuk `/stats`, jadi papan adalah satu-satunya gambar yang platform ini butuhkan — kemampuan umum di atas satu pemakai adalah abstraksi tanpa implementasi kedua.
- **Satu sumber gaya.** Palet tinggal di **satu berkas CSS custom property di `activity/`**; Activity memuatnya lewat `<link>`, backend membacanya sebagai teks. Bukan dua salinan konstanta: empat bug terakhir #7 semuanya berakar pada "dua jalur yang seharusnya menghitung hal yang sama, menghitung hal yang berbeda".

## Alasan

- **`resvg-py` dipilih karena ia satu-satunya yang sekaligus benar dan murah.** Ia lolos tiga hal yang mematahkan kandidat lain: gradien `radialGradient` (kotak `check=`), warna hex 8-digit (yang `chess.svg` pancarkan dari `Arrow`), dan alpha. `skia-python` dan `pymupdf` menghasilkan gambar yang **terlihat wajar tapi salah** — mode kegagalan yang persis sama dengan 10 bug #7.
- **Chromium 26× lebih lambat bukan alasan utamanya.** Alasan utamanya: ia menambah proses eksternal ke jalur kritis setelah Stockfish selesai, di jalur yang ADR-0009 tetapkan sebagai antrean FIFO satu worker. Mesin ini juga sudah punya riwayat Chrome menggantung alih-alih gagal, dan kegagalan senyap tanpa `--user-data-dir` yang benar.
- **Pillow ditolak karena pertanyaannya sudah dijawab di tempat lain.** `chess.svg` menggambar papan dengan benar dan gratis; menggambar manual berarti mengulanginya, plus menyediakan set bidak yang lisensinya harus diperiksa. *(Riset #5 sudah memverifikasi Pillow jalan di 3.14 — itu bukan yang menjadi keberatan.)*
- **Posisi akhir, bukan posisi awal.** Mockup #7 memakai posisi awal karena mockup butuh papan, bukan karena itu keputusan. Embed yang menampilkan posisi awal tidak mengatakan apa pun tentang game yang dianalisa.
- **Sorotan langkah terakhir tanpa koordinat adalah pertukaran keterbacaan, bukan penghematan.** Di 320 px yang dikecilkan Discord menjadi thumbnail, huruf koordinat berhenti menjadi informasi dan mulai menjadi noda.
- **Lampiran, bukan URL publik.** Tunnel yang sudah ada (ADR-0010) melayani Activity, bukan aset. Menyajikan gambar lewat rute publik berarti menambah rute, masa berlaku, dan pembersihan — untuk berkas yang Discord simpan sendiri begitu pesan terkirim.
- **Render di dalam worker, bukan thread terpisah.** Pada 14 ms, memisahkannya membeli latensi yang tidak ada dan menambah urutan kirim pesan yang tidak pasti.
- **Gagal render tidak menjatuhkan embed** karena arah kesalahannya asimetris: embed tanpa papan tetap berguna, embed yang tidak terkirim tidak berguna sama sekali.

## Konsekuensi

- **`backend/pyproject.toml`:** extra `render = ["pillow>=12.3"]` **dibuang**, `resvg-py>=0.5` masuk `dependencies` langsung. Extra opsional untuk jalur yang sudah dipilih menyiratkan Pillow masih mungkin.
- **`CONTEXT.md` mendapat istilah Thumbnail papan** — gambar posisi akhir yang dilampirkan ke pesan analisa, dirujuk embed lewat `attachment://`, dan **bukan** Papan (yang berarti tampilan interaktif di Activity).
- **ADR-0009 bagian Pelaporan mendapat penunjuk**: penyusunan pesan hasil kini mencakup satu langkah render yang bisa gagal tanpa menggagalkan pesan. ADR-0009 sendiri tidak berubah — angkanya, anggaran node, dan rumusnya tidak tersentuh.
- **Kode render harus mencampur warna sorotan sendiri.** Mockup #7 menyorot dengan **emas `#d4af37` pada 38% di atas warna kotak**, sementara `chess.svg` memakai warna **solid** untuk `square light lastmove` / `square dark lastmove`. Karena keputusan sesi ini mengunci palet mockup, dua campuran itu dihitung di muka dan **sudah terverifikasi**: `#c3bb95` di kotak terang, `#89805c` di kotak gelap. Jangan menyerahkan pencampuran ini ke rasterizer.
- **Ukuran tampil thumbnail Discord tetap tidak diketahui.** Ia absen dari Embed Object, Embed Image Structure, **dan** Embed Limits. `chess.svg` merender 320×320 px dan itu yang dipakai; mengukur ukuran tampil butuh embed uji sungguhan ke channel, dan hasilnya hanya mengubah angka `size=`.
- **Satu pemeriksaan assert-based wajib ada** yang membaca piksel hasil render, bukan mata: petak `a1` gelap, bidak berada di petak yang benar-benar ditempati FEN, warna bidak sesuai FEN. Pola yang sama dengan `verify_analysis_formulas.py` (ADR-0009) — nilai emas, bukan tangkapan layar.
- **Menambah dependensi native pertama di luar python-chess.** `resvg-py` membawa binary Rust sendiri lewat wheel abi3, jadi tidak ada langkah instalasi tambahan — tapi ia tetap satu wheel platform-specific yang harus ada di tiap mesin (dev, produksi, VPS Linux sesuai ADR-0010).
- **Server Members intent tidak tersentuh.** Ticket [Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27) tetap pertanyaan terbuka untuk alasannya sendiri (`/impor` menerima lampiran berkas).

## Verifikasi

**`backend/tools/verify_board_render.py`** — **25/25 lulus**. Ia membaca piksel PNG hasil render, bukan tangkapan layar, mengikuti pola `verify_analysis_formulas.py` (ADR-0009). Jalankan dengan `python -I`:

```sh
backend/.venv/Scripts/python.exe -I backend/tools/verify_board_render.py
```

Yang diperiksanya: ukuran 320×320 persis · orientasi putih-di-bawah (a1 gelap, h1 terang, a8 terang, h8 gelap, dan kedua pasangan itu identik) · papan kosong hanya dua warna · bidak hadir di petak yang FEN sebut dan petak lain tetap polos · warna bidak sesuai kasus FEN · sorotan menyentuh asal & tujuan saja · palet mockup #7 bisa dipasang · campuran sorotan bisa dinyatakan sebagai hex solid (`#c3bb95` di kotak terang, `#89805c` di kotak gelap).

Riset ticket ini menguji setiap klaim dengan render sungguhan, bukan metadata wheel:

| Klaim | Bukti |
|---|---|
| `chess.svg.board(size=N)` mengeluarkan PNG **persis** N×N | Diuji 64/128/160/256/320/512 — semuanya persis |
| `resvg-py` merender benar | Papan + bidak + gradien `check=` + hex 8-digit + alpha, dibandingkan piksel dengan Chrome sebagai ground truth (mean-abs **1,02**, selisih hanya antialiasing tepi) |
| Biaya render | **12,8 ms** rasterisasi, **14,0 ms** end-to-end median, p95 14,6 |
| Chromium 26× lebih lambat | **362 ms** median (n=10, dua putaran), rentang 340–522 ms |
| Tidak ada kebocoran memori | RSS 23,20 MB → 24,32 MB setelah 500 render |
| `thumbnail.url` menerima `attachment://` | Dokumentasi primer: *"Images can also be referenced in embeds using the `attachment://filename` URL"* |

**Tiga kesalahan yang dibuat skrip pemeriksaan ini sebelum ia lulus** — dicatat karena semuanya menghasilkan "lulus" yang salah, bukan gagal:

1. **Dekoder PNG hanya menangani filter None/Sub/Up.** resvg memakai Paeth (4); filter yang tidak ditangani membuat setiap pembacaan piksel berikutnya keliru.
2. **Ambang luminansi mutlak 128.** Palet bawaan `chess.svg` **bukan hitam-putih**: "gelap" = coklat `(209,139,71)`, "terang" = krem `(255,206,158)`. Pembandingnya harus relatif antar kotak.
3. **Sampel titik tengah kotak.** Bidak selalu digambar di tengah, jadi sampel tengah mengukur **bidaknya**, bukan warna kotaknya — di posisi awal, a1 berisi benteng putih dan terbaca sebagai kotak terang.

Pelajaran yang sama dengan #7: assertion yang salah menghasilkan lulus-palsu, dan hanya membandingkan angka dengan sumber kedua yang menemukannya.

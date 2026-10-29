# Mode lawan komputer: proses engine sendiri, Skill Level + batas kedalaman, empat tingkat berlabel

## Konteks

Ticket [Konfigurasi mode lawan komputer](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/14) lahir dari satu kontradiksi. Keputusan Q48 memilih preset 800/1200/1600/2000 Elo, sementara riset #3 membuktikan **`UCI_Elo` tidak bisa turun di bawah 1320** — dan Stockfish FAQ menyatakan kalibrasinya ke skala manusia *"virtually impossible"*. Dua dari empat tingkat yang dijanjikan tidak bisa dicapai lewat antarmuka bawaannya.

Empat hal sudah terkunci sebelum ticket ini dan tidak dibuka ulang:

- **Lawan komputer adalah baris `players` bertanda `is_engine`** (ADR-0005). Ia tidak pernah punya rating dan tidak muncul di klasemen.
- **Game lawan komputer tidak berating** (ADR-0008, dipersempit ADR-0012 menjadi `source='engine'`). Predikatnya di kode, bukan kolom penanda.
- **`/challenge` menolak menantang bot** (ADR-0014). Mode ini tidak dicapai lewat sana, dan permukaannya memang diserahkan ke ticket ini.
- **Jam catur punya model lengkap** (ADR-0015): Fischer, sentidetik, `clock_started`, urutan potong-lalu-tambah, dan satu fungsi tutup game dengan sebab sebagai argumen.

**Riset ticket ini membalik satu premis yang berpotensi menyesatkan.** Lichess **tidak** memakai Stockfish resmi untuk bermain: kedelapan tingkatnya berjalan di **Fairy-Stockfish**, karena hanya engine itu yang menerima `Skill Level` **negatif** (min −20, sedangkan Stockfish resmi min 0). Commit fishnet `d6856528` berjudul *"fix weak UCI_Elo by switching to Skill Level"* — Lichess mencoba `UCI_Elo` lebih dulu dan meninggalkannya karena tidak bisa cukup lemah. Tabel tingkat Lichess **tidak bisa disalin**: di Stockfish 19, `Skill Level -9` ditolak **diam-diam** dan jatuh ke default 20, yaitu kekuatan penuh.

Dua temuan pengukuran lain yang membentuk keputusan:

- **Lemah di Stockfish bukan berarti cepat.** `Skill Level` memaksa `MultiPV ≥ 4` (`src/search.cpp:318-319`), sehingga `Skill 0` tanpa batas memakan **~3,3 detik/langkah** dan di jam `180s+2s` sanggup membakar **30 detik** untuk satu langkah. Sebaliknya `go depth 5` = **1-3 ms**. Lemah harus dibatasi **kedalaman**, bukan dibiarkan bebas.
- **`UCI_LimitStrength` wajib menyala** atau `UCI_Elo` menjadi no-op (`src/search.cpp:314` membaca `UCI_Elo` hanya bila flag itu benar). Ini bug termudah untuk dikirim.

## Keputusan

**`/komputer` membuat game melawan Stockfish 19 di proses engine tersendiri, dengan empat tingkat berlabel yang masing-masing adalah pasangan (Skill Level, batas kedalaman).**

### Proses engine

- **Proses kedua, terpisah dari worker analisa.** Dimuat malas saat game komputer pertama dibuka, lalu hidup terus. `Threads = 1`, `Hash = 16 MB`.
- **Satu proses melayani semua game komputer serentak**, diserialkan lewat satu kunci asinkron.
- **ADR-0009 tidak diamendemen, tapi dibatasi ruang lingkupnya.** "Satu worker FIFO" berlaku untuk **analisa**, bukan untuk seluruh platform. Ini harus disebut saat aturan itu didokumentasikan, persis seperti ADR-0014 membedakan kedaluwarsa Challenge dari keluarga 24-jam-bot-hidup.

### Tingkat

Empat tingkat, **berlabel saja tanpa angka Elo**:

| Tingkat | `Skill Level` | Batas | Latensi terukur |
|---|---|---|---|
| **Pemula** | 0 | `depth 2` | ~0,4 ms |
| **Menengah** | 5 | `depth 6` | ~3 ms |
| **Mahir** | 11 | `depth 12` | ~190 ms |
| **Ahli** | 20 | `depth 22` | ~2-3 s |

- **Default `tingkat:` adalah Pemula.** Asimetrinya sama dengan penalaran ADR-0017: pemain pemula yang kalah telak dari default menyimpulkan botnya rusak; pemain berpengalaman yang menang mudah hanya menaikkan tingkat sekali. Default yang terlalu lemah memperbaiki diri, yang terlalu kuat tidak.
- **Tanpa angka Elo di permukaan mana pun.** Angka Elo yang tidak terkalibrasi lebih buruk daripada tanpa angka: pemain ber-rating Lichess yang kalah dari "Pemula" akan menyimpulkan ada yang rusak. `UCI_Elo` **tidak dipakai sama sekali** — karena rentangnya 1320-3190 dan kita justru butuh di bawahnya.
- **`UCI_Elo` tetap tidak dipakai untuk apa pun**, dan itu disengaja. `CONTEXT.md` sudah menyatakan "Elo" hanya dipakai untuk menyebut preset lawan komputer; kini bahkan itu tidak lagi berangka.

### Jam

- **Mesin berjam simetris.** Ia memakai `white_centis`/`black_centis` yang sama dan bisa kehabisan waktu, dengan aturan ADR-0015 apa adanya — termasuk "kehabisan waktu = kalah, kecuali lawan tak punya bahan skakmat".
- **Anggaran pikir tidak pernah melihat jam.** Batasnya `depth`, bukan waktu. Mesin tidak bisa kehilangan waktu karena berpikir lama, karena di batas kedalaman kita ia berpikir 0,4 ms sampai 3 detik.
- **`engine.play()` tidak pernah diberi batas waktu dari jam.** Ini bukan preferensi gaya: mengukur langsung memperlihatkan bahwa `Skill 0` dengan `go wtime 180000 winc 2` memakai **30 detik** untuk satu langkah. Memberinya jam berarti mesin menghabiskan jamnya sendiri karena kebijakan `MultiPV ≥ 4` yang tidak bisa kita matikan saat skill menyala.
- **Jeda tetap ~600 ms sebelum langkah mesin diumumkan.** Tanpa itu, langkah tiba seolah bersamaan dengan langkah pemain. Angka ini masuk pita transisi standar (400-600 ms) dan tidak bergantung pada tingkat maupun sisa jam.

### Aturan permainan yang tidak dimiliki manusia

- **Mesin tidak pernah menyerah.** Game berakhir hanya lewat aturan papan. Stockfish tidak punya konsep menyerah, dan heuristik ambang eval adalah mekanisme baru yang bisa salah tanpa ada yang menemukannya sampai ada yang mengeluh.
- **Mesin selalu menolak tawaran remis.** Jawaban yang berguna hanya bisa datang dari eval-nya sendiri — heuristik ambang yang sama bermasalahnya dengan menyerah, dan `draw_type='agreed'` akan mencatat persetujuan yang sebenarnya keputusan algoritma. Tombol Menyerah (#24) tetap jalan bagi manusia sebagai jalan keluar.
- **Mesin tidak pernah menjadi pihak yang menawarkan remis.**

### Permukaan dan alur

- **Perintah `/komputer`**, boleh dijalankan **semua anggota server** di channel mana pun. Opsi: `tingkat:` (default Pemula), `warna:` (putih/hitam/acak, **default acak**, diundi saat game dibuat), `format:` (enam preset ADR-0015, **default "standar" 5+3**).
- **Catur standar saja.** Chess960 tidak ditawarkan; `UCI_Chess960` dimatikan eksplisit.
- **Balasan publik** berisi pesan game dengan tombol **Buka Papan**, pola ADR-0014. Balasan ephemeral hilang, dan pemain yang menutup Activity harus tetap bisa menemukan papannya.
- **Papan dimainkan di Activity**, sama seperti game manusia. ADR-0017 menegaskan thumbnail hanya untuk pesan analisa, bukan papan hidup.
- **Bila pemain memilih hitam, mesin memainkan langkah pertamanya langsung**, di dalam transaksi pembuatan game. Konsekuensinya mengikuti ADR-0015 apa adanya: ply 1 ter-commit berarti jam mulai, dan jam pemain sudah berjalan sebelum ia membuka Activity. Ini konsekuensi yang sama yang ADR-0014 sudah terima untuk putih.
- **Langkah manusia di-commit dalam satu transaksi, langkah mesin dihitung sesudahnya di transaksi terpisah.** Menghitungnya di dalam transaksi yang sama berarti menahan transaksi SQLite selama panggilan engine — persis yang dilarang WAL + satu jalur tulis ADR-0005.
- **Tanpa batas game komputer hidup per pemain**, dan **tanpa penjaga laju** di luar yang sudah diberikan Discord pada slash command. Tiap game satu baris tanpa entri rating, dan "Ditinggalkan" 24 jam menyapu yang tak pernah dimainkan.

### Identitas lawan

- **Satu baris `players` per tingkat**, `is_engine` menyala, bernama sesuai tingkatnya ("Komputer — Pemula").
- **Tingkat tersimpan di baris lawan, bukan di `games`.** Tidak ada kolom baru. Tingkat yang dihadapi bisa dibaca dari relasi selamanya, dan `/stats` sudah menyebut lawan komputer.
- **Label Pemilih game menyebut tingkatnya**: **"Lawan komputer — Pemula"**, menggantikan "Lawan komputer" ADR-0007. Dengan game serentak tanpa batas, dua game di tingkat berbeda harus bisa dibedakan sebelum ditekan.

### Hasil dan pengumuman

- **Hasil diumumkan lewat pesan baru tanpa mention.** ADR-0015 memilih pesan baru ber-mention justru karena lawannya mungkin tidak hadir; di sini satu-satunya manusia adalah pemain itu sendiri, yang sedang menatap papannya. Pesan baru tetap dipakai supaya hasilnya tidak terkubur di pesan game yang sudah lama.
- **Pesan analisa tetap menyusul** lewat pipeline ADR-0009, dengan thumbnail ADR-0017, sama seperti game lain.

### Kegagalan

- **Timeout 10 detik per percobaan** — bukan 60 detik milik ADR-0009, karena anggarannya berbeda: analisa menunggu 1 juta node, sedangkan batas tertinggi kita adalah `depth 22` yang terukur 2-3 detik.
- **Maksimum 3 percobaan**, lalu game ditutup `end_reason='abandoned'`, `result='none'`, tanpa entri rating. Pola yang sama dengan baris gagal ADR-0009, dan `abandoned` sudah ada di daftar `end_reason` ADR-0015.
- **Saat start, bot memindai game komputer hidup yang gilirannya mesin** dan memasukkannya ke antrean. Tanpa itu, crash di antara commit langkah pemain dan commit langkah mesin meninggalkan game yang menunggu selamanya, dan "Ditinggalkan" baru menyapunya sehari kemudian. Pola yang sama dengan rekonstruksi antrian analisa ADR-0009.

## Alasan

- **Proses kedua, bukan berbagi dengan analisa.** Satu analisa memegang engine 20-40 detik dan antreannya bisa 3-5 menit saat turnamen penuh. Berbagi berarti pemain manusia menunggu menit-menitan untuk langkah balasan komputer. Antrean prioritas tidak menyelesaikannya: `SimpleEngine` tidak bisa diinterupsi di tengah `analyse()`, jadi implementasinya berarti membatalkan dan mengulang analisa yang sedang berjalan — analisa jadi tidak deterministik dan bisa mundur berkali-kali.
- **Skill Level + batas kedalaman, bukan `UCI_Elo`.** Lantai 1320 adalah lantai keras di Stockfish resmi, dan di bawahnya tidak ada jalan lewat `UCI_Elo`. Yang tersisa dua lapis: bias acak yang disengaja (maksimum di Skill 0) dan kedalaman yang terlalu kecil untuk memperbaiki pilihan. Keduanya digabung di Pemula.
- **Lichess tidak bisa ditiru.** Ini temuan yang paling mudah menyesatkan. Lichess mencapai ~800 Elo dengan pemakaian `Skill Level` negatif, yang hanya didukung Fairy-Stockfish. Di Stockfish resmi nilai negatif ditolak diam-diam — terukur: `Skill -9` menghasilkan tanda skill-nonaktif (~1.000 ms di `go depth 20`, versus ~3.200 ms bila diterima). Menyalin tabel Lichess langsung akan menghasilkan tingkat 1-3 yang **diam-diam bermain dengan kekuatan penuh**.
- **Fairy-Stockfish ditolak, untuk sekarang.** Ia memang menerima `Skill Level` sampai −20 dan `UCI_Elo` sampai 500, dan itu yang Lichess pakai. Tapi menambahnya berarti binary kedua untuk diunduh dan dipin, lisensi kedua di repo, dan jalur verifikasi kedua — demi tingkat bawah yang **labelnya tidak berangka**. Karena tidak ada angka yang dijanjikan, kelemahan Stockfish resmi tidak perlu terukur untuk berguna; ia hanya perlu cukup lemah untuk terasa.
- **Label tanpa angka, bukan angka perkiraan.** `UCI_Elo` dikalibrasi ke **CCRL 40/4 pada 120s+1s**, bukan FIDE dan bukan Lichess, dan fit-nya dibuat terhadap engine yang sudah lama mati. Menampilkan angka berarti menjanjikan sesuatu yang Stockfish sendiri menolak menjamin — dan menyesuaikannya kelak akan terlihat seperti mengubah aturan.
- **Jam simetris, bukan pengecualian.** ADR-0015 sudah punya model lengkap, satu fungsi tutup game, dan aturan "habis = kalah". Memberi mesin pengecualian berarti cabang baru di fungsi itu dan di tick jam — untuk masalah yang tidak pernah muncul, karena mesin berpikir 0,4 ms sampai 3 detik.
- **Jeda 600 ms adalah satu-satunya kostum.** Langkah mesin yang tiba dalam 0,4 ms membuat permainan terasa mekanis, dan di 1+0 pemain bisa kalah tanpa sempat melihat apa yang terjadi. Jeda tetap dipilih di atas jeda sebanding sisa jam karena yang terakhir membuat mesin berpikir lebih lama saat jamnya banyak — kebalikan dari yang diharapkan pemain.
- **Tidak ada ingatan tingkat di server.** Klien Discord sudah mengisi ulang nilai opsi terakhir yang dipakai pengguna untuk perintah yang sama. Penyimpanan per pemain membeli kenyamanan yang sudah gratis dengan satu kolom skema dan satu pertanyaan baru tentang kapan ia berubah.
- **Mesin tidak menyerah dan tidak menerima remis karena itu bukan fitur Stockfish.** Keduanya harus dibangun sendiri di atas eval, dan heuristik ambang yang salah tidak akan ketahuan sampai ada pemain yang mengeluh kehilangan posisi yang masih bisa diselamatkan.
- **Satu baris `players` per tingkat, bukan satu total.** Tingkat yang dihadapi menjadi fakta yang bisa dibaca dari relasi selamanya, tanpa kolom baru di `games` dan tanpa satu schema migration yang harus dibenarkan di kemudian hari.

## Konsekuensi

- **ADR-0009 dibatasi ruang lingkupnya.** "Satu worker FIFO / satu proses Stockfish" berlaku untuk analisa. Proses bermain adalah proses kedua. Ini penunjuk, bukan amendemen: angka, anggaran node, dan rumus ADR-0009 tidak tersentuh.
- **ADR-0007 label "Lawan komputer" menjadi "Lawan komputer — <tingkat>"**. Tiga labelnya yang lain tidak berubah.
- **`CONTEXT.md` istilah Lawan komputer ditulis ulang** — dari "preset 800/1200/1600/2000 Elo" menjadi empat tingkat berlabel tanpa angka, dicapai lewat `/komputer`, dengan Skill Level + batas kedalaman.
- **`CONTEXT.md` istilah yang sengaja dihindari "Elo" perlu dikoreksi** — ia masih menyebut "preset tingkat lawan komputer", yang tidak lagi berangka.
- **Tidak ada kolom baru di skema.** Tingkat tinggal di baris `players`; `games.source='engine'` sudah ditetapkan ADR-0012. Tabel baru tidak dibutuhkan.
- **`backend/tools/verify_backend.py` diperluas dengan probe yang tidak bisa dibohongi.** Assert `UCI_Elo.min == 1320` / `.max == 3190` yang ada sekarang memeriksa **deklarasi** opsi, bukan efeknya — dan Stockfish **menolak opsi di luar rentang tanpa error apa pun**. Probe baru mengukur waktu `go depth 20`: skill aktif ≈ 3,2 s, skill ditolak/dimatikan ≈ 1,0 s. Ditambah probe batas (Skill 25, Skill −1) yang harus tidak mengubah perilaku.
- **Tabel tingkat harus ditulis sebagai enum tertutup, bukan dari input pengguna.** Pilihan opsi Discord datang sebagai string; memetakannya lewat `int()` membuka jalur ke nilai yang ditolak engine secara diam-diam dan bermain dengan kekuatan penuh tanpa ada yang tahu. Presedennya fishnet: level datang sebagai enum delapan varian, bukan sebagai angka bebas.
- **Kekuatan tingkat tidak terukur dan tidak dijanjikan terukur.** Tidak ada angka Elo yang bisa dikutip, tidak ada tabel kalibrasi, dan tidak ada klaim "Pemula ≈ 800". Kalau kelak ada yang mengukur, tabelnya bisa disesuaikan tanpa membongkar apa pun — label dan pasangan (Skill, depth) terpisah.
- **Server Members intent tidak tersentuh.** Ticket [Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27) tetap terbuka untuk alasannya sendiri (`/impor` menerima lampiran berkas).

## Verifikasi

Riset ticket ini mengukur pada Stockfish 19 sungguhan, bukan dari ingatan. Tag `sf_19` = commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d` (2026-09-05).

| Klaim | Bukti |
|---|---|
| `UCI_Elo` diabaikan tanpa `UCI_LimitStrength` | `src/search.cpp:314` meneruskan `0` saat flag mati; terukur `LS=false + Elo=1320 → go depth 20` = 1071 ms vs `LS=true` = 3281 ms |
| `UCI_Elo` meng-override `Skill Level` | `src/search.h:253-273`; terukur Skill 0 dan Skill 20 dengan `Elo 1320` menghasilkan langkah **identik** |
| Lantai 1320 adalah lantai keras | `setoption name UCI_Elo value 800` **ditolak diam-diam** (`src/ucioption.cpp:137-158`); python-chess justru melempar `EngineError` karena membaca `min`/`max` dari handshake |
| `Skill Level` negatif ditolak diam-diam | Terukur `Skill -9/-5/-1` → ~1000 ms di `go depth 20` (tanda skill nonaktif); `0-19` → ~3200 ms |
| `Skill` memaksa `MultiPV ≥ 4` | `src/search.cpp:318-319` |
| Langkah lemah dipilih di `depth = 1 + int(level)` | `src/search.cpp:558-559` |
| Lemah itu **lambat**, bukan cepat | `Skill 0` tanpa batas = ~3,3 s; dengan `go wtime 180000 winc 2` = **30,4 s** |
| Batas kedalaman cepat | `depth 1` ~0,4 ms · `depth 5` ~1-3 ms · `depth 8` ~10,6 ms · `depth 12` ~190 ms |
| Lichess bermain di Fairy-Stockfish | `fishnet/src/queue.rs:557-570` — `EngineFlavor::Official` hanya untuk varian standar **dan** `Work::Analysis`; semua `Work::Move` jatuh ke `MultiVariant` |
| Tabel Lichess tidak bisa disalin | fishnet `src/api.rs` mengirim `skill_level()` = −9/−5/−1/3/7/11/16/20; `Skill Level` resmi Stockfish min **0** |
| `UCI_Elo` berjangkar CCRL, bukan FIDE | Wiki Stockfish: *"calibrated at a time control of 120s+1s and anchored to CCRL 40/4"* |
| Hasil melemah tidak bisa direproduksi | `static PRNG rng(now())` di `src/search.cpp:2099`; terukur 5 ulangan `Skill 0, depth 12` menghasilkan `e1g1, b1c3, b1c3, e1g1, c2c3` |

**Verifikasi milik repo:** `backend/tools/verify_backend.py:229-232` sudah meng-assert `UCI_Elo.min == 1320` dan `.max == 3190` terhadap binary sungguhan. Assert itu benar dan tetap dipakai; ticket ini menambahkan probe efek Skill Level di atasnya.

**Yang tidak terverifikasi dan tidak diklaim:** kekuatan Elo di tiap tingkat. Tidak ada angka yang dikutip, dan tidak ada yang menjanjikan Pemula setara pemain ber-rating tertentu.

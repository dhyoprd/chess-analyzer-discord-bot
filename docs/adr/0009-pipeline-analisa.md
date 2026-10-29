# Pipeline analisa: satu worker FIFO, `go nodes` 1 juta, klasifikasi & akurasi resep Lichess, analisa entitas bersejarah

## Konteks

Ticket [Pipeline analisa Stockfish](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/12) harus menentukan bagaimana sebuah game berjalan dari "selesai" sampai "hasilnya tampil" — pemicu, antrian, anggaran engine, rumus klasifikasi dan akurasi, pelaporan progres, penyimpanan, dan penanganan kasus khusus. Ia memblokir ticket [Mockup: tampilan hasil analisa](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/7), yang memutuskan bagaimana hasil itu ditata.

Ticket ini berdiri di atas empat ADR yang sudah terkunci: [ADR-0002](0002-backend-authoritative-state.md) (backend otoritatif), [ADR-0003](0003-self-hosted-with-paused-clocks.md) (self-hosted, jam dijeda saat bot mati), [ADR-0005](0005-model-data-platform.md) (`analyses` sebagai entitas tersendiri yang bisa dijalankan ulang), dan [ADR-0008](0008-konfigurasi-glicko-2.md) (predikat "dinilai rating" di kode, bukan kolom).

Tiga kendala nyata membentuk keputusan ini:

- **Satu mesin, dipakai bersama.** Analisa berjalan di komputer yang sama dengan bot Discord dan backend. Selama analisa, bot harus tetap menjawab slash command.
- **Analisa mahal dan tidak bisa dibatalkan sebagian.** Menghentikan analisa di tengah berarti kehilangan seluruh pekerjaan.
- **Angka yang diklaim harus bisa dipertanggungjawabkan.** Pemain akan membandingkan akurasi kita dengan Lichess; penyimpangan yang tidak dijelaskan merusak kepercayaan.

## Keputusan

### Bentuk pipeline

- **Satu worker, antrian FIFO.** Satu proses Stockfish dipakai ulang untuk seluruh antrian, sehingga net NNUE (98 MB, tertanam di binary) dimuat sekali, bukan sekali per game. *(Ruang lingkupnya **analisa saja**: [ADR-0018](0018-konfigurasi-lawan-komputer.md) memberi mode lawan komputer **proses engine kedua** yang terpisah, karena pemain manusia tidak boleh menunggu di belakang antrean analisa. Angka, anggaran node, dan rumus di ADR ini tidak tersentuh.)*
- **Engine dimuat saat dibutuhkan, lalu hidup terus** sampai bot mati. Bot tidak memuat engine saat boot, jadi Stockfish yang rusak tidak pernah menghalangi bot untuk start dan melayani permainan.
- **Analisa berjalan di thread khusus di dalam proses backend**, dengan antrian asyncio. Stockfish tidak pernah menyentuh event loop, sehingga bot tetap responsif.
- **Pemicu: sinyal setelah commit.** Jalur tulis yang menyelesaikan game menaruh `game_id` ke antrian **setelah** transaksinya commit — bukan di dalamnya. Ini wajib: [ADR-0008](0008-konfigurasi-glicko-2.md) menuntut hasil game dan entri rating ditulis dalam satu transaksi, dan analisa yang memakan puluhan detik tidak boleh memperpanjang transaksi itu.
- **Antrian di memori, tapi isinya direkonstruksi dari database.** Saat start, backend memindai maksimum **20 game selesai terbaru** yang belum punya analisa selesai, urut dari yang terbaru. Antrian jadi turunan dari database, bukan state yang harus dijaga — konsisten dengan ADR-0002.

### Anggaran engine

- **`go nodes 1.000.000` per posisi, bukan `go depth`.** Depth yang dilaporkan Stockfish hanyalah estimasi, sehingga biaya per posisi tidak bisa dijanjikan; dengan `go nodes`, biaya bisa dijanjikan. **Lichess memakai angka yang sama** — `Origin.manualRequest = 1_000_000 nodes/move` — dan tidak pernah mengirim depth sama sekali.
- **`Threads = 4`, `Hash = 128 MB`.** Sengaja bukan "core dikurangi satu-dua": satu worker berjalan di mesin yang sama dengan bot, dan bot harus tetap menjawab selama analisa.
- **MultiPV 1.** Klasifikasi hanya butuh eval sebelum dan sesudah; satu kandidat cukup, dan biaya tidak dikalikan.
- **Timeout 60 detik per panggilan engine**, longgar dengan sengaja: pada 1 juta node posisi rumit bisa melewati default python-chess (10 detik), sementara satu panggilan yang menggantung membekukan seluruh antrian.
- **Seluruh posisi dianalisa** — N+1 posisi untuk game N langkah. Satu posisi melayani dua langkah sekaligus (ia "sesudah" bagi langkah sebelumnya dan "sebelum" bagi langkah berikutnya), jadi ini jalur paling efisien yang mengklasifikasi **kedua** pemain secara penuh.
- **Chess960: opsi `UCI_Chess960` disetel per game** sesuai varian, dan disetel ulang setiap kali varian berganti. Satu engine yang dipakai ulang wajib melakukan ini — opsi menempel pada proses, dan salah setel membuat eval Chess960 salah secara senyap.

### Klasifikasi dan akurasi

Semua rumus mengikuti Lichess, diverifikasi dari sumber primernya.

- **Win-chance** dari centipawn: `wc(cp) = 2/(1 + exp(-0.00368208 × cp)) − 1`, pada skala −1..+1, dengan **cp di-clamp ke ±1000 lebih dulu**.
- **Klasifikasi** dari selisih win-chance **dari sudut pandang pelangkah**: ≥ 0,3 Blunder; ≥ 0,2 Mistake; ≥ 0,1 Inaccuracy.
- **⚠️ Perangkap POV — sumber bug paling berbahaya di seluruh pipeline ini.** Lichess menghitung `delta = (curr − prev)` lalu membaliknya memakai `info.color`, dan `info.color` adalah warna pemain **yang akan melangkah di posisi `info`** — yaitu **lawan** dari pelangkah yang baru bergerak. Akibatnya rumus efektifnya adalah `delta = prev − curr` untuk pelangkah putih. Delta positif berarti win-chance **pelangkah turun**, yaitu langkah yang buruk. Salah arah di sini membalik seluruh klasifikasi untuk satu warna, dan hasilnya tetap terlihat masuk akal sehingga bug-nya senyap. Sudah diuji: eval 0cp → −350cp adalah **Blunder** bila pelangkahnya putih, dan **tanpa penilaian** bila pelangkahnya hitam.
- **Posisi sudah kalah/menang telak: tanpa filter apa pun.** Netralisasinya bawaan — sigmoid jenuh, dan di luar ±1000cp semua eval menjadi angka identik, sehingga selisihnya **tepat nol**. Terukur: −2000cp → −3000cp menghasilkan delta 0,000000; −1500cp → −2500cp juga 0,000000; dan −800cp → −1800cp hanya 0,0508. Semuanya jauh di bawah ambang terkecil 0,1, jadi kehilangan 10 pion di posisi sudah kalah tidak pernah dicap blunder.
- **Transisi skakmat memakai tangga tersendiri**, karena selisih win-chance saja tidak menangkapnya:
  - `MateCreated` (dari cp menjadi mate untuk lawan) dinilai dari eval **sebelumnya**: di bawah −999 Inaccuracy, di bawah −700 Mistake, selain itu Blunder.
  - `MateLost` (dari mate untuk kita menjadi cp) dinilai dari eval **sesudahnya**: di atas 999 Inaccuracy, di atas 700 Mistake, selain itu Blunder.
  - Mate yang tertunda (mate tetap mate) **tanpa penilaian**.
  - Semua eval di sini dari **sudut pandang pelangkah**.
- **Skakmat runtuh ke satu nilai**: mate selalu menjadi ±1000cp, yaitu win-chance **97,545% / 2,455%**. Jarak mate diabaikan — mate dalam 1 dan mate dalam 30 bernilai sama.
- **Akurasi per langkah**: bila eval tidak turun → `100`. Bila turun: `raw = 103.1668100711649 × exp(-0.04354415386753951 × winDiff) − 3.166924740191411`, lalu `clamp(raw + 1, 0, 100)`. `winDiff` pada skala **0–100**, dan eval sudah dibalik ke sudut pandang pelangkah.
- **Akurasi game** = rata-rata dari **(weighted mean berbobot volatilitas)** dan **(harmonic mean)**:
  - Ukuran jendela = `clamp(n/10, 2, 8)` dengan `n` = jumlah langkah.
  - Bobot = **deviasi standar populasi** win% di dalam jendela bergeser (langkah 1), di-clamp ke **[0,5, 12]**.
  - Harmonic mean menahan tiap nilai di `max(1, v)`.
  - Nilai awal agregasi memakai **konstanta 15cp** milik Lichess, bukan hasil analisa posisi awal.
- **Nilai "sebelum langkah pertama" = konstanta 15cp**, tanpa menganalisa posisi awal. Setia ke Lichess, deterministik, dan menghemat satu panggilan engine. (Engine kita menilai posisi awal +24cp, jadi ini memang pilihan, bukan kebetulan.)
- **Minimum 2 ply, tanpa ambang eksplisit.** Akurasi hanya bisa dihitung bila **kedua** warna punya minimal satu langkah — konsekuensi alami dari agregasi per warna, bukan penjaga khusus. Game 1 ply tidak punya akurasi; game 2 ply punya (~100% keduanya).

### Pelaporan

- **Pesan progres di-edit, pesan hasil dikirim baru.** Fakta terverifikasi: mengedit pesan **tidak** memicu notifikasi; hanya pesan baru ber-mention yang memicu ping. Karena itu progres harus sunyi dan hasil harus menyala.
- **Progres di-edit tiap ~10% kemajuan**, dalam satuan **langkah** ("12/40 langkah"), dan menyebut **posisi dalam antrian** bila ada yang menunggu.
- **Pesan progres dihapus setelah selesai**, digantikan pesan hasil. Satu pesan per game.
- **Pesan hasil dikirim ke channel game** (`games.channel_id` — kolom yang ADR-0007 memang pertahankan untuk menempatkan pesan bot).
- **Mention hanya pihak yang punya `discord_id`**; lawan komputer dan pemain bayangan disebut namanya saja. Game tanpa pemenang (remis, ditinggalkan) ditampilkan normal, hanya tanpa baris pemenang.
- **Kegagalan dikirim ke channel**, bukan hanya ke log — konsisten dengan prinsip ADR-0008 bahwa kegagalan dicatat keras, bukan disembunyikan.
- **Format angka**: koma desimal (bahasa bot Bahasa Indonesia), akurasi 1 desimal ("87,4%"), skakmat sebagai "#3". Rating tetap bilangan bulat sesuai ADR-0008.

- **Pesan hasil membawa thumbnail papan.** Satu langkah render berjalan tepat sebelum pesan disusun, di dalam worker yang sama. *(Diputuskan [ADR-0017](0017-render-papan-thumbnail.md): `chess.svg.board()` + `resvg-py`, posisi akhir dengan sorotan langkah terakhir, 320×320 px, dilampirkan lewat `attachment://`. Terukur **14 ms**, jadi tidak menahan antrean FIFO. Gagal render **tidak** menggagalkan pesan — thumbnail dilepas, kegagalan dicatat keras.)*

### Penyimpanan

- **`analyses` adalah entitas bersejarah, bukan cache.** Analisa ulang menulis baris **baru**; analisa lama tidak pernah ditimpa. Yang ditampilkan adalah **analisa selesai terbaru**.
- **Dedup lewat kueri, bukan kolom.** "Sudah dianalisa" berarti "sudah ada baris `analyses` berstatus selesai" — persis pola yang ADR-0008 pilih untuk predikat rating. Tidak ada kolom penanda di `games`.
- **Kegagalan dicatat sebagai baris `analyses` berstatus gagal**, **satu baris per game** dengan kolom jumlah percobaan yang dinaikkan. Pemindaian saat start mencoba ulang maksimum **3 kali**, lalu berhenti dan menunggu analisa ulang manual. Ini mencegah game bermasalah dicoba ulang tanpa henti tanpa kehilangan jejaknya.
- **Satu transaksi di akhir.** Baris `analyses` dan seluruh `analysis_moves` ditulis setelah semua posisi selesai. Bot yang mati di tengah tidak meninggalkan baris apa pun, sehingga pemindaian saat start otomatis mengulang game itu — pemulihan tanpa logika pemulihan.
- **Kegagalan satu posisi membatalkan seluruh analisa.** Tidak ada `analysis_moves` berlubang — akurasi yang dihitung dari rangkaian tidak lengkap akan terlihat wajar tapi salah.
- **Apa yang dicatat**: anggaran node, versi engine, jumlah thread, dan Hash — cukup untuk menjawab "mengapa angka ini berbeda dari analisa kemarin". Semua analisa disimpan selamanya.
- **`analysis_moves`** menyimpan, per langkah: eval **sebelum dan sesudah** (keduanya **sudut pandang putih**), win-chance kedua sisi, klasifikasi, dan langkah terbaik. Menunjuk langkah lewat **nomor ply** dalam game. Langkah terbaik disimpan dalam **UCI** dan dikonversi ke SAN saat ditampilkan.
- **Hitungan langkah diturunkan** dari klasifikasi saat dibutuhkan; **akurasi disimpan** sebagai kolom di `analyses`. Akurasi adalah angka tunggal per pemain per game yang selalu dibutuhkan tampilan, sedangkan hitungan langkah murah diturunkan.
- **Analisa ulang manual** dipicu lewat **satu perintah bot**, boleh siapa pun, dibatasi **1 per pemain per 10 menit**.

### Cakupan

- **Semua game selesai dianalisa** — termasuk lawan komputer, game impor, dan game ditinggalkan. Yang dikecualikan hanya game tanpa langkah sama sekali (dilewati, tidak dicatat apa pun) dan game yang belum selesai.
- **Alur impor PGN diserahkan ke ticket [Alur klaim akun & game impor](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/15).** Pipeline ini hanya menerima game yang sudah ada di tabel `games`.
- **Analisa tidak dipakai untuk eval langsung saat bermain.** Engine hanya melayani analisa pasca-game.
- **Analisa ulang tidak dipicu otomatis** saat game dibuka di Activity.

## Alasan

- **`go nodes` karena biaya harus bisa dijanjikan.** Riset #3 menandai sendiri estimasi waktunya sebagai "tidak ada benchmark resmi". Pengukuran langsung di mesin ini menunjukkan estimasi itu **jauh terlalu pesimis**: satu game 40 langkah (81 posisi) selesai dalam **~20-40 detik**, dan 8 game turnamen **~3-5 menit** — bukan 1-5 menit per game seperti perkiraan awal. Rentangnya lebar karena mesin ini juga menjalankan hal lain; angka persisnya bergantung beban saat itu. Yang penting: biayanya **terukur dan bisa dijanjikan**, sehingga `go depth` yang tidak bisa dijanjikan tidak punya alasan dipakai.
- **Angka 1 juta bukan tebakan.** Lichess memakai `Origin.manualRequest = 1_000_000 nodes/move` untuk permintaan analisa game, dengan MultiPV 1 dan tanpa depth. Memakai angka yang sama membuat perbandingan dengan Lichess masuk akal sejak awal.
- **4 thread, bukan core dikurangi satu-dua.** Saran riset itu mengasumsikan engine adalah satu-satunya beban. Di sini bot Discord dan backend hidup di mesin yang sama, dan keduanya harus tetap responsif justru saat pemain sedang menunggu hasil analisa.
- **Tanpa filter posisi sudah-kalah.** Sigmoid sudah menetralkannya secara matematis. Menambah filter eksplisit berarti menduplikasi perilaku yang sudah ada, dan justru mematikan klasifikasi di posisi menang-telak yang masih bisa dibalikkan lawan.
- **Tangga mate karena selisih win-chance punya lubang nyata.** Terukur: dari mate paksa (97,545%) menjadi +9,0 pion (96,49%) menghasilkan selisih hanya **0,0211** — jauh di bawah ambang 0,1, sehingga pembuangan skakmat paksa lolos tanpa klasifikasi apa pun. Padahal itu kesalahan paling fatal yang mungkin terjadi.
- **Konstanta 15cp untuk posisi awal.** Lichess memakainya, dan memakainya berarti langkah pertama tidak bisa menjadi blunder palsu akibat selisih kecil antara eval posisi awal dan eval setelah langkah pertama.
- **Satu worker karena mesin dipakai bersama.** Dua worker berarti dua proses engine, dua Hash, dan perebutan core dengan bot. Untuk satu guild, antrian ~3-5 menit saat turnamen penuh adalah biaya yang wajar demi bot yang tetap responsif.
- **Pesan progres dihapus** supaya channel bersih: satu pesan per game. Menyisakan pesan progres berarti setiap game meninggalkan dua pesan, dan yang pertama tidak berguna lagi.
- **Satu transaksi di akhir, bukan penulisan bertahap.** Ini menghapus seluruh kelas bug: tidak ada baris "sedang berjalan" yang bisa menjadi bangkai, dan tidak ada logika pemulihan yang harus membedakan bot yang mati dari analisa yang benar-benar aktif.
- **Baris gagal dengan jumlah percobaan.** Tanpa ini, pemindaian saat start tidak bisa membedakan game yang belum dicoba dari yang sudah gagal, sehingga game bermasalah dicoba ulang di setiap restart selamanya — dan dengan satu worker, itu menunda analisa game yang sehat.
- **Akurasi disimpan, hitungan langkah diturunkan.** Keduanya berbeda sifat: akurasi adalah hasil agregasi matematis atas seluruh selisih win-chance (bukan turunan dari klasifikasi), dan selalu dibutuhkan tampilan; hitungan langkah hanyalah penjumlahan baris.

## Konsekuensi

- **`analyses` dan `analysis_moves` mendapat kolom yang belum ada di ADR-0005** — status (selesai/gagal), jumlah percobaan, akurasi putih & hitam, anggaran node, versi engine, thread, Hash, waktu mulai/selesai; serta per langkah: nomor ply, eval sebelum & sesudah, win-chance kedua sisi, klasifikasi, dan langkah terbaik (UCI). Skema harus diperluas saat implementasi.
- **`analyses` + `analysis_moves` menjadi tabel terbesar**, dan menyimpan semua analisa berarti ia tumbuh oleh analisa ulang. ADR-0005 sudah memperingatkan ini; kini peringatannya berlaku penuh. Untuk satu guild dengan pemakaian wajar, SQLite menangani ini tanpa kesulitan.
- **Hasil analisa TIDAK deterministik sempurna antar-analisa.** Terukur dengan `Threads = 4`: eval bervariasi ~±5cp antar-run, karena Stockfish memakai Lazy SMP. Variasi itu ~9% dari ambang klasifikasi terkecil (0,1), jadi pembalikan klasifikasi jarang — tapi bukan mustahil, dan hampir selalu terjadi di posisi yang memang mendekati ambang. **Yang bisa direproduksi adalah BIAYA-nya (jumlah node), bukan hasilnya.** Untuk hasil yang identik persis, `Threads` harus 1 (terukur ~3x lebih lambat).
- **Analisa ulang bisa menghasilkan angka berbeda** dari analisa sebelumnya pada game yang sama, bahkan dengan engine yang sama. Ini bukan bug, dan tampilan harus menyebut versi engine yang dipakai agar perbedaan antar-analisa bisa dijelaskan.
- **`STOCKFISH_DEPTH` di `.env.example` diganti `STOCKFISH_NODES`**, dan `STOCKFISH_THREADS` turun dari 6 ke 4, `STOCKFISH_HASH_MB` dari 256 ke 128. `STOCKFISH_TIMEOUT_SECONDS` ditambahkan.
- **Kode klasifikasi dan akurasi menjadi milik kita untuk dirawat**, dengan tes regresi terhadap nilai emas dari unit test Lichess sendiri: game 20 langkah dengan langkah terakhir −900cp → putih ~50, hitam ~100; `List.fill(50)(List(-135,15)).flatten` → keduanya ~54; `List.fill(50)(List(-435,15)).flatten` → keduanya ~20.
- **Antrian turnamen bisa menumpuk** saat banyak game selesai bersamaan. Terukur ~3-5 menit untuk 8 game pada 1 juta node, bergantung beban mesin. Pesan progres menyebut posisi antrian supaya pemain tahu itu normal.
- **Pemindaian start dibatasi 20 game terbaru.** Game lama yang belum dianalisa tidak akan pernah dianalisa otomatis — hanya lewat perintah manual. Ini disengaja: game yang baru dimainkan pemain adalah yang paling ingin dilihat.
- **Bot tetap hidup walau Stockfish rusak.** Kegagalan memuat engine dicatat sebagai baris `analyses` gagal, dan pemindaian berikutnya mencoba lagi sampai 3 kali. Konsekuensinya, kerusakan engine bisa tidak terlihat dari luar selain lewat pesan gagal di channel.
- **`CONTEXT.md` diperbarui**: definisi **Langkah** dikoreksi (eval dan klasifikasi bukan milik langkah, melainkan milik analisa — sebelumnya bertabrakan dengan ADR-0005), istilah **Posisi** ditambahkan, dan **Analisa** / **Analisa ulang** diberi isi yang tepat.
- **Alur impor PGN tetap belum ditentukan** dan harus diputuskan ticket #15 sebelum fitur "analisa game eksternal" di Destination bisa berfungsi. Pipeline ini sudah siap menerimanya.
- **`engine/stockfish.exe` tidak ada di repo** (gitignored, 98 MB). Catatan lingkungan di peta yang menyebutnya "terpasang" sudah tidak berlaku; `engine/README.md` memuat perintah unduh yang benar. Analisa tidak bisa dijalankan sebelum binary diunduh.

## Verifikasi

Dua skrip di `backend/tools/` membuktikan klaim di ADR ini, dan harus dijalankan ulang bila rumus atau anggaran engine diubah:

| Skrip | Membuktikan |
|---|---|
| `verify_analysis_formulas.py` | Rumus klasifikasi & akurasi cocok dengan **10/10 nilai emas dari unit test Lichess sendiri** (`AccuracyPercentTest.scala`) — termasuk kasus 1 ply tanpa akurasi, dan nilai agregat 54/20. Juga mencetak bukti mengapa tangga mate diperlukan (selisih 0,0211 < 0,1) dan mengapa posisi sudah-kalah tidak butuh filter (delta 0,000000). |
| `bench_analysis_nodes.py` | Anggaran node vs waktu nyata, dan mengapa `go nodes` dipilih: 1 juta node mencapai depth 19-20 di middlegame pada ~0,2-0,5 detik/posisi. |

Jalankan dengan `python -I` dari akar repo, mis.:

```sh
backend/.venv/Scripts/python.exe -I backend/tools/verify_analysis_formulas.py
backend/.venv/Scripts/python.exe -I backend/tools/bench_analysis_nodes.py engine/stockfish.exe 4 128
```

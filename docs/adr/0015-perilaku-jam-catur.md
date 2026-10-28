# Jam catur: Fischer, diukur terhadap satu jam platform, baru berjalan di langkah pertama

## Konteks

Ticket [Perilaku jam catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/21) menutup lubang terbesar yang tersisa di peta. Jam catur adalah satu-satunya bagian platform yang **tidak bisa dibeli dari pustaka**: [ticket #4](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/4) memverifikasi `python-chess` tidak menyediakannya sama sekali. Destination peta menyebutnya sebagai fitur Activity, tapi tidak ada ADR yang memilikinya — yang ada hanya serpihan keputusan di enam ADR lain.

Serpihan itu, kalau disusun, hampir saling bertabrakan:

- **[ADR-0003](0003-self-hosted-with-paused-clocks.md)** mewajibkan jam **dijeda saat bot mati** dan **tetap berjalan saat Activity ditutup**, lewat "timestamp monotonic dan sisa waktu tiap pemain". Ia menyebut restart, mati listrik, dan **tidur** sebagai cara komputer pribadi mati.
- **[ADR-0002](0002-backend-authoritative-state.md)** menjadikan backend satu-satunya sumber kebenaran jam: *"Waktu yang dilaporkan browser tidak dapat dijadikan dasar flag-fall."*
- **[ADR-0005](0005-model-data-platform.md)** menyimpan format sebagai `base_seconds` + `increment_seconds` (bentuk Fischer) dan menyebut nama `game_clock_events` tanpa memberi kolomnya.
- **[ADR-0006](0006-alur-turnamen-knockout.md)** mengunci armageddon: putih lebih banyak waktu, hitam 80%, tidak dinilai rating — tanpa menyebut angka dasarnya.
- **[ADR-0008](0008-konfigurasi-glicko-2.md)** menilai rating game yang **kehabisan waktu**, dan sudah menetapkan bahwa hasil game + entri rating ditulis dalam **satu transaksi**.
- **[ADR-0013](0013-jendela-pendaftaran-turnamen.md)** menamai **tick platform** dan mengunci kontraknya, tapi **sengaja menyerahkan interval dan presisinya ke ticket ini**, karena jam catur menuntut ketelitian jauh lebih ketat.
- **[ADR-0014](0014-alur-game-santai.md)** menetapkan **jam baru berjalan di langkah pertama**, sehingga keadaan "game ada, jam belum berjalan" adalah keadaan sah yang wajib ditangani model jam.

Riset menambahkan tiga fakta yang mengubah jawaban sebelum ditanyakan:

- **`time.monotonic()` di Windows adalah `QueryPerformanceCounter`**, dan Microsoft mendokumentasikan bahwa ia **tetap maju selama sleep/hibernate** — *"including the time when the machine was in a sleep state such as standby, hibernate, or connected standby"*. Jangkar monotonic mentah karena itu akan **membebankan tidur PC ke pemain yang sedang berpikir** — persis yang dilarang ADR-0003.
- **Lichess sama sekali tidak menjeda jam saat server mati.** Ia menyimpan timestamp absolut dan menghitung downtime sebagai waktu berpikir; satu-satunya pengaman adalah membatalkan game yang terakhir dimainkan sebelum JVM boot bila uptime < 120 detik. Kebutuhan kita berbeda dan ADR-0003 sudah memilih sadar-sadar: **kita menjeda**. Penyimpangan ini dicatat, bukan dibiarkan terlihat seperti kelalaian.
- **Lichess memotong elapsed dulu, baru menambah increment**, dalam satu langkah. Mengikuti urutan sebaliknya memberi pemain yang kehabisan waktu satu increment gratis yang tidak pernah ia dapatkan.

## Keputusan

### Satu jam untuk seluruh platform

- **Tick platform ADR-0013 adalah jam platform itu sendiri.** Ia memajukan **satu penghitung bot-hidup**, dan jam catur, jendela pendaftaran, serta "Ditinggalkan" semuanya mengukur terhadap angka yang sama.
- Tick berjalan **tiap 1 detik**. Delta diambil dari waktu nyata sejak tick terakhir, di-clamp **≥ 0** dan **≤ 2× interval** (kontrak ADR-0013, kini dengan angka).
- Karena penghitung inilah yang dijadikan jangkar, **tidur, hibernate, dan proses yang terhenti tidak pernah membebani pemain**: lompatan apa pun terpotong di 2 detik, dan itu selalu ke arah yang menguntungkan pemain.
- Penghitung disimpan sebagai **satu baris total** di `bot_uptime` dan **di-flush tiap 60 detik**. Mati listrik karena itu mengampuni paling banyak 60 detik waktu berpikir.
- **Downtime tidak dikodekan sama sekali.** Ia tidak perlu dihitung, dikurangi, atau dikecualikan — penghitungnya tidak maju, jadi ia tidak pernah masuk hitungan. Inilah bentuk konkret "timestamp monotonic dan hitung ulang saat start" yang dituntut ADR-0003.

### Model jam

- **Fischer / increment**: waktu dasar ditambah increment tiap langkah. Format `1+0` (increment nol) sah dan tidak butuh cabang.
- **Sentidetik**, bilangan bulat, untuk semua sisa waktu. Cukup halus agar galat tidak menumpuk, tetap bulat sehingga tidak ada pembulatan floating-point yang merayap.
- Urutan per langkah **dikunci mengikuti Lichess**: `sisa ← sisa − elapsed + increment`, di mana `elapsed` sudah dikurangi tenggang jaringan. **Tidak ada increment bila pelangkah sudah kehabisan** — ia harus kalah, bukan diselamatkan oleh increment-nya sendiri.
- Yang disimpan hanya **sisa waktu saat langkah di-commit** ditambah **nilai jam platform saat itu**. Sisa hidup dihitung saat dibaca. Tidak ada tulisan ke database per detik per game.

### Empat kolom jam di `games`

- **`white_centis`**, **`black_centis`** — sisa waktu tiap pemain dalam sentidetik, pada saat `clock_committed_at`.
- **`clock_committed_at`** — nilai jam platform saat sisa di atas dicatat.
- **`clock_started`** (boolean, NOT NULL default false) — false sampai ply 1 di-commit.
- **`clock_started` bukan hiasan.** Ia satu-satunya cara membedakan "jam belum pernah berjalan" dari "jam berjalan dengan 300 detik tersisa". Tanpa itu, pemulihan setelah restart akan menyalakan jam putih yang seharusnya masih bebas.

### Preset format jam

Enam preset, dipetakan ke kategori kecepatan dengan **rumus Lichess apa adanya** — `estimateTotalSeconds = base_seconds + 40 × increment_seconds`, ambang bullet 30-179, blitz 180-479, rapid 480-1499:

| Preset | Nama | Estimasi | Kategori |
|---|---|---|---|
| 1+0 | — | 40 s | bullet |
| 3+0 | — | 180 s | blitz |
| 3+2 | — | 260 s | blitz |
| **5+3** | **"standar"** | 320 s | blitz |
| 10+0 | — | 600 s | rapid |
| 10+5 | — | 800 s | rapid |

- **"Standar" = 5+3**, dan itulah default `/challenge` yang diperintahkan ADR-0014. 5+3 adalah default quick-pairing Lichess, jadi tidak ada pemain yang terkejut.
- Pemetaan dilakukan dengan **rumus, bukan tabel**, supaya preset baru tidak butuh keputusan kategori tersendiri.
- Tidak ada preset yang jatuh ke classical atau ultraBullet. Kedua keranjang itu tetap ada di rumus karena `/stats` dan klasemen memakai kategori, tapi **tidak ada preset yang mengisinya**.
- Chess960 memakai rumus yang sama tanpa pengali — terverifikasi di `scalachess`, di mana `Speed` hanya menerima `Clock.Config`.

### Kapan jam berjalan

- **Jam belum berjalan saat game dibuat.** Ia mulai saat **ply 1 di-commit** (`clock_started` menjadi true, `clock_committed_at` diisi, dan giliran berpindah ke hitam).
- **Putih bebas waktu untuk langkah pertamanya.** Ini bacaan harfiah ADR-0014 dan konsekuensi yang sudah dipilihnya: jam mulai di langkah pertama berarti jam putih baru berjalan ketika putih sudah melangkah. Asimetrinya nyata tapi kecil dibandingkan alternatifnya, yang menghukum penerima challenge yang menekan Terima lalu menutup Discord.
- **Tidak ada konstanta baru untuk jendela itu.** Penjaganya "Ditinggalkan" 24 jam waktu bot hidup yang sudah ada.
- **Game yang tak pernah dilangkahi** berakhir `result='none'`, `end_reason='abandoned'`, tanpa pemenang, **tanpa entri rating** — seragam dengan game ditinggalkan setelah berlangkah.
- Jam **tetap berjalan saat Activity ditutup** dan **berhenti saat bot mati**, keduanya karena jamnya adalah penghitung bot-hidup itu sendiri, bukan waktu nyata.

### Berakhirnya game

- **Satu fungsi tutup game, dengan sebab sebagai argumen.** Skakmat, menyerah, kehabisan waktu, ditinggalkan, dan remis semuanya menulis bentuk hasil yang sama. Mengulangi pola "satu jalur kode, dua pemicu" milik ADR-0013 bukan formalitas: proyek ini sudah empat kali kena bug dari dua jalur yang seharusnya menghitung hal yang sama (#7), dan akhir game adalah tempat paling mahal untuk mengulanginya.
- **Kehabisan waktu = kalah**, **kecuali lawan tidak punya bahan skakmat** → **remis**. Mengikuti Lichess, dan `python-chess` menyediakannya lewat `is_insufficient_material()`. Tanpa cabang ini, raja telanjang bisa "menang" melawan K+B.
- **Tenggang jaringan 500 ms tetap.** Langkah yang diterima dalam 500 ms setelah jam menyentuh nol tetap sah. Angka ini **tidak berasal dari klien** — Lichess menurunkan kompensasinya dari lag yang dilaporkan klien, jalur yang bisa dimanipulasi. Angka tetap tidak bisa dimanipulasi, dan 500 ms menutup RTT rumah tangga tanpa memberi ruang curang yang berarti.
- **Langkah yang tiba setelah game selesai ditolak**, dan hasil tidak pernah diulang. Klien menyegarkan state dan menampilkan hasil. Hasil yang sudah diumumkan dan sudah masuk `rating_ledger` tidak boleh bisa ditarik kembali.
- **Pengumuman hasil lewat pesan baru ber-mention kedua pemain, segera** — terpisah dari pesan analisa ADR-0009 yang datang ~20-40 detik kemudian dan bisa gagal tiga kali. Hasil game tidak boleh bergantung pada pipeline analisa.

### Armageddon

- **Waktu tetap 5 menit putih / 4 menit hitam, tanpa increment.** Angkanya lepas dari format game-game sebelumnya, sehingga tidak ada pertanyaan "format yang mana" pada pertandingan yang memuat tiga game berbeda format.
- **Boleh berakhir dengan cara apa pun.** Skakmat dan menyerah dibaca apa adanya dari papan; bahan tak cukup → **hitam menang**, karena itu satu-satunya remis yang tersisa. Aturan "remis = hitam menang" adalah **pembaca hasil akhir**, bukan larangan game berakhir dengan cara lain.
- Ini menjaga `games` = kebenaran papan (ADR-0006) sementara `tournament_matches.winner_id` tetap memutuskan siapa maju.
- Armageddon **tidak** dinilai rating (ADR-0006, sudah terkunci).

### Format jam turnamen

- **Seluruh game turnamen memakai preset "standar" (5+3)**, tanpa pilihan dan tanpa kolom baru. Armageddon 5/4 berdiri sendiri.
- Alasan: satu pertandingan sudah memuat hingga tiga game, dan dua pertandingan di ronde yang sama harus bisa dibandingkan. Menu `/turnamen` tidak bertambah satu keputusan yang tidak diminta siapa pun.

### `end_reason` bernama

ADR-0005 menyebut kolom ini tanpa memberi nilainya. Kosakatanya kini dikunci:

| Nilai | Arti |
|---|---|
| `checkmate` | skakmat |
| `resign` | menyerah |
| `timeout` | jam habis |
| `abandoned` | ditinggalkan 24 jam waktu bot hidup |
| `insufficient_material` | bahan tak cukup untuk skakmat |
| `stalemate`, `fifty_move`, `threefold`, `agreed` | lewat **`draw_type`**, bukan `end_reason` |

`result` tetap empat nilai ADR-0012 (`white` / `black` / `draw` / `none`). **`result` menjawab "siapa", `end_reason` menjawab "kenapa".**

### Tampilan

- **Hitung mundur hanya di Activity.** Backend mengirim sisa waktu + waktu server tiap siaran state; klien menghitung di antaranya dan **tidak pernah** menjadi otoritas.
- **Discord tidak menampilkan hitung mundur sama sekali.** Edit tidak memicu notifikasi (fakta #10), jadi tick-edit hanya membeli rate limit. Jam muncul hanya di pesan hasil: "hitam kehabisan waktu — putih menang".

## Alasan

- **Satu jam, bukan tiga.** "Waktu bot hidup" sudah didefinisikan `CONTEXT.md` sebagai satu penghitung yang maju selama proses bot berjalan. Menjadikannya jangkar jam catur sekaligus menutup lubang sleep tanpa menambah mekanisme: lompatan yang sudah di-clamp kontrak ADR-0013 kini juga melindungi jam catur.
- **Clamp, bukan pendeteksi sleep.** Perbandingan delta monotonic vs delta waktu nyata akan menjadi jalur pemeriksa kedua yang bisa keliru sendiri, dan hasilnya tetap harus dipotong di angka yang sama. Clamp yang sudah ada memberi jawaban yang sama dengan nol kode tambahan.
- **Sentidetik, bukan detik.** Galat pembulatan 1 detik per langkah pada game 60 langkah menggeser flag beberapa detik dari yang seharusnya, dan itu terlihat sebagai bug jam yang tidak bisa dijelaskan.
- **Potong dulu, increment sesudah.** Urutan sebaliknya memberi pelangkah yang kehabisan waktu satu increment gratis, sehingga ada langkah yang bisa dimainkan tanpa waktu untuk memikirkannya.
- **Tenggang tetap, bukan lag dari klien.** ADR-0002 menjadikan backend satu-satunya sumber kebenaran jam; menerima angka waktu dari klien membatalkan alasan itu. Lichess boleh memakai lag yang dilaporkan klien karena ia menanggung risikonya di skala yang berbeda dari satu server teman.
- **Jam mulai di langkah pertama adalah harga challenge yang adil.** Alternatifnya — jam putih mulai saat Terima atau saat papan dibuka — menghukum penerima yang menutup Discord, dan menambah kejadian (koneksi klien) yang menentukan jam. Satu-satunya pemain yang bisa menyalahgunakannya adalah putih yang sengaja berdiam, dan itu sudah dinetralkan "Ditinggalkan" 24 jam.
- **Enam preset, 5+3 standar.** Menutup bullet sampai rapid tanpa membuat menu `/challenge` panjang. Format classical (hingga ~6 jam) hampir tidak terpakai di satu server berisi teman, dan menambahkannya berarti menambah kategori yang tidak akan pernah terisi.
- **Rumus, bukan tabel kategori.** Tabel butuh diperbarui setiap kali preset ditambah, dan tidak ada yang akan ingat. Rumusnya satu baris dan sama dengan sumbernya.
- **Satu fungsi tutup.** Lima jalan menuju satu hasil adalah tempat di mana jalur yang lupa menulis `result` membuat game hilang dari rekor — dan ADR-0012 sengaja membuat `source` tanpa default supaya kelalaian semacam itu gagal keras, bukan diam-diam.
- **Langkah setelah selesai ditolak.** Membalik hasil yang sudah diumumkan membuat `rating_ledger` dan pesan Discord berselisih, dan menuntut jalur koreksi rating yang belum ada dan tidak akan pernah cukup diuji.
- **Pesan hasil terpisah dari pesan analisa.** Analisa bisa gagal tiga kali (ADR-0009) dan selalu lebih lambat; pemain yang ingin tahu siapa menang tidak boleh menunggu Stockfish.
- **Armageddon 5/4 tetap.** Menurunkan waktu dari format game pertama berarti memilih salah satu dari tiga format secara arbitrer, dan menghubungkan jam penentu ke game yang sudah selesai tanpa hubungan yang bermakna.
- **`end_reason` dipisah dari `draw_type`.** ADR-0005 sudah memisahkannya; menggabungkan semua sebab remis ke `end_reason` akan membuat kolom itu menjawab dua pertanyaan sekaligus dan `/stats` kehilangan kemampuan menjumlah "kenapa game berakhir" tanpa memilah remis.

## Konsekuensi

- **ADR-0003 mendapatkan bentuk konkretnya.** "Timestamp monotonic dan hitung ulang saat start" dilaksanakan sebagai **satu penghitung bot-hidup**, bukan timestamp per pemain. Penyimpangan dari Lichess — yang menghitung downtime sebagai waktu berpikir — dicatat sebagai **pilihan sadar**, bukan kelalaian.
- **ADR-0005 diamendemen**: tabel **`game_clock_events` dibuang**. Dengan jam platform, isinya sepenuhnya turunan dari data langkah + sisa terakhir, dan tidak ada kejadian non-langkah yang perlu dicatat — jeda saat bot mati justru ditandai oleh **ketiadaan** baris. `games` mendapat empat kolom jam di atas; `end_reason` mendapat kosakatanya.
- **ADR-0013 dilengkapi**, tidak diubah: kontrak tick tetap, dan **interval 1 detik + presisi** kini terisi. Kontraknya bertambah satu kalimat — penghitung yang ia majukan **adalah** jam platform.
- **ADR-0006 dilengkapi**: armageddon mendapat angka dasarnya (5/4, tanpa increment) dan aturan bahwa ia boleh berakhir dengan cara apa pun. Format game turnamen ditetapkan 5+3.
- **ADR-0014 dilengkapi**: "jam baru berjalan di langkah pertama" mendapat kolom penandanya (`clock_started`) dan konsekuensi eksplisit bahwa putih bebas waktu untuk langkah pertamanya.
- **ADR-0008 tidak berubah**, tapi ketergantungannya menjadi eksplisit: kehabisan waktu adalah salah satu sebab yang **menilai rating**, dan karena itu jalur tutup game wajib menulis entri rating dalam transaksi yang sama.
- **`CONTEXT.md` diperbarui**: **Jam catur** mendapat model, presisi, dan dasar jamnya; **Format jam** menyebut enam preset dan "standar"; **Waktu bot hidup** menyebut bahwa ia **adalah** jam platform, bukan hanya penghitung batas waktu; **Armageddon** mendapat angka dan aturan berakhirnya.
- **Dua ticket baru lahir**: tombol **Menyerah** (memblokir #8, karena tombol itu elemen papan) dan **tawaran remis** (terpisah — mekanisme dua pihak dengan aturan waktunya sendiri). `end_reason='resign'` dan `draw_type='agreed'` sudah bernama sebelum pemiliknya ada.
- **Beban tulis**: satu tulisan per 60 detik untuk penghitung, ditambah satu tulisan per langkah (sudah ada). Tidak ada tulisan per detik per game.
- **Pemulihan setelah restart** menjadi satu pembacaan: semua game `status='playing'` dengan `clock_started` true memakai `white_centis`/`black_centis` + selisih jam platform; yang `clock_started` false tidak menyalakan jam sama sekali.

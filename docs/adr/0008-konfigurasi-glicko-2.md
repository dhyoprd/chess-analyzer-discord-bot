# Rating Glicko-2: satu pool, satu periode per game, dengan inflasi RD berbasis waktu nyata

## Konteks

Ticket [Konfigurasi sistem rating Glicko-2](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/11) harus menentukan bagaimana rating dihitung di komunitas yang **kecil dan jarang bermain** — beberapa game per minggu untuk seluruh server, dan pemain yang bisa hilang berbulan-bulan lalu kembali.

Dua kendala saling tarik-menarik:

- **Glicko-2 mengasumsikan pemain bermain dalam "rating period"** yang memuat banyak game (makalah menyarankan 10-15 game per pemain per periode) supaya estimasi volatilitas bermakna. Komunitas kita tidak akan pernah mencapai itu dalam periode mana pun.
- **ADR-0005 sudah mengunci bentuk tabelnya** (`rating_ledger` ber-scope pool + `player_ratings` untuk nilai terkini), dan [ADR-0006](0006-alur-turnamen-knockout.md) sudah memutuskan bahwa **armageddon, walkover, dan bye tidak mengubah rating**, sementara game turnamen yang benar-benar dimainkan mengubahnya.

Riset menemukan bahwa **spesifikasi Glicko-2 tidak menetapkan satu pun dari nilai-nilai yang tampak "baku"**: panjang periode diserahkan ke administrator, τ hanya diberi rentang 0.3-1.2, dan plafon RD 350 adalah konvensi Glicko-1, bukan ketentuan Glicko-2. Yang lebih menentukan: **tidak ada pustaka PyPI yang menyediakan inflasi RD berbasis waktu** — justru fitur yang paling dibutuhkan komunitas jarang-main — sehingga memakai pustaka berarti tetap menulis bagian tersulitnya sendiri sambil mewarisi keputusan desain yang tidak terdokumentasi.

## Keputusan

**Implementasi sendiri (~150 baris) Glicko-2 dengan kalibrasi Lichess, satu pool global, satu periode rating per game, dan inflasi RD berbasis waktu nyata.**

### Bentuk rating

- **Satu pool global**, kunci `"global"` (bukan NULL). Rating tidak dipecah per kategori kecepatan maupun per varian: **Chess960 ikut pool yang sama** dengan catur standar. Dimensi pool tetap ada di `rating_ledger` sehingga pemecahan nanti tidak menuntut migrasi.
- **Nilai awal**: rating 1500, RD 350, volatilitas 0.06 — bawaan spesifikasi.
- **Satu periode rating per game.** Setiap game selesai langsung memperbarui rating kedua pemain; tidak ada batch mingguan dan tidak ada scheduler.
- **Inflasi RD berbasis waktu nyata** diterapkan sebelum setiap game: `φ ← √(φ² + elapsedPeriods · σ²)`, dengan `elapsedPeriods = jam_sejak_game_berating_terakhir × 0.21436/24` — laju Lichess, yaitu **satu periode per ~4,67 hari**.
- **Invarian**: plafon RD **350** (sepasang dengan RD awal), lantai RD **45**, plafon volatilitas **0,1**, lantai rating **600**, **tanpa plafon rating**.
- **Keunggulan putih** sebesar **11,78 poin skor harapan** ditambahkan untuk pemain yang memegang putih, mengikuti Lichess.
- **τ = 0.75** (Lichess). Toleransi konvergensi iterasi Illinois ε = 0.000001.
- **Tanpa batas perubahan rating dari matematika Glicko-2**, tapi dengan **batas pengaman ±700 poin per game** ala Lichess.
- **Tanpa pengali keuntungan** ala Lichess: pool kita tertutup, jadi tidak ada deflasi jangka panjang yang perlu ditambal.

### Kapan rating ditulis

- **Hanya game yang benar-benar dimainkan antara dua manusia yang menilai rating.** Yang **tidak** menilai: lawan komputer, game impor, armageddon, walkover, bye, dan **game yang ditinggalkan**.
- **Kehabisan waktu dan menyerah menilai rating** — keduanya hasil tegas di papan dengan pemenang.
- **Kriteria "dinilai rating" adalah predikat di kode**, bukan kolom tersimpan: kedua pemain manusia, status selesai, ada pemenang, bukan armageddon. Tidak ada kolom baru di `games`.
- **Hasil game dan entri rating ditulis dalam satu transaksi**, di jalur tulis terserialisasi ADR-0005. Bot yang mati di tengah tidak pernah meninggalkan hasil tercatat tanpa rating.
- **Inflasi RD dihitung saat game selesai saja**, bukan saat rating dibaca. `/stats` menampilkan RD tersimpan, sehingga angka bisa direproduksi persis.

### Penjaga kewarasan

Sebelum menulis, hasil perhitungan diperiksa terhadap **invarian internal**: tidak ada nilai tak berhingga/NaN, RD di dalam [0, 350], volatilitas tidak melebihi 0,1.

Bila gagal: **entri rating ditolak, kegagalan dicatat keras, dan state pemain tidak diubah.** Hasil game tetap tercatat. Ini **berbeda dari Lichess**, yang me-reset pemain ke default — di server ini adminnya adalah pengembangnya sendiri, jadi sinyal yang bisa ditindaklanjuti lebih berguna daripada pemulihan otomatis yang menyembunyikan bug.

### Penyimpanan

- **`rating_ledger`** menyimpan **state penuh**: rating, RD, dan volatilitas **sebelum dan sesudah** untuk **kedua** pemain, lawan, hasil, dan jumlah periode yang berlalu — append-only, ber-scope pool `"global"`.
- **`player_ratings`** menyimpan nilai terkini per pool: rating, RD, volatilitas, jumlah game berating, dan waktu game berating terakhir.
- **Rating dan RD disimpan sebagai pecahan penuh**, dibulatkan hanya saat ditampilkan.

### Provisional dan tampilan

- **Provisional bila RD ≥ 110** — ambang Lichess, satu tingkat saja. Ini definisi tunggal yang berlaku di seluruh platform, termasuk **seeding turnamen**: pemain dengan RD < 110 diunggulkan menurut rating, sisanya diacak. Ini menutup ambiguitas "pemain provisional diacak" di ADR-0006.
- **Pemain tanpa game berating belum muncul di klasemen** — termasuk yang hanya bermain lawan komputer atau mengimpor game. Untuk seeding, mereka diperlakukan sama dengan provisional (diacak).
- **Pemain provisional tampil di klasemen** dengan penanda, tidak disingkirkan.
- **Format**: `1523` bila mapan, `1523 (provisional, ±120)` bila belum.
- **Saat game berakhir, selisihnya ditampilkan**: `1523 → 1541 (+18)`.

## Alasan

- **Inflasi RD berbasis waktu adalah satu-satunya cara Glicko-2 menangani pemain jarang-main.** Tanpa itu, pemain yang hilang setahun kembali dengan RD sempit dan rating lamanya dipercaya berlebihan, sehingga kekalahan pertamanya menghantam keras. Dengan itu, ketidakpastian mencerminkan waktu yang benar-benar berlalu. Lichess melakukan hal yang sama, dan Glicko-1 menyatakan periode rating "bisa sesingkat satu menit" dengan pembaruan per game — model yang diwarisi Glicko-2, yang menyerahkan panjang periode ke administrator.
- **Implementasi sendiri, bukan pustaka.** Satu-satunya pustaka Glicko-2 murni-Python yang terawat **tidak punya inflasi berbasis waktu**; memakainya berarti tetap menulis bagian tersulitnya sendiri sambil mewarisi τ yang ter-hardcode dan keputusan desain yang tidak terdokumentasi. Algoritmanya ~150 baris dan sepenuhnya dispesifikasikan, dengan **contoh kerja makalah sebagai tes regresi**: pemain 1500/RD 200/σ 0.06 melawan 1400/1550/1700 dengan hasil menang-kalah-kalah harus menghasilkan **rating 1464.06, RD 151.52, volatilitas 0.05999**. Tes itu mematikan suku keunggulan putih supaya contohnya bisa direproduksi.
- **Kalibrasi Lichess, bukan contoh makalah.** Nilai-nilai yang kita pakai (τ 0.75, laju inflasi 0.21436/hari, lantai RD 45, lantai rating 600, ambang provisional 110, batas ±700, keunggulan putih 11,78, plafon volatilitas 0,1) semuanya sudah teruji pada populasi nyata dengan masalah yang sama: pemain yang datang dan pergi. Contoh makalah adalah ilustrasi, bukan kalibrasi.
- **Plafon RD tetap 350, bukan 500 seperti Lichess.** Kita memilih RD awal 350 dari spesifikasi, jadi plafon 500 akan berarti pemain yang lama hilang menjadi **lebih** tidak pasti daripada pemain yang belum pernah bermain. Menyimpang dari Lichess di sini justru menjaga satu arti untuk "tidak diketahui sama sekali".
- **Satu pool.** Dengan beberapa game per minggu untuk seluruh server, memecah rating per kategori kecepatan berarti setiap pool punya sangat sedikit game sehingga tidak pernah mapan, dan klasemen menjadi beberapa daftar hampir kosong. Satu angka juga membuat klasemen langsung bermakna.
- **Batas ±700 adalah jaring pengaman bug, bukan bagian dari model.** Di tangga 5 orang, satu bug (hasil tertukar, pemain salah) menjadi kerusakan permanen yang tidak bisa dirata-ratakan oleh lawan lain. Lichess memakai angka yang sama, dan 700 praktis tidak pernah menyentuh permainan normal sehingga tidak menyerempet model ketidakpastian Glicko-2. Alasan awal ticket ini menolak batas karena mengira Lichess tidak memakainya — **itu keliru**.
- **Menolak tulis, bukan me-reset pemain.** Reset diam-diam ke default menghancurkan riwayat rating dan justru menyembunyikan bug yang menyebabkannya. Menahan entri rating sambil mencatat keras membuat bug terlihat dan bisa diperbaiki.
- **State penuh di ledger.** ADR-0005 menyebut `rating_ledger` sebagai kebenaran yang bisa diaudit. Menyimpan hanya rating sebelum/sesudah membuat riwayat RD hilang, sehingga mustahil membuktikan mengapa rating bergerak sebanyak itu dan bug perhitungan tidak bisa direproduksi dari ledger.
- **Predikat, bukan kolom.** Kolom tersimpan menjadi sumber kebenaran kedua yang bisa berbeda dari aturan. Absennya entri ledger pada game yang gagal penjaga kewarasan adalah **sinyal bug**, bukan klasifikasi rating — dan menutupinya dengan kolom justru menyamarkan bug itu.
- **Pemain tanpa game berating tidak muncul.** Rating 1500 dengan RD 350 untuk orang yang belum pernah bermain berating adalah derau di klasemen; seluruh pemain baru akan menumpuk di angka yang sama tanpa informasi apa pun.
- **Tanpa pengali keuntungan.** Pengali Lichess melawan deflasi dari populasi yang terus bertambah; pool kita tertutup dan kecil. Menambal masalah yang belum kita miliki berarti menambah konstanta tak terjelaskan yang menyulitkan reproduksi perhitungan.
- **Tanpa plafon rating.** Asimetri disengaja: angka rendah merendahkan pemain dan tidak informatif, sedangkan angka tinggi bermakna. Batas ±700 dan penjaga kewarasan sudah menangkap kasus patologis.

## Konsekuensi

- **Kode rating menjadi milik kita untuk dirawat.** ~150 baris plus tes regresi terhadap contoh kerja makalah, ditambah tes untuk inflasi berbasis waktu yang tidak dimiliki pustaka mana pun. Ini menuntut disiplin: setiap perubahan pada rumus harus lolos contoh kerja makalah.
- **`rating_ledger` dan `player_ratings` mendapat kolom yang belum ada di ADR-0005** — kolom volatilitas dan RD di kedua tabel, serta jumlah game berating dan waktu game berating terakhir di `player_ratings`. Skema harus diperluas saat implementasi.
- **`player_ratings` hanya berisi pemain dengan minimal satu game berating.** Klasemen dan `/stats` harus menangani pemain yang punya baris `players` tapi tidak punya baris `player_ratings` — ini keadaan normal, bukan kasus tepi.
- **Rating bergantung pada jam dinding.** Laju inflasi memakai waktu nyata, bukan waktu bot hidup — berbeda dari ADR-0003 dan ADR-0006 yang memakai waktu bot hidup untuk batas waktu game dan turnamen. Ini disengaja: rating adalah pernyataan tentang kekuatan pemain di dunia nyata, sedangkan batas waktu adalah tentang keadilan.
- **Inflasi hanya terjadi saat game selesai.** Pemain yang lama hilang tetap terlihat ber-RD sempit di `/stats` sampai ia bermain lagi. Angka yang ditampilkan dan RD yang akan dipakai di game berikutnya bisa berbeda, dan itu harus dijelaskan bila ditanyakan.
- **`games` tidak mendapat kolom penanda rating.** Setiap tempat yang perlu tahu apakah sebuah game dinilai rating harus memakai predikat yang sama. Predikat itu memuat beberapa syarat dan harus dijaga sinkron dengan ADR ini, ADR-0006, dan ADR-0007.
- **Ambang provisional RD 110 kini jadi definisi bersama** untuk `/stats`, klasemen, dan seeding turnamen. Mengubahnya berarti mengubah perilaku turnamen juga.
- **Lantai rating 600 dan tanpa plafon berarti rentangnya terbuka ke atas.** Klasemen bisa menampilkan pemain yang jauh di atas yang lain setelah bertahun-tahun, dan itu diterima.
- **`CONTEXT.md` diperbarui**: **Rating** dan **Provisional** diberi isi yang tepat (satu pool, ambang RD 110, inflasi berbasis waktu), dan istilah **Pool rating** ditegaskan bernilai tunggal.

# Penyajian /stats: dua blok populasi, satu embed, peringkat dari `player_ratings`

## Konteks

Ticket [Penyajian /stats](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/16) menanyakan bagaimana statistik seorang pemain disajikan. Model data sudah dikunci di [ADR-0005](0005-model-data-platform.md), rating di [ADR-0008](0008-konfigurasi-glicko-2.md), pipeline analisa di [ADR-0009](0009-pipeline-analisa.md), dan impor di [ADR-0011](0011-impor-game-eksternal-dan-klaim-akun.md) — jadi ticket ini tidak menggantung pada apa pun.

Dua kendala membentuk seluruh keputusan:

- **ADR-0011:78 sudah mewajibkan** `/stats` membedakan game berating dari game impor, karena menyatukannya menyesatkan pembaca tentang arti rating Glicko-2.
- **Klasifikasi bukan milik `moves`** (ADR-0005), melainkan milik **analisa**, dan satu game bisa punya beberapa analisa. Setiap angka akurasi harus menyebut analisa mana yang dibaca.

## Keputusan

**Satu perintah `/stats`, satu embed, dua blok populasi terpisah.**

### Perintah

- **`/stats`** dengan dua opsi opsional bertipe **User**: `pemain:` dan `lawan:`. Tanpa `pemain:`, subjeknya pemanggil sendiri. Tanpa `lawan:`, tidak ada field rekor pertemuan.
- **`lawan:` selalu relatif ke subjek.** `/stats pemain:@A lawan:@B` berarti "statistik A, plus rekor A melawan B". Satu aturan, tanpa kasus khusus.
- **`lawan:` yang menunjuk subjek sendiri ditolak dengan kalimat**, sisa embed tetap dirender.
- **Balasan publik** di channel, bukan ephemeral.
- **Nama perintah `/stats` dipertahankan.** Nama perintah lain mengikuti apa yang sudah dikunci ADR masing-masing; tidak ada penyeragaman bahasa.

### Dua blok populasi

- **Blok berating**: game yang memenuhi predikat berating di bawah — dinilai rating. Memuat rating, RD, status provisional, jumlah game, rekor menang-kalah-remis, akurasi, dan hitungan klasifikasi. **Tidak** memuat keranjang `tanpa hasil`, karena populasi ini mengecualikan game ditinggalkan.
- **Blok semua game**: seluruh game selesai yang memuat pemain ini, **dengan hasil papan apa pun** — termasuk remis, armageddon, dan game ditinggalkan. Memuat rekor empat keranjang, akurasi, dan **baris komposisi**. **Tanpa** hitungan klasifikasi — klasifikasi atas game lawan Stockfish level 800 tidak mengukur kemampuan manusia.
- **Rating hanya muncul di blok berating**, karena hanya di sana ia bermakna.
- **Hanya game berstatus selesai** yang dihitung di kedua blok.

### Enam field

| Field | Isi |
|---|---|
| **Rating** | `#3` · `1523` atau `1523 (provisional, ±120)` — format ADR-0008. Tiga keadaan: (a) belum ada game berating → arahan, **bukan** 1500/RD 350; (b) ada game berating tapi **tidak ada baris `player_ratings`** — entri ditolak penjaga kewarasan ADR-0008:42 — → **kalimat kegagalan eksplisit** ("rating tidak tersedia — entri rating ditolak penjaga kewarasan"), rekor tetap tampil, nomor peringkat tidak ada; (c) normal |
| **Rekor berating** | `12 menang · 8 kalah · 2 remis`. **Tanpa** penghitung `tanpa hasil` — populasi ini mengecualikan game ditinggalkan (lihat Semua game) |
| **Akurasi & klasifikasi** | Mean sederhana per game, hitungan mentah inaccuracy/mistake/blunder, baris basis `dari 12 game beranalisa, 3 menunggu`, `1 gagal` bila bukan nol |
| **Semua game** | Rekor **empat keranjang**: menang · kalah · remis · **tanpa hasil** (yang terakhir hanya bila bukan nol), akurasi, komposisi `12 platform · 8 impor · 3 lawan komputer` (hanya jenis bukan nol) |
| **Rekor pertemuan** | Hanya bila `lawan:` diberikan. Hanya game berating. Berlabel. Tanpa pertemuan: kalimat, bukan field kosong |
| **Riwayat rating** | 10 baris `rating_ledger` terakhir milik subjek: `vs NamaLawan menang 1523 → 1541 (+18)`. Disembunyikan bila kosong |

**Footer** (bukan field): `Akun: lichess:dhyo ✓ · chess.com:hikaru (belum terverifikasi)`, hanya bila ada tautan dan hanya untuk subjek yang merupakan pemain Discord.

### Aturan hitung

- **Akurasi = mean sederhana per game**, bukan penggabungan per langkah. Setiap game yang punya analisa selesai menyumbang satu angka. Hitungan klasifikasi = **jumlah mentah**.
- **Hanya analisa berstatus selesai** yang dibaca; yang ditampilkan adalah **analisa selesai terbaru** per game (ADR-0009:69).
- **`beranalisa`** = game yang punya **nilai akurasi**. Game 1 ply dianalisa tapi tidak punya akurasi (ADR-0009) sehingga **tidak** dihitung di basis.
- **`menunggu`** = game **berminimal satu langkah** yang belum punya analisa selesai dan belum gagal permanen. Game 0 ply dikecualikan — ADR-0009:81 melewatinya tanpa mencatat apa pun, jadi ia tidak akan pernah beranalisa dan hitungannya tidak akan pernah turun.
- **`gagal`** = game dengan analisa gagal yang percobaannya sudah habis (3, ADR-0009:71).
- **Hitungan menunggu/gagal mengikuti populasi field-nya**: di field akurasi berating hanya game berating; di blok semua-game **semua** game selesai yang memuat pemain ini — `platform` (termasuk armageddon dan ditinggalkan), impor, dan lawan komputer.
- **Komposisi didefinisikan atas `games.source`**, bukan atas predikat: `platform · impor · lawan komputer`. Ketiganya nilai `source`, sehingga **setiap** game jatuh tepat di satu keranjang dan jumlahnya selalu cocok dengan total rekor di field yang sama. Predikat berating **tidak** dipakai sebagai keranjang, karena ia memotong populasi di dalam `platform` (armageddon, ditinggalkan) dan membuat jumlahnya tidak pernah cocok.
- **Game ditinggalkan** mendapat keranjang **tanpa hasil** di rekor blok semua-game, muncul hanya bila bukan nol.

### Peringkat

- **Nomor peringkat disertakan**, diambil dari urutan `player_ratings`.
- **Urutan: rating menurun → jumlah game berating menurun → `player_id` menaik.** Deterministik: peringkat hanya bergeser bila ada yang bermain.
- **Pemain provisional ikut bersaing**, tidak ditempatkan terpisah.
- **Pemain tanpa baris `player_ratings` tidak punya nomor peringkat.** Dua sebab, keduanya tanpa nomor: belum pernah bermain berating, atau entri rating pertamanya ditolak penjaga kewarasan. Rekor beratingnya tetap tampil pada kasus kedua.

### Nama

- **Diresolusi langsung dari Discord** saat perintah dijalankan, tanpa kolom `display_name`. Objek `User` tetap membawa `name` dan `global_name` meski pemain sudah keluar guild, jadi tidak ada cabang khusus — nama panggilan guild dipakai bila ada, nama global bila tidak.

## Amandemen skema

Tiga kolom baru di `games`, semuanya dibutuhkan predikat berating dan baris komposisi:

- **`games.source`** — `platform` | `import` | `engine`. NOT NULL, **tanpa default**. Default `platform` akan membuat jalur yang lupa mengisi gagal senyap — game impor menjadi `platform` dan ikut dinilai rating. Tanpa default, jalur itu gagal keras saat menulis.
- **`games.is_armageddon`** — boolean, NOT NULL, default false.
- **`games.result`** — `white` | `black` | `draw` | `none`. NOT NULL. `none` = game tanpa hasil (ditinggalkan). ADR-0006:23 sudah mewajibkan `games` mencatat kebenaran papan, tapi tidak ada ADR yang menamai kolomnya; tanpa nama, klausa "hasil papan ada" di predikat berating tidak bisa dievaluasi.

**Predikat berating hasil amandemen:**

```
source = 'platform'
AND kedua pemain manusia
AND status = selesai
AND result IN ('white','black','draw')   -- hasil papan ada
AND NOT is_armageddon
```

`ada pemenang` **diganti**, bukan dihapus: ADR-0008:34 mensyaratkan pemenang, sehingga remis tidak pernah lolos predikat — padahal ADR-0008:32, ADR-0009:63, dan `CONTEXT.md` tidak pernah mengecualikan remis dari game yang dinilai rating. Tanpa pengganti, game ditinggalkan akan ikut dinilai; dengan `result IN (...)`, remis kembali dinilai dan game ditinggalkan tetap tersaring.

## Alasan

- **Dua blok, bukan satu angka gabungan.** Rating Glicko-2 adalah pernyataan tentang kekuatan bermain melawan manusia di platform ini (ADR-0008). Game impor dan lawan komputer sengaja tidak menyentuhnya. Menampilkan satu rekor gabungan membuat pembaca menyimpulkan rating 1523 dibentuk oleh 200 game Lichess yang sebenarnya tidak pernah menyentuh perhitungannya — persis kekeliruan yang ADR-0011:78 minta dicegah.
- **Rating hanya di blok berating.** Angka tanpa makna di tempat yang salah lebih buruk daripada absennya angka. Blok semua-game tetap memuat rekor dan akurasi, karena di situlah game impor punya nilainya: analisa Stockfish atas permainan orang di tempat lain.
- **Tidak ada hitungan klasifikasi di blok semua-game.** Klasifikasi mengukur kehilangan win-chance relatif terhadap lawan. Melawan Stockfish level 800, hampir setiap langkah pemain manusia adalah langkah terbaik karena lawannya membuat kesalahan lebih dulu — hitungannya akan terlihat bagus dan tidak mengukur apa pun.
- **Mean sederhana per game, bukan gabungan per langkah.** "Akurasi rata-rata" yang dibaca orang berarti rata-rata atas permainan, bukan rata-rata atas langkah. Penggabungan per langkah membuat satu game 120 langkah menenggelamkan sembilan game 20 langkah, sehingga pemain tidak bisa memakai angkanya untuk menilai diri sendiri.
- **Hitungan klasifikasi sebagai jumlah mentah.** Sebuah blunder adalah satu peristiwa, bukan rata-rata. "1,3 blunder per game" memaksa pembaca mengalikan sendiri untuk mendapat angka yang ingin ia ketahui.
- **Hanya analisa selesai yang dibaca, dan yang terbaru.** `analyses` adalah entitas bersejarah (ADR-0009) sehingga satu game bisa punya beberapa baris. Membaca yang terbaru menjaga angka tetap konsisten dengan apa yang ditampilkan di pesan hasil analisa, dan tidak pernah mencampur analisa lama dengan baru.
- **`menunggu` dipisahkan dari `gagal`.** Keduanya berarti "tidak ada angka", tapi hanya satu yang akan berubah sendiri. Menyatukannya menghasilkan angka yang tidak pernah turun tanpa penjelasan — dan ADR-0009:71 sudah membedakan keduanya di database, jadi menyatukannya di tampilan berarti membuang informasi yang ada.
- **Hitungan menunggu/gagal mengikuti populasi field-nya.** Basis akurasi berating yang menyebut "3 menunggu" padahal ketiganya game impor akan salah menjelaskan kenapa akurasi berating belum lengkap.
- **`tanpa hasil` terpisah dari remis, dan tinggal di blok semua-game.** ADR-0006 memisahkan hasil papan dari hasil pertandingan secara sengaja, dan game ditinggalkan tidak punya pemenang di papan. Menghitungnya sebagai remis membuat pemain yang ditinggalkan lawannya terlihat sering remis — pernyataan yang keliru tentang papan. Tempatnya hanya bisa di blok semua-game: populasi berating **mengecualikan** game ditinggalkan, jadi penghitung itu di sana selalu nol dan aturan "muncul bila bukan nol" membuatnya tidak pernah tampil.
- **Penghitung kondisional.** Pemain yang tidak pernah meninggalkan game tidak perlu melihat `0` seumur hidupnya. Field yang selalu nol melatih pembaca mengabaikan field itu, dan ia akan terlewat saat akhirnya berisi.
- **Peringkat dari `player_ratings`, provisional ikut bersaing.** ADR-0008 memutuskan pemain provisional tetap tampil di klasemen dengan penanda. Menyingkirkannya dari urutan akan membuat nomor peringkat tidak cocok dengan klasemen yang dilihat orang di tempat lain — dua nomor berbeda untuk pemain yang sama adalah bug yang menunggu dilaporkan.
- **Urutan tiga tingkat yang deterministik.** Tanpa pemutus, urutan baris SQLite bisa berubah antar-kueri dan peringkat seorang pemain bergeser tanpa ada yang bermain. Jumlah game berating sebagai tingkat kedua menempatkan pemain yang lebih terbukti di atas pada rating yang sama, dan `player_id` menutup kasus yang benar-benar identik.
- **Nama langsung dari Discord.** Satu-satunya nama yang benar adalah nama yang berlaku sekarang. Kolom `display_name` akan basi tanpa ada yang menyadarinya, dan nama yang basi lebih buruk daripada satu panggilan API.
- **`/stats` dipertahankan sebagai nama.** Ia sudah tertulis di destination peta, judul ticket ini, dan seluruh ADR. Menyeragamkan bahasa perintah berarti mengganti nama yang sudah dipakai di dokumen yang tidak akan ikut berubah.
- **Opsi `lawan:` relatif ke subjek, bukan ke pemanggil.** "Statistik A, rekor A melawan B" adalah satu kalimat yang bisa dibaca tanpa aturan tambahan. Membuat `lawan:` selalu relatif ke pemanggil berarti perintah yang sama menjawab dua pertanyaan berbeda tergantung opsi lain.
- **Tanpa filter kategori kecepatan dan varian.** ADR-0008 mengunci satu pool rating, jadi filter tidak mengubah satu pun angka rating — ia hanya memecah rekor dan akurasi menjadi potongan yang, di server dengan beberapa game per minggu, sebagian besar kosong. Parameter bisa ditambahkan nanti tanpa membongkar apa pun.
- **Tanpa grafik rating.** Dengan beberapa game per minggu, garis rating adalah titik-titik jarang yang lebih buruk dibaca daripada sepuluh angka. Pillow terverifikasi jalan (ticket #5), tapi kemampuan menggambar bukan alasan untuk menggambar.
- **Tanpa field game terakhir.** Riwayat rating sudah memuat lawan dan hasil sepuluh game terakhir. Field "game terakhir" menduplikasi baris teratasnya sambil menambah satu kueri, dan tautan analisa milik pesan hasil analisa — bukan `/stats`.
- **Nol game dibalas teks, bukan embed kosong.** Embed berisi dua blok kosong terbaca seperti perintah rusak. Satu kalimat jujur lebih baik.
- **`source` sebagai kolom, meski ADR-0008:34 menulis "tidak ada kolom baru di `games`".** Yang ADR-0008 tolak adalah kolom berisi **kesimpulan** "game ini dinilai rating", karena kesimpulan tersimpan bisa berbeda dari aturan. Di sini yang disimpan adalah **fakta asal game** — peristiwa yang terjadi sekali dan tidak pernah berubah. Predikatnya tetap dihitung di kode dan tetap satu-satunya tempat aturan itu hidup. Tanpa kolom ini, predikat di ADR-0008:34 **salah** untuk setiap game impor yang kedua sisinya sudah diklaim, karena "kedua pemain manusia" menjadi benar padahal game itu tidak boleh dinilai.
- **`is_armageddon` menutup lubang yang ADR-0008 sendiri buka.** Predikat di ADR-0008:34 sudah mensyaratkan "bukan armageddon", tapi tidak ada satu pun kolom, tabel, atau relasi dalam ADR-0005 maupun ADR-0006 yang menyatakan sebuah game adalah armageddon — `tournament_matches.game_id` justru tunggal sementara satu pertandingan bisa memuat tiga game. Syarat itu tidak bisa dievaluasi hari ini. Kolom boolean adalah bentuk terkecil yang membuatnya bisa.
- **`is_armageddon` sebagai kolom, bukan tabel penghubung.** Predikat berating butuh satu bit; membongkar `tournament_matches.game_id` menjadi tabel penghubung menuntut perubahan pada bracket ADR-0006 yang sudah terkunci, demi kebutuhan yang lebih kecil dari perubahan itu.
- **`result` dinamai, bukan disimpulkan.** ADR-0006:23 mewajibkan `games` mencatat kebenaran papan, tapi tidak satu pun ADR menamai kolomnya. Klausa predikat yang baru — "hasil papan ada" — menuntut fakta itu punya nama dan nilai yang bisa dibandingkan. `none` dipilih sebagai nilai tersendiri alih-alih membiarkan kolomnya NULL, supaya "tanpa hasil" adalah pernyataan yang disengaja, bukan ketiadaan data.
- **`ada pemenang` diganti, bukan dihapus.** ADR-0008:34 menuntut pemenang sehingga remis — hasil inti catur — tidak pernah lolos predikat: tidak pernah dinilai rating, tidak pernah muncul di rekor berating, dan `2 remis` di field rekor akan selalu nol. Daftar pengecualian di ADR-0008:32 dan `CONTEXT.md` adalah daftar **tertutup** yang tidak memuat remis, jadi remis memang seharusnya dinilai. Menghapus klausa tanpa pengganti akan memasukkan game ditinggalkan; `result IN ('white','black','draw')` menutup keduanya.
- **Komposisi atas `source`, bukan atas predikat.** Keranjang pertama yang berupa predikat tidak bisa dijumlahkan dengan dua keranjang yang berupa `source`: armageddon dan game ditinggalkan ber-`source='platform'` tapi bukan berating, sehingga keduanya jatuh di luar semua keranjang dan jumlah komposisi lebih kecil dari rekor di sebelahnya. Tiga nilai `source` mempartisi populasi dengan tepat, dan pembaca yang menjumlahkan mendapat angka yang cocok.
- **Basis akurasi menyaring 0-ply dan 1-ply.** ADR-0009 melewati game tanpa langkah tanpa mencatat apa pun, dan menganalisa game 1 ply tanpa menghasilkan akurasi. Menghitung keduanya di basis membuat "dari 3 beranalisa" menyebut game yang tidak menyumbang satu angka pun ke mean, dan "menunggu" menyebut game yang tidak akan pernah diproses.
- **Riwayat dari `rating_ledger`, bukan dari daftar game.** Format baris menuntut pasangan sebelum/sesudah yang hanya ada di ledger. Game berating yang entrinya ditolak penjaga kewarasan tidak punya baris ledger; menampilkannya di riwayat berarti satu baris tanpa angka, sementara kegagalannya sudah ditampilkan di field Rating. Riwayat tetap jujur kalau ia menyatakan dirinya sebagai riwayat **perubahan rating**, bukan riwayat permainan.
- **`source` tanpa nilai default.** Kolom ini ada justru karena jalur yang lupa mengisinya berbahaya: `DEFAULT 'platform'` membuat `/impor` yang lupa menulis `source` menghasilkan game berstatus platform yang ikut dinilai rating — kegagalan senyap yang hanya terlihat sebagai angka rating yang aneh berbulan-bulan kemudian. Tanpa default, kesalahan itu muncul saat baris pertama ditulis.

## Konsekuensi

- **ADR-0005 diamendemen**: `games` mendapat kolom `source` (`platform`/`import`/`engine`, NOT NULL tanpa default), `is_armageddon` (boolean, NOT NULL default false), dan `result` (`white`/`black`/`draw`/`none`, NOT NULL).
- **ADR-0008 diamendemen**: baris 34 dan 80 menyatakan "tidak ada kolom baru di `games`". Amandemen ini **mengizinkan tepat tiga kolom fakta** dan tetap melarang kolom kesimpulan rating. Predikat berating menjadi `source = 'platform' AND kedua pemain manusia AND status = selesai AND result IN ('white','black','draw') AND NOT is_armageddon` — satu tempat, di kode, dibaca oleh semua pemanggil.
- **Populasi rating berubah: remis kini dinilai.** Ini bukan penyesuaian kosmetik — sebelum amandemen ini, Glicko-2 tidak pernah menerima satu pun hasil remis, sehingga rating seluruh platform miring terhadap hasil imbang. Pemain yang sering remis akan bergerak berbeda setelah perbaikan ini.
- **Kolom `source` harus diisi di setiap jalur yang membuat baris `games`**: game santai, game turnamen, lawan komputer (`engine`), dan `/impor` (`import`). Tanpa default, jalur yang lupa akan **gagal keras** saat menulis — itu tujuannya.
- **`result` harus ditulis saat game berakhir**, termasuk `none` untuk game ditinggalkan. Game yang berakhir tanpa menulis `result` tidak bisa diklasifikasi dan akan hilang dari kedua blok `/stats`.
- **`/stats` menampilkan RD tersimpan, bukan RD yang sudah diinflasi.** ADR-0008:36 menetapkan inflasi hanya dihitung saat game selesai, jadi pemain yang lama hilang tetap terlihat ber-RD sempit sampai ia bermain lagi. Angka di `/stats` dan RD yang akan dipakai di game berikutnya bisa berbeda, dan pengguna yang bertanya harus mendapat penjelasan itu.
- **Rekor berating dan rating bisa berbeda jumlahnya.** Bila penjaga kewarasan ADR-0008 menolak sebuah entri `rating_ledger`, game itu tetap memenuhi predikat berating — ia masuk rekor dan akurasi — tapi rating tidak bergerak (ADR-0008:42 menahan entri, tidak me-reset state). Selisih antara "jumlah game berating" di rekor dan jumlah game yang benar-benar mengubah rating adalah **sinyal bug**, bukan keadaan normal, dan `/stats` tidak boleh menyembunyikannya dengan menyamakan keduanya.
- **Pemain bisa punya game berating tanpa punya baris `player_ratings`.** Bila entri rating pertamanya ditolak penjaga kewarasan, ADR-0008:42 tidak menulis state sama sekali, sehingga baris `player_ratings` tidak pernah dibuat. Field Rating menampilkan kalimat kegagalan, rekor tetap tampil, nomor peringkat tidak ada. Ini berbeda dari pemain yang belum pernah bermain berating, dan kedua keadaan itu tidak boleh dirender sama.
- **Nomor peringkat di `/stats` mengunci kebijakan urutan yang juga dipakai klasemen.** Ticket [Penyajian klasemen](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/22) mewarisi urutan ini: rating menurun → jumlah game berating menurun → `player_id` menaik, provisional ikut bersaing. Bila #22 mengubahnya, `/stats` harus ikut berubah di commit yang sama.
- **Kelayakan peringkat belum diputuskan, dan #22 bisa memutuskan sebaliknya.** Aturan yang dikunci di sini hanya "nomor ada bila baris `player_ratings` ada". Bila #22 memasang ambang minimum jumlah game, `/stats` akan menampilkan `#3` untuk pemain yang tidak muncul di klasemen — dua angka berbeda untuk pemain yang sama. Aturan kelayakan harus diputuskan di #22 dan `/stats` mengikutinya di commit yang sama, persis seperti urutannya. *(Diselesaikan [ADR-0016](0016-penyajian-klasemen.md): #22 memilih **tanpa ambang** — kelayakannya sama persis dengan aturan di sini, sehingga ADR ini tidak berubah. Klasemen memuat pemain yang punya baris `player_ratings`, dan `#N` di `/stats` selalu punya baris yang sepadan.)*
- **`CONTEXT.md` diperbarui**: istilah **Berating** ditambahkan (kata ini sudah dipakai di definisi **Rating**, **Provisional**, dan **Pool rating** tanpa pernah didefinisikan), bersama **Tanpa hasil** dan **Peringkat**.
- **`field.value` 1024 adalah batas yang mengikat untuk field riwayat.** Sepuluh baris berisi lawan + hasil + perubahan rating harus dipotong bila melewatinya; pemotongan menyebut berapa baris disembunyikan, mengikuti pola penjaga yang sudah ditetapkan ticket #7.
- **Perintah analisa ulang belum punya pemilik.** `CONTEXT.md` mendefinisikannya sebagai perintah yang dipicu pemain, dan ADR-0009:71 menyebut "menunggu analisa ulang manual" sebagai jalur keluar untuk game yang gagal 3 kali — tapi tidak ada ADR yang menetapkan perintahnya. Dicatat sebagai kabut di peta.

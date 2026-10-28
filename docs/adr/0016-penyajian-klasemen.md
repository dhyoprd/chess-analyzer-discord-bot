# Penyajian klasemen: satu perintah, satu kolom, tanpa ambang

## Konteks

Ticket [Penyajian klasemen](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/22) menanyakan bagaimana daftar peringkat disusun dan disajikan. Ini permukaan bot terakhir yang belum punya pemilik, dan ia istimewa karena **bukan statistik satu pemain**: ia merender satu kolom pemain sekaligus.

Urutan dan format angkanya sudah terkunci [ADR-0012](0012-penyajian-stats.md) — rating menurun, lalu jumlah game berating menurun, lalu `player_id` menaik; provisional ikut bersaing; format `1523` / `1523 (provisional, ±120)` dari [ADR-0008](0008-konfigurasi-glicko-2.md). Yang ditinggalkan terbuka secara sengaja hanya **kelayakan** — dan ADR-0012:128 memasang taruhan: bila #22 memasang ambang minimum game, `/stats` harus ikut berubah di commit yang sama, karena `#3` di `/stats` dan klasemen yang tidak memuat peringkat 3 adalah dua angka berbeda untuk pemain yang sama.

Tiga kendala membentuk keputusan-keputusan di bawah:

- **Populasi kecil.** Server ini 4-16 orang, beberapa game per minggu. Mesin apa pun yang mengasumsikan populasi besar (halaman, ambang, peringkat terpisah) akan menghasilkan layar hampir kosong.
- **`/stats` mencetak nomor peringkat absolut.** Setiap aturan yang menyembunyikan baris dari klasemen menciptakan nomor yang tidak bisa dicari pembaca di tempat lain.
- **Nama adalah input pengguna yang masuk ke code block.** Nama Discord bisa memuat backtick, dan satu nama berisi tiga backtick menutup fence.

## Keputusan

**Satu perintah `/klasemen` tanpa opsi, satu embed, satu kolom teks di dalam code block.**

### Kelayakan: punya baris `player_ratings`, tanpa ambang

- **Tidak ada ambang minimum game berating.** Siapa pun yang sudah pernah memainkan satu game berating masuk klasemen.
- **Kelayakan = adanya baris `player_ratings`** — bukan hitungan yang dihitung ulang. Ini aturan yang sudah dipakai `/stats` (ADR-0012:60), sehingga **ADR-0012 tidak berubah sama sekali**.
- **`CONTEXT.md` sudah menyatakan aturan ini**: **Peringkat** — "Peringkat hanya dimiliki pemain yang sudah punya rating"; **Provisional** — "Pemain yang belum pernah memainkan satu pun game berating belum punya rating dan belum muncul di klasemen". Memasang ambang berarti mengamendemen kedua definisi itu.
- **Pemain yang entri ratingnya ditolak penjaga kewarasan ADR-0008:42 tidak muncul, tanpa keterangan.** Ia punya game berating tapi tidak punya baris `player_ratings`, jadi ia tidak punya rating — dan klasemen hanya memuat pemain ber-rating. `/stats` sudah menampilkan kalimat kegagalan eksplisit untuk orang yang mencari dirinya (ADR-0012:35); mengulanginya di sini berarti menyebut kegagalan internal ke setiap pembaca klasemen.

### Perintah

- **`/klasemen`**, tanpa opsi. Tanpa penyaringan, tanpa batas baris, tanpa opsi pemain.
- **Balasan publik** di channel, mengikuti `/stats` (ADR-0012:21). Isinya identik untuk semua pemanggil.
- **Hanya saat diminta.** Tidak ada pesan tetap yang diperbarui, tidak ada pengiriman berkala, tidak ada scheduler.
- **Nama perintah berbahasa Indonesia**, berbeda dari `/stats`. Tidak ada penyeragaman: `/stats` dipertahankan karena sudah tertulis di seluruh dokumen (ADR-0012:22), dan `klasemen` adalah istilah glosarium kita sendiri.

### Satu baris

```
   #1                              1541   dhyoprd
   #2          1523 (provisional, ±120)   nekoadi
   #3          1488 (provisional, ±211)   wibowo
   #4                              1412   putu
```

- **Tiga kolom: peringkat, rating, nama.** Tidak ada jumlah game, rekor, atau akurasi. Penanda provisional sudah membawa sinyal kepercayaan, dan rincian performa adalah milik `/stats`.
- **Bentuk rating memakai format ADR-0008:55 apa adanya** — `1523` atau `1523 (provisional, ±120)`. Tidak ada bentuk ringkas kedua, supaya `/stats` dan klasemen tidak pernah menulis angka yang sama dengan dua cara.
- **Semua kolom angka rata kanan** — peringkat, rating. Nama rata kiri.
- **Lebar kolom dihitung dari isi**, bukan ditetapkan: kolom peringkat dari nomor terlebar, kolom rating dari string terlebar yang benar-benar muncul, kolom nama dari nama terpanjang.
- **Nama dipotong maksimum 24 karakter**, diakhiri `…`. Satu nama 32 karakter tidak boleh memperlebar setiap baris.
- **Pemisah kolom tiga spasi.**

### Code block, dan sanitasi nama

- **Daftar ditaruh di `description` embed (4096 karakter) di dalam satu code block**, bukan di `field` (1024). Font monospace yang membuat kolom benar-benar rata hanya ada di dalam code block.
- **Backtick di nama disanitasi** sebelum masuk code block — diganti apostrof. Nama Discord adalah input pengguna, dan satu nama berisi tiga backtick menutup fence sehingga **seluruh embed rusak**, kegagalan senyap yang bisa dipicu sendiri oleh pemain.
- **Baris ditambahkan sampai mendekati 4096**, menyisakan ruang untuk baris penutup; sisanya diringkas satu baris **di luar fence**: `… dan N pemain lain tidak ditampilkan`.

### Nama

- **Nickname guild bila ada, nama global bila tidak** — aturan ADR-0012:64, dipertahankan.
- **Nama diresolusi lewat `Guild.query_members(user_ids=[...])`** — satu permintaan gateway untuk sampai **100 ID**, tanpa **Server Members intent**, dan hasilnya objek `Member` yang membawa `nick`. `Guild.get_member` dari cache dipakai lebih dulu untuk anggota yang sudah ada di sana (gratis).
- **`fetch_user` bukan jalur nama.** Ia mengembalikan `User`, yang **secara struktural tidak bisa membawa nickname guild** (hanya `name` dan `global_name`), dan ia **tidak mengisi cache** — panggilan kedua untuk ID yang sama adalah panggilan HTTP kedua. Ia hanya dipakai sebagai jalan terakhir untuk ID yang tidak dikembalikan `query_members` (akun terhapus), dan yang diambil darinya hanyalah nama global.
- **Pemain yang sudah keluar guild tetap tampil.** Rating tidak hilang saat ia keluar; menyembunyikannya menggeser peringkat semua orang di bawahnya tanpa ada yang bermain, dan membuat `#N` di `/stats` menunjuk nomor yang tidak ada di klasemen.
- **Nama yang tidak bisa diambil menjadi `Pemain <id>`.** Satu baris yang gagal tidak boleh menggagalkan seluruh klasemen — pembaca tetap melihat peringkat dan ratingnya, dan tidak ada yang hilang dari urutan.

### Kepala dan kaki

- **Judul embed: `Klasemen`.** Tanpa baris ringkas populasi, tanpa menyebut pool.
- **Footer: `Rincian per pemain: /stats`.** Tanpa mention — mention memicu ping, dan satu mention per baris akan membuat setiap `/klasemen` berisik.

### Keadaan kosong

- **Belum ada satu pun pemain ber-rating dibalas dengan teks satu kalimat**, bukan embed kosong. Mengikuti preseden ADR-0012:106 ("nol game dibalas teks, bukan embed kosong"): embed kosong terbaca seperti perintah rusak.

## Alasan

- **Tanpa ambang, karena ambang tidak membeli apa pun dan memakan sesuatu.** Penanda `(provisional, ±120)` sudah menyatakan bahwa sebuah rating belum mapan — itu jawaban yang lebih tepat daripada menyembunyikan pemain, karena ia menyebut **seberapa** belum mapan. Ambang juga menciptakan pekerjaan: ADR-0012:128 mewajibkan `/stats` ikut berubah di commit yang sama, dan `CONTEXT.md` harus diamendemen di dua definisi. Memilih tanpa ambang membuat ADR-0012 tetap utuh dan kedua permukaan sudah sepakat sebelum ticket ini dikerjakan.
- **Kelayakan dibaca dari baris `player_ratings`, bukan dihitung ulang.** Klasemen, `/stats`, dan seeding turnamen tiga-tiganya bertanya "apakah pemain ini punya rating". Satu sumber jawaban, satu tempat yang bisa salah.
- **Rating provisional menampilkan bentuk panjangnya walau ia memperlebar kolom.** Bentuk ringkas (`1523±120 *`) akan menjadi format kedua untuk angka yang sama, dengan penjelasan yang harus dicari di tempat lain — sementara `(provisional, ±120)` adalah kalimat yang sudah dipahami tanpa kamus, dan `/stats` memakai bentuk yang identik.
- **Tiga kolom, bukan enam.** Baris `1523 (provisional, ±120)` sudah ~24 karakter; menambahkan rekor membuatnya ~70, dua kali lipat, sehingga jumlah pemain yang muat per layar terbelah dua. Yang dibeli angka tambahan itu kecil: rekor berating sudah punya rumah di `/stats`, dan urutan klasemen **sudah** memakai jumlah game sebagai pemutus kedua — angka itu tersembunyi di urutan, bukan hilang.
- **Code block, karena kolom yang tidak rata tidak terbaca sebagai tabel.** Di font proporsional, `#1` dan `#10` menggeser setiap kolom di kanannya dan daftar berubah menjadi kalimat. Harga yang dibayar — tidak bisa tebal/miring di dalam fence — adalah harga yang tepat untuk daftar yang tugasnya dipindai, bukan dibaca.
- **Rata kanan untuk angka, karena angka dibandingkan menurut digit terakhirnya.** `1541` dan `1412` sejajar di digit satuan membuat selisih terbaca sekilas; rata kiri memaksa mata menghitung posisi.
- **Lebar kolom dari isi, bukan tetapan.** Daftar enam pemain dengan nama pendek tidak perlu gutter kosong 20 karakter; tinggi kolom yang mengikuti isi membuat klasemen kecil tetap rapat dan klasemen besar tetap rata. Batas 24 karakter menutup kasus nama ekstrem.
- **Sanitasi backtick adalah penjagaan di batas kepercayaan, bukan kosmetik.** Ini satu-satunya tempat di platform di mana input pengguna masuk ke dalam penanda yang mengubah arti teks di sekitarnya. Tanpa sanitasi, satu pemain bisa merusak tampilan klasemen seluruh server dengan mengganti namanya sendiri — dan penyebabnya tidak akan terlihat dari pesan yang rusak.
- **Pemain yang keluar guild tetap tampil.** Keanggotaan guild berubah-ubah dan tidak ada hubungannya dengan rating. Menyembunyikan mereka membuat peringkat bergeser karena sesuatu yang bukan permainan — persis yang dilarang pemutus urutan deterministik di ADR-0012:58.
- **`Pemain <id>` alih-alih menggagalkan perintah.** ADR-0008:42 memilih "menolak dan mencatat keras" untuk **perhitungan rating**, di mana angka yang ragu lebih buruk daripada tidak ada angka. Di sini yang ragu hanyalah sebuah **label**, dan membuang seluruh daftar demi satu label adalah pertukaran yang salah.
- **Hanya saat diminta, karena pesan yang memperbarui diri tidak membeli visibilitas.** Mengedit pesan tidak memicu notifikasi (fakta terverifikasi ticket #10), jadi pesan klasemen tetap yang berubah tiap game selesai hanya terlihat oleh orang yang kebetulan menggulir ke atas. Yang dibelinya nol, dan harganya adalah ID pesan yang harus disimpan, pesan yang bisa dihapus manual, dan satu penulisan Discord di setiap akhir game.
- **Judul tanpa baris populasi.** "12 pemain (7 provisional)" menyebut fakta yang sudah terlihat dari panjang daftar dan dari sebaran penanda. Setiap baris teks tambahan ikut memakan 4096 yang justru dipakai untuk memuat lebih banyak pemain.
- **Footer menunjuk `/stats` tanpa mention.** Klasemen menjawab "siapa di atas"; pembaca yang ingin "bagaimana caranya" perlu tahu ke mana. Mention akan memicu ping pada setiap pemain di daftar setiap kali perintah dijalankan — harga yang tidak sebanding dengan satu baris bantuan.
- **Keadaan kosong dibalas teks.** Di minggu-minggu pertama server ini, "belum ada pemain dengan rating" adalah keadaan normal, dan embed berjudul dengan isi kosong terbaca seperti kegagalan, bukan seperti keadaan awal.
- **Nama lewat `query_members`, bukan lewat kolom tersimpan.** ADR-0012:64 melarang kolom `display_name` karena nama basi lebih buruk daripada satu panggilan API; larangan itu berlaku sama di sini. **Riset membalik asumsi awal ADR ini**: nickname guild **tidak** menuntut Server Members intent — `query_members(user_ids=[...])` melayani sampai 100 ID dalam **satu** permintaan gateway dan mengembalikan `Member` ber-`nick`. Jadi permukaan ini tidak membeli satu intent privileged pun. `fetch_user` **ditolak sebagai jalur nama**: hasilnya `User` tanpa `nick` secara struktural, dan ia tidak mengisi cache sehingga satu render berbiaya satu HTTP per pemain.

## Konsekuensi

- **ADR-0012 tidak diamendemen.** Kelayakan yang dipilih di sini sama persis dengan aturan yang sudah dikunci di sana ("nomor ada bila baris `player_ratings` ada"), jadi `#N` di `/stats` dan posisi baris di klasemen tidak pernah berbeda. Inilah alasan ADR-0012:128 menyebut kelayakan harus diputuskan di #22 — dan jawabannya adalah "tidak ada aturan baru".
- **`CONTEXT.md` diperluas**: istilah **Klasemen** mendapat perintahnya (`/klasemen`), bentuknya (satu kolom peringkat · rating · nama), dan aturan bahwa pemain yang sudah keluar guild tetap tampil. Istilah **Peringkat** tidak berubah — ia sudah menyatakan urutan dan kepemilikan nomor peringkat.
- **Bot tidak butuh Server Members intent hanya untuk klasemen.** `query_members(user_ids=[...])` bekerja tanpanya (sampai 100 ID per permintaan gateway), dan `Guild.fetch_member` juga tidak terdokumentasi menuntutnya. Intent tetap pertanyaan terbuka untuk keperluan lain — `/impor` menerima lampiran berkas (ADR-0011) — dan diputuskan di ticket **[Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27)**, bukan di sini.
- **`query_members` bisa timeout dan butuh websocket hidup.** Ia dibungkus `asyncio.wait_for` di discord.py dan bisa melempar `asyncio.TimeoutError`; hasilnya sebaiknya di-cache dengan TTL sendiri, karena `GUILD_MEMBER_UPDATE` tidak tersedia tanpa intent dan nickname berubah jarang. ID yang tidak dikembalikan menjadi `Pemain <id>`.
- **Kode render harus punya satu fungsi format baris** yang dipakai klasemen, supaya lebar kolom dihitung dari kumpulan baris yang benar-benar tampil — bukan ditebak per baris.
- **Sanitasi backtick adalah fungsi yang dipakai bersama** oleh setiap tempat yang menaruh nama pengguna di dalam code block. Saat ini hanya klasemen; pesan hasil analisa (ADR-0009) dan pesan pairing turnamen (ADR-0006) menyebut nama tanpa code block, jadi belum membutuhkannya.
- **Batas 4096 karakter berarti klasemen praktis tidak terpotong** pada populasi 4-16 orang, dengan ~45 karakter per baris. Penjaga luapan tetap ditulis karena bentuknya murah, bukan karena masalahnya ada — pola yang sama dengan penjaga `field.value` di ticket #7.
- **Perintah analisa ulang masih belum punya pemilik.** ADR-0012:131 mencatatnya sebagai kabut peta, dan klasemen tidak mengubah keadaan itu.

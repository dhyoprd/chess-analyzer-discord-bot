# Alur game santai: challenge lewat pesan publik ber-mention, jam baru berjalan di langkah pertama

## Konteks

Ticket [Alur game santai lewat /challenge](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/20) menutup dua lubang sekaligus.

Pertama, **tidak ada ticket yang memiliki alur `/challenge`**. Destination peta menyebutnya sebagai salah satu perintah bot, dan `CONTEXT.md` sudah mendefinisikan **Challenge**, tapi bentuk tawarannya, pilihan di dalamnya, kedaluwarsanya, dan nasib pesannya belum pernah diputuskan siapa pun. Ticket [Alur klaim akun & game impor](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/15) sering dikira rumahnya, padahal isinya pemain bayangan dan impor PGN.

Kedua, [ADR-0007](0007-pencocokan-klien-ke-game.md) memutuskan mekanisme **Buka Papan** tapi secara sadar menyerahkan pertanyaan "di mana tombol itu muncul untuk game santai" ke ticket ini — setelah [ADR-0011](0011-impor-game-eksternal-dan-klaim-akun.md) mengoreksi bahwa penitipan pertanyaan itu ke ticket #15 keliru.

Tiga fakta yang sudah terkunci membentuk jawabannya:

- **DM bot→user gagal senyap** (`50007`, `50278`, `40003`), dan hanya pesan baru ber-mention yang memicu notifikasi — edit tidak.
- **Discord tidak membatasi tombol per-pengguna**; siapa pun di channel bisa menekan tombol apa pun, jadi hak tekan harus ditegakkan app-side.
- **Jam catur tetap berjalan saat Activity ditutup** (ADR-0003), sementara "Ditinggalkan" (24 jam waktu bot hidup) praktis hanya bisa menyala **sebelum langkah pertama** — karena jam selalu habis jauh lebih dulu.

## Keputusan

### Tawaran

- `/challenge` langsung mengirim **pesan publik di channel** berisi **mention lawan** dan tombol **Terima / Tolak / Batal**. Mention adalah satu-satunya notifikasi yang bisa diandalkan; tidak ada balasan ephemeral perantara dan tidak ada DM.
- Pesannya berupa **embed ringkas**: penantang, lawan, format jam, warna, varian, dan waktu kedaluwarsa. Jauh di bawah batas `field.value` 1024.
- **Hanya `lawan:` yang wajib.** Format jam, warna, dan varian punya default.
- **Hak tekan ditegakkan app-side**: Terima/Tolak hanya untuk **lawan yang disebut**, Batal hanya untuk **penantang**; penekan lain ditolak ephemeral. Tombolnya tetap terlihat semua orang — Discord tidak menyediakan cara menyembunyikannya.
- **Tiga penolakan di pintu masuk**, semuanya balasan ephemeral: menantang **diri sendiri** (game semacam itu lolos predikat berating dan menggerakkan rating lewat hasil yang bisa diatur), menantang **bot** (mode lawan komputer tetap milik ticket [Konfigurasi mode lawan komputer](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/14)), dan menantang **bukan anggota server** (mention tidak memicu notifikasi apa pun dan tawarannya pasti kedaluwarsa).
- Seluruh pesan berbahasa **Indonesia**, konsisten dengan keputusan fondasi.

### Isi tawaran

- **Format jam dipilih dari daftar preset tetap** milik ticket [Perilaku jam catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/21); `/challenge` menyalin `base_seconds` + `increment_seconds` dari preset itu. Bila `format:` tidak diisi, defaultnya **preset "standar"** di daftar tersebut — ticket ini tidak mengarang angka preset sebelum #21 menetapkannya.
- **Warna**: penantang memilih **putih / hitam / acak**, default **acak**. Bila acak, undian dijatuhkan **saat lawan menerima**, bukan saat tawaran dibuat — kalau lebih awal, warnanya bisa terbaca dari pesan yang belum diterima.
- **Varian**: **standar atau Chess960**, default standar.
- **Posisi awal Chess960 diundi backend sekali saat game dibuat**, disimpan sebagai FEN. Tidak bisa diulang: mengulang berarti pemain menolak posisi yang tidak disukai.

### Kedaluwarsa dan jumlah

- Challenge berlaku **1 jam waktu nyata**. Ini **menyimpang** dari keluarga 24-jam-bot-hidup dengan alasan eksplisit: kedaluwarsa challenge tidak merugikan siapa pun (penantang tinggal mengajukan lagi), dan tawaran yang lahir saat bot mati memang tidak bisa diterima siapa pun — menghitung bot-hidup hanya membuatnya menggantung melewati restart tanpa pernah bisa diterima.
- **Ditegakkan malas, bukan oleh tick atau timer.** Challenge dianggap kedaluwarsa bila `expires_at` sudah lewat, diperiksa saat tombolnya ditekan dan saat penantang mengajukan challenge baru. Tidak ada timer yang harus direkonstruksi setelah restart.
- **Satu keluar, banyak masuk**: penantang hanya boleh punya satu tawaran terbuka; calon lawan boleh menampung beberapa sekaligus. Membatasi sisi masuk memaksa pemain populer menolak orang karena antrean penuh.
- **Tantangan silang boleh hidup berdampingan.** Menerima salah satu tidak membatalkan yang lain — satu penekanan tombol tidak boleh memusnahkan tawaran orang lain.
- **Boleh menantang lawan yang sedang punya game hidup**, tanpa peringatan. Q37 ADR-0006 sudah mengizinkan pemain bermain game lain saat pertandingan turnamennya menunggu, dan ADR-0007 mengasumsikan satu pemain bisa punya beberapa game hidup (karena itu ada Pemilih game).
- **Jeda 10 menit untuk pasangan yang sama hanya setelah Tolak eksplisit**, bukan setelah kedaluwarsa. Kedaluwarsa berarti lawan tidak menjawab — mungkin sedang tidur — dan menjeda penantang untuk itu menghukum orang yang salah.
- Pesan menulis **jam kedaluwarsanya** ("berlaku sampai 14:35"), **tanpa hitung mundur** dan tanpa tick yang mengeditnya. Berbeda dari ADR-0013, tidak perlu kata "sekitar": dasarnya waktu nyata, jadi jam dinding adalah kebenaran yang bisa dibaca langsung.
- **Pesan yang kedaluwarsa tanpa pernah disentuh dibiarkan apa adanya.** Tidak ada penyapu. Jam kedaluwarsa sudah tertulis di pesan, dan tombolnya tetap menolak secara ephemeral bila ditekan — ini harga yang sengaja dibayar oleh kedaluwarsa malas.

### Menerima, dan membuka papan

- **Terima langsung membuat game**, dalam **satu transaksi**: `challenges` menjadi `accepted` dan baris `games` baru dibuat bersamaan. Gagal di tengah berarti tidak ada yang berubah dan lawan bisa menekan Terima lagi. Idiom yang sama dengan ADR-0008 (hasil game + entri rating satu transaksi).
- **Jam catur belum berjalan saat game dibuat.** Jam baru mulai di **langkah pertama**. Selama jendela itu, satu-satunya penjaga adalah **"Ditinggalkan" 24 jam waktu bot hidup** yang sudah ada — tidak ada konstanta baru. Tanpa aturan ini, penerima yang menekan Terima lalu menutup Discord akan kehilangan waktu tanpa pernah melangkah, dan untuk putih justru **penantang** yang kena.
- **Pesan baru ber-mention kedua pemain dikirim saat Terima**, memuat tombol **Buka Papan**. Ini satu-satunya jalur yang benar-benar memberi tahu kedua pemain bahwa permainan sudah siap — edit tidak memicu notifikasi. Pesan challenge lama **diedit menjadi teks hasil dan tombolnya dicabut**, supaya tidak ada tombol mati yang tersisa.
- **Game tanpa langkah dibiarkan hidup 24 jam waktu bot hidup**, sama seperti game lain, dan muncul di Pemilih game kedua pemain selama itu. Tawaran yang diterima adalah kesepakatan dua orang; batas khusus yang lebih pendek berarti keluarga konstanta kedua untuk masalah yang jarang.

### Akibat pada mekanisme ADR-0007

- Syarat ADR-0007 bahwa kandidat harus **"sudah dimulai (kedua pemain duduk)" terpenuhi otomatis** untuk game santai: game lahir tepat saat Terima, jadi ia langsung masuk Pemilih game **tanpa aturan baru**.

### Model data

- **`challenges`** (named tanpa kolom di ADR-0005) mendapat: `challenger_id`, `opponent_id`, `base_seconds`, `increment_seconds`, `variant`, `color_choice`, `status` (`pending` / `accepted` / `declined` / `expired` / `cancelled`), `created_at`, `expires_at`, dan `game_id` (nullable, terisi saat diterima).
- **Baris tidak dihapus saat selesai.** Jeda 10 menit butuh riwayatnya, dan menghapusnya membuang jejak tawaran yang mungkin masih dicari pemain.
- **`games.channel_id` = channel tempat `/challenge` dijalankan**, sama dengan idiom `/impor` di ADR-0011. Pesan Buka Papan dan hasil analisa dikirim ke sana.
- Kolom penegak kedaluwarsa cukup **`expires_at`** tunggal; tidak ada kolom "sudah ditutup" di samping `status`.

### Rating

- **Game dari `/challenge` dinilai rating.** Ia `source='platform'` antara dua manusia dengan hasil papan, sehingga **predikat berating ADR-0012 sudah mencakupnya tanpa perubahan**. "Santai" hanya berarti **tidak ada taruhan turnamen**, bukan "tanpa rating". Karena bot tidak bisa ditantang, setiap game dari `/challenge` berating tanpa pengecualian yang perlu diperiksa.

## Alasan

- **Mention adalah satu-satunya notifikasi.** DM gagal senyap, edit tidak memicu ping. Setiap keputusan di atas yang menyangkut "memberi tahu seseorang" mengalir dari fakta ini: tawaran ber-mention, dan pesan Buka Papan berupa pesan baru.
- **Pesan publik, bukan ephemeral.** Tawaran yang hanya terlihat penantang menuntut langkah kedua sebelum lawan bisa diberi tahu, dan memberi satu langkah ekstra bagi orang yang sudah yakin. Untuk satu server berisi teman, keterlihatan tawaran bukan ongkos.
- **Kedaluwarsa waktu nyata, bukan waktu bot hidup.** ADR-0013 memilih waktu bot hidup karena peserta yang tidak kebagian slot **kehilangan sesuatu** saat bot mati. Challenge tidak: penantang tinggal mengajukan lagi. Memakai bot-hidup di sini akan membuat tawaran menggantung berhari-hari sementara mention-nya sudah usang.
- **Kedaluwarsa malas, bukan timer.** Timer per challenge hilang saat restart dan harus direkonstruksi; tick ADR-0013 menghitung waktu bot hidup sementara kedaluwarsa challenge memakai waktu nyata, sehingga mencampur dua dasar jam di satu loop. Satu kolom `expires_at` tidak bisa berselisih dengan dirinya sendiri.
- **Jam mulai di langkah pertama.** ADR-0003 menetapkan jam tetap berjalan saat Activity ditutup. Bila jam mulai saat Terima, penerima bisa kehilangan menit-menit pertama tanpa pernah melihat papan — dan untuk putih, yang dirugikan justru penantang, bukan penerima. Karena "Ditinggalkan" 24 jam praktis hanya bisa menyala sebelum langkah pertama, jendela itu sudah punya penjaga.
- **Pesan Buka Papan sebagai pesan baru.** Mengedit pesan challenge akan lebih hemat satu pesan, tapi edit tidak memicu notifikasi — kedua pemain bisa tidak pernah tahu permainan sudah siap. Satu pesan tambahan dibeli dengan kepastian bahwa Game benar-benar dimulai.
- **Satu transaksi saat Terima.** Dua jalur yang seharusnya melakukan hal sama adalah sumber bug yang sudah berulang di proyek ini; empat bug di #7 berasal dari akar itu. Keadaan "diterima tanpa game" tidak boleh pernah ada.
- **Penolakan dini lebih baik daripada tawaran mati.** Tiga penolakan di pintu masuk (diri sendiri, bot, bukan anggota) menutup tiga cara sebuah tawaran menghabiskan satu jam slot keluar tanpa pernah punya peluang diterima.
- **Rating tanpa pengecualian.** Karena `/challenge` hanya antar manusia dan bot bukan pilihan, setiap game darinya berating. Tidak ada cabang yang perlu diingat implementor.

## Konsekuensi

- **`challenges` di ADR-0005 mendapat bentuk konkretnya.** ADR-0005 hanya menyebut namanya; ADR ini yang memberi kolom dan artinya.
- **ADR-0007 mendapat penutup**: pertanyaan "di mana Buka Papan muncul untuk game santai" dijawab di sini — di pesan baru ber-mention saat Terima, bukan di pesan challenge. Syarat kandidat "sudah dimulai" terpenuhi otomatis untuk game santai.
- **ADR-0013 tidak diamendemen, tapi dibedakan.** Keluarga konstanta 24-jam-waktu-bot-hidup tetap utuh; kedaluwarsa challenge memakai waktu nyata dan **tidak** menjadi anggotanya. Perbedaannya harus disebut saat konstanta keluarga itu didokumentasikan, supaya tidak ada yang menambahkan challenge ke daftar itu karena "semua batas waktu di platform ini waktu bot hidup".
- **Tick platform ADR-0013 tidak menangani challenge.** Tidak ada penghitung bot-hidup yang perlu dimajukan di sini. Ticket **Perilaku jam catur** (#21) tetap satu-satunya pemilik interval dan presisi tick.
- **`/challenge` menambah satu pesan per tawaran** (embed tawaran) dan satu pesan lagi saat diterima (Buka Papan), keduanya di channel yang sama, dan keduanya ber-mention. Tidak ada DM dan tidak ada scheduled event.
- **Pesan challenge harus disimpan id-nya** untuk diedit saat selesai — pola yang sama dengan `bracket_message_id` di ADR-0006 dan pesan pendaftaran di ADR-0013.
- **`CONTEXT.md` diperbarui**: **Challenge** mendapat bentuk tawarannya, kedaluwarsanya, dan hak tekannya; **Buka Papan** menyebut di mana ia muncul untuk game santai; **Waktu bot hidup** menegaskan bahwa kedaluwarsa challenge **bukan** anggotanya; **Lawan komputer** menegaskan bahwa ia tidak dicapai lewat `/challenge`.
- **Dilengkapi oleh [ADR-0015](0015-perilaku-jam-catur.md)**: "jam baru berjalan di langkah pertama" mendapat **kolom penandanya** — `games.clock_started`, false sampai ply 1 di-commit — karena tanpa itu pemulihan setelah restart tidak bisa membedakan "jam belum berjalan" dari "jam berjalan dengan sisa tertentu". Konsekuensi eksplisitnya: **putih bebas waktu untuk langkah pertamanya**, dan itu diterima sebagai harga challenge yang adil. Penjaganya tetap **"Ditinggalkan" 24 jam waktu bot hidup**, tanpa konstanta baru. Preset **"standar"** yang di sini hanya disebut namanya kini bernilai **5+3**.

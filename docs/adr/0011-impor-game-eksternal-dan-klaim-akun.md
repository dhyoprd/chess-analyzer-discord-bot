# Impor game eksternal & klaim akun: satu game per perintah, dua jenis pemain bayangan, kode bio untuk Lichess dan klaim tak terverifikasi untuk Chess.com

## Konteks

Destination platform menyebut "analisa game eksternal: user paste link/PGN dari Lichess/Chess.com". ADR-0005 sudah menyiapkan tempatnya — `games` menampung game impor, dan pemain luar masuk sebagai **pemain bayangan** (baris `players` tanpa `discord_id`) yang bisa diklaim. ADR-0009 menyerahkan seluruh alur impor ke ticket [Alur klaim akun & game impor](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/15), dan ADR-0008 sudah memastikan game impor **tidak** mengubah rating.

Yang belum ada: siapa boleh mengimpor apa, bagaimana pemain luar dikenali, bagaimana klaim dibuktikan, dan apa yang terjadi pada game yang sudah dipindahkan. Riset dokumentasi primer Lichess dan Chess.com menutup beberapa kemungkinan sebelum keputusan diambil:

- **Lichess punya OAuth2**, dengan PKCE wajib (`S256`), **tanpa pendaftaran klien** (`client_id` bebas), tanpa refresh token (access token hidup ~1 tahun). Tapi respons penukaran token **hanya** memuat `token_type`, `access_token`, `expires_in` — **tidak ada username**; ia harus diambil lewat panggilan kedua ke `GET /api/account`.
- **Chess.com tidak punya OAuth maupun mekanisme verifikasi kepemilikan apa pun.** `chess.com/developer` 404, pubapi read-only tanpa auth, dan profil publiknya tidak punya bidang bebas seperti bio. **Tidak terdokumentasi** — bukan "belum ditemukan".
- **Tidak ada mekanisme "bukti kepemilikan akun" resmi di kedua platform.** Apa pun yang dibangun adalah skema kita sendiri, di atas API publik mereka.
- **Lichess menolak rename akun** ("usernames cannot be changed for technical and practical reasons"), kecuali sekali untuk kapitalisasi. **Chess.com mengizinkan rename**, "extremely rare", dengan `player_id` numerik yang "will never change" — tapi ketersediaannya "is not guaranteed".
- **PGN satu game bisa diambil anonim dari Lichess by ID** (`GET /game/export/{gameId}`), dan game berjalan sengaja **ditunda 3 langkah**. **Chess.com tidak punya PGN per game** — hanya per bulan (`/pub/player/{u}/games/{YYYY}/{MM}`, JSON memuat `pgn` per game, atau `.pgn` satu bulan penuh yang bisa 3 MB).
- **Pesan Discord dibatasi 2000 karakter**, sedangkan PGN game 60 langkah sudah melewatinya.

Peta memutuskan tiket ini dalam 27 pertanyaan; riset di atas mengubah dua di antaranya sebelum dijawab (Q11 dan Q12).

## Keputusan

**Dua perintah terpisah — `/impor` untuk game, `/klaim` untuk akun.**

### Impor

- **Satu game per perintah.** `/impor` menerima **tepat satu** dari dua opsi: `tautan:<url>` atau `berkas:<attachment>`. PGN **tidak** diterima sebagai teks opsi perintah — batas 2000 karakter mematahkannya pada game panjang, dan attachment Discord (25 MB) menampung PGN mana pun.
- **Game siapa pun boleh diimpor**, tanpa akun tertaut, tanpa syarat kepemilikan.
- **Berkas berisi banyak game → hanya game pertama yang diimpor**, dan balasannya menyebut berapa game ada di berkas itu. Bukan pemilih game — itu impor massal, yang ditolak.
- **Game yang belum selesai ditolak** dengan pesan jelas. Sinyalnya `Result` bernilai `*`. (Chess.com hanya menyajikan game selesai lewat arsip bulanan, jadi aturan ini praktis hanya menyentuh Lichess.)
- **Asal impor menentukan status pemain luarnya:**
  - Tautan **Lichess** → kedua sisi adalah **akun Lichess**.
  - Tautan **Chess.com** → kedua sisi adalah **akun Chess.com**.
  - Berkas **PGN** → kedua sisi hanya **nama header**, tanpa akun.
- **Atribusi otomatis**: bila salah satu sisi game cocok dengan akun yang sudah tertaut ke seorang pemain, sisi itu langsung menjadi milik pemain tersebut. Sisi lawan tetap lahir sebagai pemain bayangan.
- **Tautan Chess.com dipindai mundur maksimum 12 bulan.** Ambil `/pub/player/{u}/games/archives`, telusuri dari bulan terbaru, ambil JSON bulan itu, cocokkan URL game. Berhenti pada 12 bulan; di luar itu ditolak dengan arahan memakai `berkas:`. Alasan: URL Chess.com tidak memuat tanggal, dan pemindaian tanpa batas menjadikan bot proksi ke API mereka.
- **Duplikat mengembalikan game yang sudah ada**, beserta tautan hasil analisanya — tanpa membuat baris baru dan **tanpa** memicu analisa ulang. Dedup memakai hash langkah + PGN asli sesuai ADR-0005.
- **`games.channel_id` diisi channel tempat `/impor` dijalankan**, sehingga pipeline analisa ADR-0009 mengirim progres dan hasilnya ke sana tanpa mekanisme baru.
- **Satu impor berjalan per pemain.** Impor kedua ditolak selama yang pertama belum selesai. Ini melindungi antrean analisa FIFO dari satu pemain yang mengimpor berturut-turut.

### Klaim

- **`/klaim <platform> <username>`** — satu perintah, dua nasib: bila kode verifikasi sudah ada di bio, klaim lolos; bila belum, balasannya menampilkan kode beserta instruksi, dan pemain menjalankan perintah yang sama lagi. Tidak ada state "pending" yang harus diingat bot.
- **Kode verifikasi Lichess diturunkan deterministik**: 8 karakter dari HMAC-SHA256 atas `klaim:<discord_id>:<platform>` dengan secret dari konfigurasi produksi. Tanpa tabel, tanpa TTL, tanpa pembersihan; perintah ulang selalu memberi kode yang sama. Pemeriksaan bio menormalkan huruf besar-kecil dan spasi sebelum mencari substring.
- **Chess.com boleh diklaim tanpa pembuktian, ditandai `verified = false`** di `/stats` dan di embed. Lichess yang lolos bio mendapat `verified = true`.
- **Klaim memindahkan semua game akun itu sekaligus**, lalu akun tercatat di `player_accounts`. Baris pemain bayangannya **dipensiunkan, bukan dihapus**: kolom akunnya dikosongkan sehingga kunci `(platform, username)` bebas, dan barisnya tetap ada sebagai baris nama biasa.
- **Efek klaim bagi pemain**: `/stats` menghitung game impor itu sebagai miliknya, dan embed menampilkan nama Discord-nya alih-alih nama PGN. **Rating tidak tersentuh** (ADR-0008).
- **Bentrokan: klaim pertama yang lolos pembuktian menang.** Klaim berikutnya ditolak dengan pesan bahwa akun sudah tertaut ke pemain lain.
- **Satu akun per platform per pemain**; keunikan `(platform, username)` **global**.
- **`/klaim lepas <platform>`** menghapus tautan. **Game yang sudah dipindahkan tetap milik pemain** — tidak dikembalikan ke pemain bayangan. Setelah dilepas, akun itu bebas diklaim siapa pun yang lolos pembuktian, termasuk pemain yang tadi melepas.
- **Username disimpan huruf kecil sebagai kunci** (tampilan memakai huruf asli dari PGN/URL). **`player_id` Chess.com tidak disimpan** — dokumentasinya sendiri membuka kemungkinan pensiun.
- **Pemain bayangan tidak pernah menyatu otomatis.** Baris `lichess:john` dan baris nama `John` dari PGN tetap dua baris berbeda, selamanya.
- **Pemain bayangan dibiarkan selamanya** — tidak ada pembersihan. Sudah dikecualikan dari klasemen dan `/stats`, dan game yang menunjuk ke baris terhapus melanggar FK.

### Skema

- **`players`** mendapat dua kolom nullable: `external_platform` dan `external_username_lower`, dengan **UNIQUE gabungan**. Baris dengan kolom ini terisi adalah pemain bayangan berbasis akun; baris dengan `discord_id` terisi adalah pemain Discord.
- **`player_accounts`** menjadi catatan **klaim**: `platform`, `username_lower`, `player_id` (FK, NOT NULL), `verified` (boolean), `claimed_at`. **UNIQUE `(platform, username_lower)`** dan **UNIQUE `(player_id, platform)`**.
- Game impor adalah baris `games` biasa; tidak ada tabel `external_games` (ADR-0005).

## Alasan

- **Kode bio, bukan OAuth Lichess.** Hanya pemilik akun yang bisa menulis di bio, jadi ini bukti sungguhan — dan ia membeli hal yang sama tanpa satu pun permukaan OAuth: tanpa `client_id`, tanpa redirect URI, tanpa parameter `state`, tanpa callback HTTPS, dan tanpa menyimpan access token setahun. OAuth unggul hanya dalam satu hal: bukti diambil pada detik itu juga. Bio tidak kalah karena **Lichess tidak mengizinkan rename** — bukti yang tertulis hari ini tetap benar besok.
- **Kode deterministik, bukan acak ber-TTL.** Kode acak yang disimpan membeli satu kemampuan: membatalkan kode lama. Tidak ada yang membutuhkannya — kode terikat ke `discord_id` + platform, jadi kode orang lain tidak berguna bagi siapa pun. Determinisme menghapus tabel, TTL, dan pekerjaan pembersihan sekaligus, dan membuat "jalankan perintahnya lagi" selalu berhasil.
- **Chess.com boleh diklaim tanpa bukti, tapi bertanda.** Menolak klaim Chess.com membuat separuh game impor tidak pernah bisa diatribusikan, di satu server privat antarteman. Yang berbahaya bukan klaim tanpa bukti, melainkan klaim tanpa bukti **yang menyamar sebagai terbukti** — jadi buktinya tidak dipalsukan, hanya dilabeli.
- **Dua jenis pemain bayangan, karena buktinya dua jenis.** Tautan membawa akun — identitas yang bisa dibuktikan, di-key, dan diklaim. PGN mentah hanya membawa nama di header. Memaksakan satu bentuk untuk keduanya berarti memilih antara tidak bisa mengklaim game Lichess dengan aman, atau membuang jalur tempel-PGN sepenuhnya.
- **Tidak pernah menyatukan atas dasar nama.** "John" di PGN tidak membawa platform — tidak ada dasar apa pun untuk menyimpulkannya `lichess:john`, apalagi `chess.com:john`. Menyatukan berdasarkan nama persis adalah cara paling murah membuat dua orang berbeda menjadi satu pemain.
- **Satu game per perintah.** Impor massal menuntut paginasi API luar, dedup batch, dan pemilihan game — tiga lapisan yang tidak diminta destination. Satu game tetap memenuhi seluruh kebutuhan yang terdokumentasi.
- **Attachment, bukan teks.** Bukan preferensi gaya: batas 2000 karakter Discord membuat jalur teks gagal justru pada game yang paling layak dianalisa.
- **Tolak game berjalan.** Lichess sendiri menunda game berjalan 3 langkah untuk mencegah bot curang, dan hasilnya masih bisa berubah. Karena dedup mengembalikan baris yang sama selamanya, pemain tidak punya cara memperbaikinya.
- **Satu impor berjalan per pemain.** Bukan soal API luar — satu permintaan per perintah sudah aman — melainkan soal antrean analisa FIFO: satu pemain yang mengimpor 20 game berturut-turut menahan setiap analisa turnamen di belakangnya.
- **Pindai mundur maksimum 12 bulan.** URL Chess.com tidak memuat tanggal, jadi satu-satunya cara menemukan game adalah menyusuri arsip. Batas 12 bulan membuat kerja per perintah berhingga dan mencegah bot dipakai sebagai proksi bebas ke API Chess.com.
- **Pelepasan tidak mengembalikan game.** Mengembalikan akan menghidupkan lagi baris pemain bayangan yang sudah pensiun dan membuat statistik pemain menyusut secara mengejutkan — dua kerusakan riwayat demi satu tindakan administratif.

## Konsekuensi

- **ADR-0005 diamendemen**: pemain bayangan **tidak lagi "bisa diklaim" secara umum**. Hanya pemain bayangan **berbasis akun** yang bisa diklaim; pemain bayangan **berbasis nama** (dari PGN) tidak, karena nama bukan bukti. `players` mendapat `external_platform` + `external_username_lower`, dan `player_accounts` mendapat kolom `verified`.
- **`CONTEXT.md` diperbarui**: istilah **Impor**, **Klaim akun**, **Akun eksternal** ditambahkan, dan definisi **Pemain bayangan** dipersempit ke dua jenis dengan aturan klaim masing-masing.
- **Keterbatasan yang diketahui**: pemain yang menempel PGN-nya hari ini lalu mengklaim akun Lichess besok akan punya dua himpunan game yang tidak pernah bertemu — jalur tempel dan jalur tautan menghasilkan dua identitas. Penggabungan eksplisit tidak dibangun di sini; bila dibutuhkan nanti, ia menjadi perintah tersendiri yang memindahkan game antar-baris atas permintaan manusia.
- **Game impor masuk ke `games.channel_id` channel tempat perintah dijalankan**, sehingga hasil analisanya diposting di sana oleh pipeline ADR-0009 yang sudah ada. Tidak ada jalur pesan baru.
- **`/stats` harus membedakan game berating dari game impor.** Menampilkan keduanya sebagai satu angka akan menyesatkan pembaca tentang arti rating Glicko-2 — diserahkan ke ticket [Penyajian /stats](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/16).
- **Tombol Buka Papan untuk game santai dipindahkan ke ticket [Alur game santai lewat /challenge](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/20).** ADR-0007 menitipkannya ke sini secara keliru; di #20 pertanyaannya punya konteks, sedangkan di sini ia harus mengarang alur `/challenge` yang belum diputuskan. ADR-0007 diberi catatan arah ulang.
- **Secret HMAC adalah konfigurasi produksi baru** dan harus masuk ke `C:\ChessPlatform\.env` (ADR-0010). Bila secret berubah, seluruh kode verifikasi yang sudah ditempel di bio berubah — pemain yang klaimnya belum selesai harus menempelkan kode baru. Ini tidak merusak klaim yang sudah tersimpan.
- **Batas 25 MB attachment** adalah batas Discord; berkas PGN yang lebih besar ditolak sebelum dibaca.
- **Akun bot di Lichess tidak dikenali khusus.** Game melawan Stockfish di Lichess masuk sebagai pemain bayangan berbasis akun biasa, bukan `is_engine` — tidak ada penanda bot yang bisa diandalkan di PGN.

# Turnamen knockout: ronde mengalir, walkover dihitung dalam waktu bot hidup

## Konteks

Ticket [Alur turnamen knockout](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/10) harus menentukan bagaimana turnamen knockout berjalan dari pendaftaran sampai juara, di server Discord yang pemainnya tidak bermain serentak. Tiga kendala saling tarik-menarik:

- **Pemain tidak bisa diandalkan hadir tepat waktu.** Ini pertanyaan inti ticket, dan jawabannya menentukan seluruh bentuk turnamen.
- **Bot bisa mati kapan saja** (ADR-0003). Peserta yang "tidak datang" bisa berarti pemain kabur, **atau** bot mati. Definisi yang tidak membedakan keduanya akan menghukum pemain atas kegagalan infrastruktur — persis yang ditolak ADR-0003.
- **Turnamen knockout wajib menghasilkan tepat satu pemenang per pertandingan**, sementara game yang ditinggalkan menurut ADR-0005 justru berakhir **tanpa pemenang**.

Riset juga menemukan bahwa **tidak ada preseden yang bisa ditiru**: Lichess dan Chess.com sama-sama menjalankan Swiss/arena dengan bye, bukan gugur tunggal. Semantik knockout di sini ditemukan sendiri, bukan disalin.

## Keputusan

**Format.** Satu pertandingan = satu game; bila remis, game ulang dengan warna ditukar; bila masih remis, **armageddon**. **Putih mendapat waktu lebih banyak** (hitam 80% dari waktu putih) dan **remis berarti hitam menang** — konvensi FIDE dan Chess.com. Armageddon **tidak** mengubah rating, karena kondisinya sengaja tidak setara dan Glicko-2 mengasumsikan kondisi setara.

**Bracket.** 4–16 peserta, dilengkapi **bye** ke pangkat dua terdekat, diberikan ke unggulan teratas. Unggulan berdasarkan rating Glicko-2; pemain provisional atau belum berating diacak. **Ronde mengalir**: ronde berikutnya mulai begitu kedua pemainnya diketahui, tanpa menunggu ronde sebelumnya tuntas. Bracket **dibangun penuh saat disusun** — ronde 1 lengkap termasuk baris bye, ronde berikutnya dengan slot kosong.

**Kehadiran.** Pesan pairing terpisah per pertandingan, me-mention kedua pemain, dengan tombol **Masuk**. Pertandingan mulai saat kedua pemain sudah masuk. Discord tidak punya pembatasan tombol per-pengguna, jadi penekan yang bukan peserta ditolak secara ephemeral tanpa mengubah state.

**Batas waktu.** Batas no-show dan batas game ditinggalkan memakai **satu konstanta 24 jam waktu bot hidup**. Walkover bersifat **otomatis**, diumumkan lewat pesan tersendiri di channel. Turnamen bubar sendiri setelah **72 jam waktu bot hidup** tanpa aktivitas, di mana "aktivitas" = tekanan Masuk, hasil pertandingan, atau langkah dalam game turnamen. **Jendela pendaftaran memakai konstanta 24 jam yang sama** — lihat [ADR-0013](0013-jendela-pendaftaran-turnamen.md).

**Hasil.** `games` mencatat **kebenaran papan**; `tournament_matches.winner_id` mencatat **siapa yang maju**. Armageddon remis tetap tercatat remis di `games`; game yang ditinggalkan tetap tanpa pemenang di papan.

**Model data.** Tambah tabel induk **`tournaments`** (ADR-0005 hanya punya `tournament_players` dan `tournament_matches`, keduanya berkunci ke induk yang tidak ada). `tournament_matches` diperluas dengan `white_id`/`black_id`, `joined_white_at`/`joined_black_at`, `game_id`, `deadline_alive_seconds`, `winner_id`, `result`. Walkover dan bye **tidak** membuat baris `games` — `games` tetap berarti "permainan yang benar-benar dimainkan".

## Alasan

- **Jam bot hidup, bukan jam dinding, untuk semua batas waktu.** Ini alasan yang sama yang melahirkan definisi `Ditinggalkan` di ADR-0005, dan menerapkannya pada turnamen mencegah satu kegagalan bot menghapus seluruh turnamen. Kalau batasnya jam dinding, bot yang mati 30 jam akan men-walkover-kan hampir semua pertandingan sekaligus saat hidup lagi.
- **Ronde mengalir, bukan berurutan.** Satu pemain lambat — atau bot yang mati — tidak menahan seluruh turnamen. Dalam turnamen yang dimainkan tidak serentak, penantian berurutan bisa tak terbatas.
- **Walkover otomatis, bukan klaim manual.** Tindakan yang bisa terlewat justru akan menghukum pemain yang sudah hadir.
- **`games` = kebenaran papan.** Memaksa hasil bracket masuk ke `games` akan membuat `/stats` menghitung remis armageddon sebagai kemenangan hitam dan game yang ditinggalkan sebagai kemenangan — angka yang tidak benar di papan, dan analisa Stockfish menjadi tidak jujur.
- **Armageddon tidak dinilai rating.** Hasil dari game yang sengaja tidak setara (jam berbeda, hitam menang bila remis) adalah derau bagi Glicko-2, bukan informasi tentang kekuatan pemain.
- **Tanpa DM.** Bot tidak punya cara memeriksa lebih dulu apakah DM akan sampai, kegagalannya senyap, dan Discord memperingatkan bahwa membuka DM secara agresif bisa membuat bot diblokir dari membuka DM sama sekali. Pengingat hidup di channel tempat pemain memang melihatnya.

## Konsekuensi

- **ADR-0005 diperluas, bukan digantikan.** Tabel `tournaments` dan kolom tambahan di `tournament_matches` harus ditambahkan ke skema saat implementasi.
- **Istilah "provisional" kini didefinisikan [ADR-0008](0008-konfigurasi-glicko-2.md)**: pemain provisional adalah pemain dengan **RD ≥ 110**, dan ambang itu sama di seluruh platform termasuk seeding. Sebelumnya keputusan ini memakai kata "provisional" tanpa definisi. Pemain yang belum pernah bermain game berating juga diperlakukan sebagai provisional saat seeding — diacak.
- **Tabel `players` tetap bercampur**, dan turnamen menambah satu penyaring lagi: peserta turnamen adalah `tournament_players`, bukan kueri atas `players`.
- **Armageddon butuh bendera di `games`** yang membalik "remis" menjadi "hitam menang" **hanya untuk penentuan pemenang pertandingan** — bukan untuk hasil yang dicatat di `games`.
- **Definisi `Ditinggalkan` di `CONTEXT.md` kini punya pengecualian turnamen**, dan istilah **Pertandingan** dipisahkan dari **Game** supaya slot bracket tidak lagi bernama sama dengan satu permainan catur.
- **Satu turnamen aktif per guild** berarti turnamen yang macet memblokir guild sampai dibatalkan atau bubar sendiri — karena itu auto-abandon 72 jam ada.
- Turnamen yang dibatalkan **tetap menulis entri rating** untuk game yang sudah dimainkan, karena `rating_ledger` bersifat append-only.
- **Diamendemen oleh [ADR-0013](0013-jendela-pendaftaran-turnamen.md)**: **jendela pendaftaran** — yang di sini hanya disebut "otomatis setelah 24 jam" tanpa dasar jam — ikut dihitung **waktu bot hidup**, memakai **konstanta 24 jam yang sama** dengan batas no-show dan batas game ditinggalkan. Kolom `tournaments.registration_closes_at` (Q54) **diganti** `registration_closes_in_alive_seconds` + `registration_reminder_sent`. Invarian yang muncul: jendela pendaftaran (24 jam) dan auto-abandon (72 jam) sama-sama mulai saat turnamen dibuat, jadi **auto-abandon tidak mungkin menyala selama pendaftaran masih berjalan**. Tick yang memajukan penghitung bot-hidup ditetapkan ADR-0013 hanya sampai kontraknya; intervalnya milik ticket **Perilaku jam catur**.
- **Dilengkapi oleh [ADR-0015](0015-perilaku-jam-catur.md)**: **seluruh game turnamen memakai preset "standar" (5+3)**, tanpa pilihan dan tanpa kolom baru — satu pertandingan sudah memuat hingga tiga game, dan dua pertandingan di ronde yang sama harus bisa dibandingkan. **Armageddon mendapat angka dasarnya: 5 menit putih / 4 menit hitam, tanpa increment** (rasio 80% di sini sudah terkunci), lepas dari format game-game sebelumnya. **Armageddon boleh berakhir dengan cara apa pun**: skakmat dan menyerah dibaca apa adanya dari papan, bahan tak cukup → hitam menang. Aturan "remis = hitam menang" adalah **pembaca hasil akhir**, bukan larangan game berakhir dengan cara lain — sehingga `games` tetap kebenaran papan sementara `tournament_matches.winner_id` tetap memutuskan siapa maju.

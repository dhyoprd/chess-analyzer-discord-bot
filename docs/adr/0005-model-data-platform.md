# Model data platform: satu SQLite relasional, pemain bayangan di dalam `players`, game hidup dan arsip dalam satu tabel

## Konteks

Ticket [Model data platform](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/9) harus menentukan satu skema yang menampung seluruh platform — pemain, game, langkah, analisa, turnamen, rating — sekaligus memblokir empat ticket lain (#10, #11, #12, #14) yang menunggu bentuknya. Beberapa kebutuhan saling tarik-menarik: game impor dari Lichess/Chess.com tidak punya ID Discord, game lawan komputer tidak punya dua manusia, dan ADR-0002 mewajibkan game berjalan pulih setelah restart.

## Keputusan

Satu database **SQLite** diakses lewat **SQLAlchemy 2.1 async + Alembic**, dengan bentuk berikut:

- **`players`** ber-PK surrogate (`id` integer), `discord_id` **nullable** dan UNIQUE. Pemain luar (nama di PGN) menjadi **pemain bayangan** — baris `players` tanpa `discord_id`, dikecualikan dari klasemen, bisa diklaim nanti. Lawan komputer juga baris `players`, ditandai `is_engine`.
- **`games`** menampung game **hidup dan arsip sekaligus**, dibedakan kolom `status`. Baris dibuat saat game dimulai, memuat FEN, giliran, `channel_id`, dan state jam.
- **`moves`** satu baris per ply. **`analyses`** entitas tersendiri (bisa dijalankan ulang), dan eval/klasifikasi per langkah menempel pada **analisa**, bukan pada langkah.
- **`rating_ledger`** mencatat setiap perubahan Glicko-2 per game, ber-scope **pool**; **`player_ratings`** menyimpan rating terkini per pool untuk klasemen.
- **`challenges`**, **`tournament_players`**, **`tournament_matches`**, **`player_accounts`**, **`bot_uptime`**, dan log transisi jam melengkapi model.
- SQLite berjalan dalam **WAL** dengan satu jalur tulis terserialisasi.

## Alasan

- **Pemain bayangan, bukan tabel `external_games` terpisah.** Satu tabel `games` berarti satu jalur kode untuk `/stats`, klasemen, dan pipeline analisa. Alternatifnya memaksa setiap kueri menggabungkan dua sumber selamanya.
- **Satu tabel `games` untuk hidup dan arsip.** ADR-0002 sudah menuntut state bertahan lintas restart, jadi state game *harus* ada di database. Memisahkan tabel hidup/arsip menambah logika pemindahan tanpa membeli apa pun yang terbukti dibutuhkan.
- **Klasifikasi menempel pada analisa.** Keputusan bahwa analisa bisa dijalankan ulang hanya bermakna kalau hasil analisa lama tidak ditimpa. Menaruh eval di `moves` akan membuat setiap analisa ulang menghancurkan hasil sebelumnya.
- **Rating ber-scope pool sejak awal.** Ticket #11 akan memutuskan pool mana yang ada (satu global, atau per format jam ala Lichess). Membawa dimensi pool sekarang berarti #11 tidak menuntut migrasi dan backfill atas seluruh ledger.
- **`player_ratings` terpisah dari ledger.** Klasemen butuh rating *terkini*; indeks pada tabel riwayat tidak melayani itu. Ledger tetap kebenaran yang bisa diaudit, `player_ratings` yang diindeks.
- **greenlet 3.5.6 punya wheel `cp314-win_amd64`** (diverifikasi langsung saat ticket ini). Inilah yang menghapus risiko yang dulu menjadikan `aiosqlite` pilihan aman, dan membuka jalan ke ORM + migrasi berversi.

## Konsekuensi

- Tabel `players` bercampur akun Discord, pemain bayangan, dan lawan komputer. Setiap kueri yang menampilkan "pemain manusia di server ini" wajib menyaring — ini sumber bug yang harus dijaga.
- `analyses` + eval per langkah per analisa menjadi tabel terbesar; menjalankan ulang analisa berkali-kali menumbuhkannya dengan cepat.
- Skema hidup dan arsip dalam satu tabel berarti kueri `/stats` menyentuh tabel yang juga menampung data panas. Indeks yang dipilih (tiga indeks inti) dibuat untuk itu.
- "Ditinggalkan" **mengecualikan downtime bot** (dihitung dari waktu bot benar-benar hidup, memakai `bot_uptime`), supaya bot yang mati 30 jam tidak menghukum pemain atas kegagalan infrastruktur — konsisten dengan alasan ADR-0003.
- Definisi **Ditinggalkan** di `CONTEXT.md` diperbarui mengikuti keputusan ini.
- **Diamendemen oleh [ADR-0007](0007-pencocokan-klien-ke-game.md)**: aturan "klien mencocokkan diri lewat `channel_id` + `status=playing`" digantikan oleh identitas pemain terverifikasi + rujukan game eksplisit. Kolom `games.channel_id` tetap ada untuk menempatkan pesan bot, tapi bukan untuk mencocokkan klien.
- **Diperluas oleh [ADR-0008](0008-konfigurasi-glicko-2.md)**: `rating_ledger` menyimpan state penuh (rating, RD, volatilitas sebelum dan sesudah, untuk kedua pemain), dan `player_ratings` menyimpan rating, RD, volatilitas, jumlah game berating, serta waktu game berating terakhir. Pool tunggal berkunci `"global"`. Kedua tabel karena itu menuntut kolom yang belum ada di sini.
- **Diamendemen oleh [ADR-0011](0011-impor-game-eksternal-dan-klaim-akun.md)**: "pemain bayangan bisa diklaim nanti" **tidak berlaku umum**. Hanya pemain bayangan **berbasis akun** (`external_platform` + `external_username_lower` terisi, berasal dari tautan Lichess/Chess.com) yang bisa diklaim; pemain bayangan **berbasis nama** (dari header PGN) tidak, karena nama bukan bukti kepemilikan. `players` mendapat kolom `external_platform` dan `external_username_lower` dengan UNIQUE gabungan, dan `player_accounts` — yang di sini baru disebut namanya — menjadi catatan **klaim** dengan `platform`, `username_lower`, `player_id`, `verified`, dan `claimed_at`.
- **Diperluas oleh [ADR-0012](0012-penyajian-stats.md)**: `games` mendapat tiga kolom fakta — **`source`** (`platform` / `import` / `engine`, NOT NULL **tanpa default**), **`is_armageddon`** (boolean, NOT NULL default false), dan **`result`** (`white` / `black` / `draw` / `none`, NOT NULL; `none` = ditinggalkan). Semuanya dibutuhkan predikat **berating** dan baris komposisi `/stats`: tanpa `source`, game impor yang kedua sisinya sudah diklaim tidak bisa dibedakan dari game yang dimainkan di platform ini; tanpa `is_armageddon`, syarat "bukan armageddon" di ADR-0008 tidak bisa dievaluasi sama sekali; tanpa `result`, "hasil papan ada" — yang membedakan remis dari game ditinggalkan — tidak punya sumber. `source` sengaja **tanpa default** supaya jalur pembuatan game yang lupa mengisinya gagal keras, bukan diam-diam menjadi `platform` dan ikut dinilai rating.
- **Diperluas oleh [ADR-0014](0014-alur-game-santai.md)**: **`challenges`** — yang di sini hanya disebut namanya — mendapat kolomnya: `challenger_id`, `opponent_id`, `base_seconds`, `increment_seconds`, `variant`, `color_choice`, `status`, `created_at`, `expires_at` (waktu nyata), dan `game_id` nullable. Baris **tidak dihapus** saat selesai, karena jeda 10 menit setelah penolakan butuh riwayatnya.

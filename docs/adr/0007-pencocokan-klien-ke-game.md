# Pencocokan klien ke game: identitas pemain + rujukan game, bukan channel atau instance

## Konteks

ADR-0005 memutuskan klien Activity mencocokkan diri ke game lewat **`channel_id` + `status=playing`**, dan secara eksplisit menolak `instance_id` sebagai kunci karena ia berubah setiap Activity dibuka. Aturan itu cukup selama satu channel hanya menampung satu game berjalan.

Ticket [Alur turnamen knockout](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/10) merusak asumsi itu lewat dua keputusannya: turnamen berlangsung di **satu channel** (Q32) dan ronde **mengalir** (Q4), sehingga turnamen 16 pemain bisa menampilkan 8 game berjalan serentak di channel yang sama. Ditambah Q37 (pemain boleh bermain game lain saat pertandingan turnamennya menunggu), `channel_id` + `status=playing` tidak lagi mengidentifikasi satu game.

Ticket [Pencocokan klien ke game saat banyak game berjalan di satu channel](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/18) mencari penggantinya. Riset menemukan tiga fakta yang membentuk jawabannya:

- Klien Activity menerima `instanceId` (selalu ada), plus `channelId`, `guildId`, `customId`, `referrerId`, `locationId` — semuanya nullable.
- Rujukan kustom (`custom_id`) **hanya** sampai ke klien lewat URL deep link `discord.com/activities/<app-id>?custom_id=…`. Tombol pesan yang membuka Activity (respons interaksi bertipe `LAUNCH_ACTIVITY`) **tidak punya mekanisme terdokumentasi** untuk membawa `custom_id` masuk.
- Activity Instance API (`GET /applications/{id}/activity-instances/{instance_id}`) butuh **bot token**, mengembalikan `users` sebagai daftar ID mentah (tanpa nama panggilan), dan **tidak ada endpoint daftar** — instance hanya bisa dibaca bila `instance_id` sudah diketahui.

## Keputusan

**Klien dikenali lewat identitas Discord yang terverifikasi, dan game dipilih lewat rujukan eksplisit — bukan lewat channel atau instance.**

- **Identitas** diperoleh lewat OAuth `identify`: klien memanggil `authorize()` → kode → backend menukarnya di `https://discord.com/api/oauth2/token` → `GET /users/@me`. Backend memercayai token hasil pertukaran, bukan klaim klien.
- **Set kandidat**: game di mana pemain terverifikasi itu **peserta**, sudah dimulai (kedua pemain duduk), dan `status=playing`.
- **Satu game hidup → auto-attach**, dengan header menyebut lawan dan warna. **Lebih dari satu → pemilih game**, ditandai "Turnamen — Ronde N" versus "Santai", dan "Lawan komputer" untuk game melawan Stockfish.
- **Sesi terikat ke satu game**, dengan tombol **ganti game** bila pemain punya game hidup lain.
- **Tidak ada game hidup → layar kosong + arahan.** Pemain turnamen yang sudah menekan **Masuk** tapi lawannya belum melihat "Menunggu lawan menekan Masuk" sebagai **banner** di atas papan, bukan layar kosong.
- **Binding tidak disimpan.** Ia diturunkan ulang tiap koneksi dari identitas + kueri DB. Klien memegang pilihannya di memori dan menyatakannya ulang saat menyambung ulang; server memvalidasi bahwa pemain adalah peserta game itu. Menutup-lalu-membuka Activity adalah konteks baru, jadi pemilih muncul lagi.
- **Langganan WebSocket dikunci ke game**, bukan ke instance. Dua pemain di instance berbeda tetap berbagi satu game.
- **Tombol Masuk tetap hanya mencatat kehadiran.** Papan dibuka lewat tombol **Buka Papan** yang muncul setelah kedua pemain hadir.
- **Non-peserta tidak bisa menempel** ke game orang lain. Menonton bukan bagian dari keputusan ini.
- **Klien yang menyebut game yang bukan miliknya, atau game yang sudah berakhir, ditolak** dan dikembalikan ke pemilih — tidak pernah diam-diam menempel ke game lain.

## Alasan

- **`channel_id` bukan sekadar tidak membantu — ia bisa salah.** Activity berjalan di voice channel, sementara game turnamen hidup di channel teks tempat `/turnamen` dijalankan. Dua channel yang berbeda, jadi memfilter dengan channel bisa menolak game yang benar. Endpoint instance pun tidak mengembalikan tipe channel (`location.kind` hanya `'gc'` atau `'pc'`), sehingga klien tidak bisa memeriksa sendiri.
- **Identitas adalah satu-satunya sinyal yang selalu tersedia dan tidak bisa dipalsukan.** Rujukan `custom_id` tidak bisa diandalkan karena tombol pesan — jalur pembuka yang alami untuk game turnamen — tidak dapat membawanya. Bergantung padanya berarti bergantung pada perilaku yang belum terdokumentasi.
- **Menurunkan ulang binding, bukan menyimpannya, memenuhi ADR-0002 tanpa biaya.** Restart bot tidak merusak apa pun karena tidak ada yang disimpan; tidak ada tabel sesi, tidak ada TTL, tidak ada lifecycle untuk dibersihkan. Ini konsisten dengan penolakan ADR-0005 atas `instance_id` sebagai kunci penyimpanan.
- **Pemilih, bukan tebak otomatis.** #10 Q37 secara eksplisit mengizinkan pemain bermain game lain saat pertandingan turnamennya menunggu. Menebak "game terbaru" bisa memasukkan pemain ke game yang salah tanpa ia sadar — kegagalan yang mahal saat turnamen berjalan.
- **Masuk dan Buka Papan tetap dua tindakan.** #10 Q5 mendefinisikan pertandingan mulai saat **kedua** pemain menekan Masuk; menggabungkan Masuk dengan membuka papan akan mengaburkan definisi kehadiran yang sudah dikunci.
- **Hanya peserta.** Membatasi pemilih ke game milik pemain membuat kueri sederhana dan menutup pertanyaan privasi. Menonton adalah fitur tersendiri, bukan konsekuensi dari pencocokan.

## Konsekuensi

- **ADR-0005 diamendemen**: aturan "klien mencocokkan diri lewat `channel_id` + `status=playing`" digantikan. Kolom `games.channel_id` tetap ada dan tetap berguna untuk menempatkan pesan bot, tapi **bukan** untuk mencocokkan klien.
- **Verifikasi instance Activity tidak dipakai** untuk otentikasi klien. Bila anti-curang ingin diperkuat nanti, `GET /applications/{id}/activity-instances/{instance_id}` tersedia sebagai lapisan tambahan dengan bot token — tapi ia bukan syarat, dan ia tidak bisa dipakai untuk menemukan instance (tidak ada endpoint daftar).
- **Kehadiran dan pembukaan papan terpisah**: pesan pairing turnamen butuh tombol **Buka Papan** selain tombol **Masuk**. Di mana tombol itu muncul untuk game santai diputuskan ticket [Alur klaim akun & game impor](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/15).
- **Activity tidak lagi bisa diasumsikan satu-per-game.** Beberapa instance bisa menempel ke game yang sama; backend harus menyiarkan state per game, bukan per instance.
- **Daftar game hidup disiarkan lewat WebSocket**, sehingga pemain yang menerima challenge saat Activity terbuka melihat game baru tanpa menutup-buka Activity.
- **`CONTEXT.md` diperbarui**: definisi **Instance** dikoreksi (backend tidak memakainya untuk mengenali klien), dan istilah **Papan**, **Pemilih game**, serta **Buka Papan** ditambahkan.

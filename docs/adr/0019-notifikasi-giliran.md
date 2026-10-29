# Notifikasi giliran: pesan baru ber-mention di channel game, satu kali per ply, dievaluasi tick platform

## Konteks

Ticket [Notifikasi giliran saat Activity tertutup](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/17) bertanya bagaimana bot memberi tahu pemain bahwa gilirannya tiba saat Activity tertutup. Body-nya mengajukan tujuh pertanyaan: media, ambang, isi, peringatan waktu hampir habis, anti-spam, perilaku setelah bot mati, dan preferensi pemain.

Yang sudah terkunci dan tidak dibuka ulang:

- **DM bot→user ditolak** (ADR-0006:34, ADR-0014). Gagal senyap (`50007`, `50278`, `40003`), dan membuka DM secara agresif bisa membuat bot **diblokir dari membuka DM sama sekali**. Mention adalah satu-satunya notifikasi yang bisa diandalkan; **mengedit pesan tidak memicu notifikasi apa pun** (ADR-0009:59, ADR-0014:70).
- **Langganan WebSocket dikunci ke `game_id`**, bukan ke instance, dan sesi ganda ke game yang sama diizinkan (ADR-0007:26). Sesi hanya bisa menempel bila pemain adalah peserta game itu.
- **Tick platform 1 detik** (ADR-0013, angka dan presisi dikunci ADR-0015) sudah berjalan dan sudah menjadi jam catur itu sendiri. Jam, Pendaftaran, dan Ditinggalkan semuanya mengukur terhadap satu penghitung bot-hidup yang sama.
- **Satu proses Python** menjalankan bot dan FastAPI dalam satu event loop (ADR-0010). Jadi pendaftaran langganan WebSocket hidup di memori proses yang sama dengan tick.
- **Jam tetap berjalan saat Activity ditutup**, dan berhenti saat bot mati (ADR-0003, ADR-0015).

**Premis di body ticket yang perlu dikoreksi: "notifikasi tertunda bisa menumpuk begitu bot hidup lagi".** Tidak bisa. Langkah hanya masuk lewat Activity, dan Activity hanya bisa bicara ke backend; backend mati berarti tidak ada langkah yang bisa masuk, dan jam tidak maju. Keadaan setiap game saat boot **identik** dengan keadaannya saat mati (kecuali jendela flush `bot_uptime` sampai 60 detik). Tidak ada giliran yang "berpindah saat bot mati", jadi tidak ada antrean notifikasi yang bisa menumpuk — kecuali kalau kita sengaja membangun outbox, yang justru ditolak di sini.

**Kapabilitas baru yang ticket ini pakai, dan yang tidak dipakai ticket mana pun sebelumnya: backend tahu siapa yang sedang terhubung.** ADR-0007 sudah mengunci bahwa klien menempel dengan identitas terverifikasi dan berlangganan ke `game_id`. Artinya "Activity tertutup" bukan tebakan — ia fakta yang bisa dibaca dari daftar langganan. Ini yang membuat ticket ini jauh lebih kecil dari yang tersirat di body-nya: tidak perlu timer per game, tidak perlu kolom skema, dan tidak perlu mesin anti-spam, karena **giliran hanya bisa dimainkan dari Activity**, sehingga pemain yang terhubung dan tidak melangkah adalah kasus yang berbeda dan jauh lebih jarang daripada pemain yang terputus.

## Keputusan

**Bot mengirim satu pesan baru ber-mention di channel game saat giliran seorang pemain manusia tiba dan ia tidak mengambilnya, dengan aturan tunggal: satu ping per ply, dievaluasi tiap tick platform.**

### Kapan ping dikirim

Satu syarat, dua ambang. Untuk pemain manusia yang sedang giliran:

| Keadaan pemain | Syarat | Ambang |
|---|---|---|
| **Tidak terhubung** — nol langganan WebSocket hidup untuk `game_id` ini atas namanya | sudah tidak terhubung selama `putus` | `putus = min(10 detik, sisa₀/10)` |
| **Terhubung** — ≥1 langganan hidup | sudah diam selama `diam` sejak giliran dimulai | `diam = min(300 detik, sisa₀/4)` |

- **`sisa₀` adalah sisa waktu pemain itu pada saat giliran dimulai**, dihitung sekali dari `white_centis`/`black_centis` + `clock_committed_at` menurut ADR-0015, lalu **dibekukan untuk seluruh giliran**. Nilai itu disimpan di memori bersama `pinged_ply`, dan tidak ada yang ditulis ke database per detik.
- **Kenapa dibekukan, bukan dibaca ulang tiap tick.** Ambang yang dihitung dari `sisa` yang terus menyusut **mengurai dirinya sendiri**: syarat `elapsed ≥ (sisa₀ − elapsed)/4` setara dengan `elapsed ≥ sisa₀/5`, jadi ping justru menyala di 20% jam, bukan 25% — dan setiap perubahan rumus menggeser angka sebenarnya tanpa terlihat. Membekukan `sisa₀` membuat tabel di bawah ini benar apa adanya, dan membuat ambangnya satu fakta per giliran alih-alih fungsi dari waktu.
- **Yang lebih dulu tercapai menang**, dan **hanya satu ping** yang dikirim untuk giliran itu. Pemain yang terhubung lalu terputus di detik ke-30 tetap mendapat satu ping saat terputus, bukan dua.
- **"Tidak terhubung" diukur dari saat koneksinya habis**, bukan dari awal giliran. Pemain yang Activity-nya berkedip di tengah giliran tidak langsung diping; ia diberi `putus` detik untuk kembali. Sebaliknya pemain yang memang sudah pergi sejak awal giliran diping setelah `putus`.
- **Keduanya mengecil mengikuti jam**, karena ambang tetap lebih panjang dari seluruh jam game adalah ping yang datang setelah game selesai. Nilainya untuk keenam preset ADR-0015 dan armageddon:

| Format | Jam awal | `putus` | `diam` |
|---|---|---|---|
| 1+0 | 60 s | **6 s** | **15 s** |
| 3+0 | 180 s | 10 s | 45 s |
| 3+2 | 180 s | 10 s | 45 s |
| 5+3 (standar) | 300 s | 10 s | 75 s |
| 10+0 | 600 s | 10 s | 150 s |
| 10+5 | 600 s | 10 s | 150 s |
| Armageddon putih | 300 s | 10 s | 75 s |
| Armageddon hitam | 240 s | 10 s | 60 s |

- **Plafon 300 detik praktis tidak mengikat.** Sisa terbesar **saat giliran pertama** adalah 600 detik (preset terpanjang), sehingga `diam` bernilai paling banyak 150 detik. Jam Fischer bisa **tumbuh melewati waktu dasarnya** bila pemain melangkah lebih cepat daripada increment-nya, jadi sisa bisa melampaui 600 detik di kemudian hari — tapi untuk menyentuh plafon 300 detik, jam harus sudah tumbuh melewati **20 menit**, yang tidak tercapai di preset terpanjang kita (10+5) kecuali setelah ratusan langkah. Tabel di atas karena itu menampilkan keadaan giliran pertama, bukan batas teoretis yang tak pernah tercapai.

### Satu ping per ply, dan hanya untuk ply yang lahir di proses ini

- **Penanda `pinged_ply` per game, di memori proses.** Sebuah ping hanya dikirim bila ply yang sedang berjalan belum pernah dipingi. Setelah terkirim, ply itu tidak akan dipingi lagi — tidak ada pengulangan, tidak ada pengingat kedua.
- **Saat boot, penanda di setiap game hidup diinisialisasi ke ply yang sedang berjalan.** Akibatnya **ply yang menggantung saat bot hidup lagi tidak pernah diping.** Ini bukan kelonggaran: giliran itu lahir sebelum bot mati, pemainnya sudah dipingi saat itu kalau memang perlu, dan tidak ada apa pun yang memburuk selama bot mati karena jam pun tidak bergerak. Detik ke-5 giliran sebelum crash sama dengan detik ke-5 giliran sesudah boot.
- **Konsekuensi yang diterima:** giliran yang lahir di antara tick terakhir sebelum mati dan tick pertama sesudah hidup — jendela paling lebar satu detik — kehilangan ping-nya untuk selamanya. Pemainnya tidak kehilangan waktu, hanya satu pemberitahuan.
- **Ply 0 tidak pernah diping — `clock_started` adalah syarat tersendiri.** Aturan "hanya ply yang lahir di proses ini" **tidak** menutup kasus ini: game yang dibuat di tengah sesi lahir di proses yang sedang berjalan. Jadi syaratnya eksplisit: ping hanya dievaluasi bila `clock_started` menyala. Alasannya, jam belum berjalan (ADR-0015), dan ADR-0014 sudah mengirim pesan **Buka Papan** ber-mention kedua pemain saat challenge diterima — ping beberapa detik kemudian hanya mengulang pesan yang baru saja dikirim.
- **Game lawan komputer ikut diping.** Giliran mesin selalu dijawab dalam hitungan milidetik (ADR-0018: `depth 2` = 0,4 ms ditambah jeda 600 ms), jadi ping hanya mungkin terjadi bila pemain manusianya sendiri yang tidak kembali. Ia satu-satunya manusia di meja, dan tanpa ping ia kalah karena waktu setelah menutup Activity sebentar — persis kegagalan yang ADR-0015 khawatirkan.

### Di mana dievaluasi

- **Menumpang tick 1 detik ADR-0013/ADR-0015**, sebagai langkah tambahan setelah penghitung dimajukan dan jendela yang habis ditutup. Tidak ada timer kedua, tidak ada `asyncio.sleep` terpisah, dan presisi yang didapat adalah presisi tick yang sudah ada.
- **Tidak ada handle timer per giliran.** Timer per game menuntut pembatalan yang benar di setiap jalur langkah, penutupan, dan restart — tiga tempat yang sudah pernah menjadi sumber bug di proyek ini.
- **Daftar langganan WebSocket dibaca langsung dari memori proses.** ADR-0010 sudah memastikan bot, tick, dan WebSocket hidup di satu event loop, jadi ini pembacaan struktur data, bukan IPC.

### Isi dan bentuk pesan

- **Pesan baru di `games.channel_id`**, channel tempat game itu memang hidup: channel `/challenge`, channel `/komputer`, atau channel pesan pairing turnamen.
- **Mention di `content`, bukan di dalam embed.** Ini bukan preferensi gaya: apakah `<@id>` di dalam `description`, `field.value`, atau `title` memicu ping **tidak terdokumentasi sama sekali**. Dokumentasi Discord membatasi cakupan `allowed_mentions` pada "mentions in the message content, or the content of components attached to that message", dan syarat "the mention format must also be present in the content of the message or its components" — **embed tidak disebut** di kedua enumerasi itu. Sebaliknya untuk komponen, ping memang didokumentasikan eksplisit. Menaruh mention di embed berarti menggantungkan seluruh mekanisme pada perilaku yang tidak dijanjikan; di `content`, perilakunya adalah yang sudah dipakai ADR-0006/0009/0013/0014/0015/0016.
- **`allowed_mentions` dibatasi ke satu ID pemain itu saja**, bentuknya `{"users": ["<id>"]}` **tanpa `parse`** — `parse` saling eksklusif dengan field lain menurut dokumentasi. Ini bukan formalitas: nama lawan masuk ke teks pesan dan bisa berasal dari header PGN pemain bayangan (ADR-0011), jadi satu nama berisi `@everyone` menjadi mention yang tidak pernah dimaksudkan.
- **Jangan kirim `AllowedMentions()` kosong, dan jangan andalkan default discord.py.** `AllowedMentions.__init__` mengisi keempat field dengan sentinel `_FakeBool()` yang truthy, sehingga `AllowedMentions()` **mengizinkan mention pengguna, peran, dan `@everyone` sekaligus** — kebalikan dari yang namanya tersirat. Ini jebakan yang sama bentuknya dengan `UCI_LimitStrength` di ADR-0018: objek yang "terpasang" tidak membuktikan efek yang diinginkan.
- **`SUPPRESS_NOTIFICATIONS` (flag `1 << 12` = 4096) tidak boleh dipasang.** Ia mematikan push dan desktop notification untuk pesan itu — termasuk notifikasi mention. Satu `silent=True` yang tidak sengaja akan membuat seluruh mekanisme ini bisu tanpa satu pun error muncul, dan gejalanya persis "ping tidak pernah datang".
- **Isi:** `<mention> Giliranmu — sisa <mm:ss>, melawan <nama lawan>.` ditambah tombol **Buka Papan** (ADR-0007, ADR-0014). Ping yang tidak menawarkan jalan ke papan adalah ping setengah; tombolnya jalur yang sudah dikunci.
- **Tanpa thumbnail papan.** ADR-0017 sudah menetapkan papan hanya di pesan analisa; merender 14 ms untuk gambar yang tidak dipakai memutuskan apa pun adalah biaya tanpa manfaat.
- **Tidak ada peringatan waktu hampir habis yang terpisah.** Sisa waktu sudah menyertai ping, dan ping itu sendiri datang saat masih ada waktu untuk bertindak. Ambang waktu tersendiri (25%, 10%, satu menit) berarti satu mesin ambang lagi yang harus diputuskan per preset, dan ping kedua untuk pemain yang sudah diberi tahu.

### Siklus pesan

- **Satu pesan ping hidup per game pada satu waktu.** Pesan itu **dihapus di jalur commit langkah**, yaitu saat giliran yang diumumkannya berakhir — bukan saat ping berikutnya dikirim. Kalau dihapusnya menunggu ping berikutnya, game yang lawannya terhubung dan cepat melangkah akan meninggalkan rantai "Giliranmu" basi di channel; di turnamen 8 game serentak itu puluhan pesan bohong per malam.
- **Penghapusan juga terjadi di jalur tutup game**, sebelum pesan hasil ADR-0015 dikirim. Pesan yang mengklaim giliran pada game yang sudah selesai adalah kebohongan yang tinggal di channel, dan pesan hasil yang muncul di atasnya akan terbaca sebagai lanjutannya.
- **Jaring pengaman saat mengirim:** bila masih ada pesan ping terlacak untuk game itu, ia dihapus lebih dulu. Ini hanya bisa terjadi kalau penghapusan di commit langkah gagal.
- **Pesan yatim dibiarkan.** Bot restart menghilangkan `message_id` dari memori, sehingga pesan ping lama tidak bisa dihapus dan tertinggal di channel. Isinya masih benar — giliran memang tidak berubah sepanjang bot mati — dan tidak menumpuk dalam pemakaian normal. Menyapunya saat boot menuntut `history()` per game dan berisiko menghapus pesan bot lain tanpa penanda yang tahan restart.
- **Semua I/O Discord terjadi setelah transaksi database**, tidak di dalamnya. Pola yang sama dengan ADR-0018 untuk panggilan engine: transaksi SQLite tidak boleh ditahan selama panggilan jaringan.

### Kegagalan

- **Pengiriman gagal dicatat keras, ditandai sudah diping, dan tidak dicoba ulang.** Percobaan ulang hanya akan menabrak kegagalan yang sama (channel terhapus, izin dicabut), dan tanpa penanda, tick 1 detik menjadi loop panas selama sisa game.
- **Kegagalan senyap yang paling mungkin bukan error, melainkan pesan yang terkirim tanpa ping.** Tiga jalurnya sudah dikenal dan semuanya harus diuji: mention yang diletakkan di dalam embed (tidak dijanjikan memicu ping), `AllowedMentions()` kosong (justru mengizinkan semua, jadi bukan penyebab bisu), dan `silent=True` / `SUPPRESS_NOTIFICATIONS` (mematikan push termasuk mention). Tidak satu pun memunculkan exception — pesan tetap terkirim dan terlihat benar di channel. Karena itu uji terima implementasinya adalah **"apakah ponsel berbunyi"**, bukan "apakah pesannya muncul".
- **Push notification tidak dijamin sampai.** Dokumentasi Discord menyatakan mention "does not guarantee a push notification will be sent", dan pengguna bisa mengubah setelan sehingga hanya menerima badge. Ini batas platform, bukan bug kita; pesan di channel tetap menjadi catatan yang benar.
- **Penghapusan gagal tidak menggagalkan langkah maupun penutupan game.** Langkah sudah commit sebelum I/O Discord dimulai; kegagalan hapus hanya meninggalkan pesan basi sampai restart berikutnya.
- **Pemain yang tidak bisa disebut tetap dipingi tanpa mention.** Pemain yang sudah keluar guild tidak membutuhkan pemeriksaan keanggotaan: mention-nya tetap dirender dan tidak membunyikan apa pun, yang memang hasil yang benar. Pemain bayangan (`discord_id` NULL) tidak pernah sampai ke jalur ini karena game impor tidak punya jam berjalan. **Tidak ada `fetch_member`** — itu satu panggilan HTTP per ping demi membedakan dua keadaan yang hasilnya sama.

### Yang tidak dibangun

- **Tanpa preferensi pemain — tidak ada `/setelan`, tidak ada kolom di `players`.** Ping giliran adalah satu-satunya mekanisme yang mencegah pemain kalah karena lupa, dan di satu guild berisi orang yang saling kenal tidak ada yang membutuhkan tombol mematikannya. Yang menopang ini bukan selera: **bot tidak bisa membaca setelan notifikasi pengguna sama sekali** — tidak ada endpoint user-settings, dan `PATCH /users/@me` hanya menerima username/avatar/banner. Jadi setelan per pemain hanya bisa menjadi sakelar milik kita sendiri, bukan cermin preferensi Discord yang sebenarnya.
- **Tidak ada kolom baru di skema.** Penanda ping dan waktu putus hidup di memori. Ini aman justru karena boot tidak mem-ping: kehilangan penanda tidak bisa menghasilkan ping ganda.
- **Tidak ada outbox, antrean, atau tabel notifikasi.** Alasannya di Konteks: tidak ada yang bisa menumpuk.
- **Satu ping per game, bukan digabung per pemain.** Pemain yang sedang giliran di dua game menerima dua ping. Menggabungnya menuntut satu pesan agregat yang harus diperbarui tiap kali salah satu game berpindah — dan karena edit tidak memicu notifikasi, pesan agregat itu bisu.

## Alasan

- **Koneksi, bukan tebakan.** "Activity tertutup" adalah fakta yang sudah dimiliki backend (ADR-0007). Tanpa memakainya, ping harus dikirim ke semua orang yang tidak melangkah setelah N detik, termasuk yang sedang menatap papan dan berpikir. Kebisingan itu bisa dihindari gratis, jadi dihindari.
- **Dua ambang, bukan satu.** Pemain terputus hampir pasti tidak melihat apa pun dan perlu dipanggil cepat — 10 detik. Pemain terhubung sedang berpikir atau Activity-nya di tab lain, dan mem-ping orang yang sedang berpikir setelah 10 detik membuat setiap giliran panjang berisik. Seperempat jam adalah batas "kamu jelas tidak sedang berpikir".
- **Ambang mengikuti jam, bukan tetap.** ADR-0015 menetapkan preset terpendek 1+0, yaitu 60 detik untuk seluruh game. Ambang diam 5 menit yang tetap berarti ping selalu datang setelah game selesai di preset terpendek dan setelah setengah jam di 5+3. Menurunkan ambang secara proporsional menjaga janji ping itu sendiri: memberi tahu saat masih ada waktu untuk bertindak. **Akibatnya plafon 300 detik praktis tidak mengikat** — angka yang benar-benar berlaku di preset terpanjang pada giliran pertama adalah 150 detik — dan itu ditulis apa adanya supaya tidak terbaca sebagai janji "lima menit".
- **Satu ping per ply, bukan pengulangan berkala.** Alasan yang sama yang membuat ADR-0006 menolak DM agresif dan ADR-0013 menolak tick-edit: Discord menghukum kebisingan, dan pengulangan tidak menambah informasi — pesan yang sama diulang kepada orang yang sudah menerimanya. Pemain yang tidak muncul setelah satu ping sudah menyatakan pilihannya.
- **Dihapus saat giliran berakhir, bukan saat ping berikutnya.** Ping adalah pernyataan tentang keadaan sekarang. Begitu giliran lewat, pernyataannya salah. Menghapusnya di titik giliran berakhir membuat channel tidak pernah memuat klaim yang salah, dan ongkosnya satu panggilan hapus per langkah — jauh lebih murah daripada merawat pesan yang harus terus disunting agar jujur.
- **Tanpa ping saat boot.** Karena giliran tidak bisa berpindah saat bot mati, ping saat boot hanya mengulang pemberitahuan yang sudah dikirim sebelum mati. Di turnamen 8 game, restart adalah 8 mention sekaligus, dan saat pengembangan itu terjadi puluhan kali sehari.
- **Penanda di memori, bukan di database.** Skema ADR-0005 sudah punya empat kolom jam dan riwayat bug dari jalur yang lupa mengisi kolom baru (`games.source` sengaja tanpa default karena itu). Menambah dua kolom untuk penanda yang nilainya hilang tanpa kerugian adalah kebalikan dari pelajaran itu.
- **Menumpang tick, bukan timer per giliran.** Tick 1 detik sudah berjalan dan sudah menjadi jam platform. Timer per giliran berarti satu handle per game hidup, satu jalur pembatalan di setiap langkah, penutupan, dan restart, dan satu kesempatan baru untuk lupa membatalkan — kemudian ping untuk giliran yang sudah lewat. Presisi 1 detik lebih dari cukup untuk ambang 6-150 detik.
- **Tanpa peringatan waktu terpisah.** Peringatan waktu hampir habis adalah ping kedua yang isinya hampir sama dengan ping pertama, dikirim lebih lambat, kepada orang yang sudah diberi tahu. Sisa waktu yang menyertai ping menyampaikan informasi yang sama dengan satu pesan.
- **Tanpa preferensi pemain.** Setiap setelan adalah satu kolom, satu perintah, satu jalur uji, dan satu pertanyaan baru tentang apa artinya ketika pemain mematikannya lalu kalah karena waktu. Belum ada yang meminta, dan satu guild berisi orang yang saling kenal bukan tempat yang membutuhkan tombol itu.

## Konsekuensi

- **`CONTEXT.md` mendapat dua istilah baru.** **Ping giliran** — pesan baru ber-mention yang memberi tahu pemain bahwa gilirannya tiba, dikirim paling banyak sekali per ply dan dihapus saat giliran itu berakhir. **Terhubung (Activity)** — keadaan pemain yang punya setidaknya satu langganan WebSocket hidup atas namanya untuk sebuah game; lawannya **terputus**, dan tidak ada kedudukan lain di antaranya.
- **Tick platform mendapat satu langkah tambahan.** Kontrak ADR-0013 ("memajukan penghitung lalu menutup yang habis") bertambah: ia juga mengevaluasi ping giliran. Tidak ada perubahan pada interval, presisi, atau clamp.
- **`Games` tidak mendapat kolom apa pun**, dan tidak ada tabel baru. ADR-0005 tidak diamendemen.
- **ADR-0015 tidak diubah.** Pesan hasil ber-mention dan pesan analisa tanpa papan tetap seperti diputuskan; pesan ping adalah pesan ketiga yang jenisnya berbeda dan umurnya paling pendek.
- **ADR-0007 mendapat pemakai baru untuk langganan per `game_id`.** Ia sudah memutuskan bentuknya; ticket ini hanya membaca daftar itu. Tidak ada perubahan pada mekanisme penempelan.
- **ADR-0018 tidak diubah, tapi diperjelas pemakaiannya.** Game lawan komputer ikut mem-ping pemain manusianya. "Hasil diumumkan tanpa mention" tetap berlaku untuk pesan hasil, yang merupakan pesan yang berbeda.
- **Tidak ada intent Discord baru.** Mention, tombol, dan pesan tidak menuntut intent istimewa; `Guild.get_member` pun tidak dipakai. Ticket [Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27) tetap terbuka untuk alasannya sendiri (`/impor` menerima lampiran berkas).
- **Beban Discord tambahan:** paling banyak satu pesan dan dua penghapusan per giliran per game. **Tidak ada batas kirim pesan per channel yang terdokumentasi** — halaman rate limits Discord hanya menetapkan 50 req/detik global, bucket per rute ber-`channel_id`, dan 10.000 request invalid per 10 menit — jadi tidak ada angka per-channel yang bisa dianggarkan terhadapnya; yang tersedia hanya header `X-RateLimit-*`, dan serialisasi per channel adalah satu-satunya penjagaan yang jujur.
- **Yang harus dibangun saat implementasi:** pendaftaran langganan yang menyimpan identitas pemain per `game_id` (sudah dibutuhkan ADR-0007), `pinged_ply` dan `disconnected_since` di memori, satu fungsi `maybe_ping_turn(game)` yang dipanggil tick, dan satu penghapusan pesan di jalur commit langkah serta jalur tutup game.

## Verifikasi

**Yang sudah terverifikasi dan tidak perlu diulang:** DM gagal senyap dengan tiga kode error, edit pesan tidak memicu notifikasi, dan hanya pesan baru ber-mention yang memicu ping (ticket #10, dipakai ADR-0006/0009/0013/0014/0015/0016/0018). Langganan WebSocket terikat `game_id` dan sesi ganda diizinkan (ticket #18, ADR-0007). Tick 1 detik, sentidetik, dan urutan potong-lalu-tambah (ticket #21, ADR-0015). Satu proses Python untuk bot + FastAPI (ADR-0010).

**Terverifikasi saat ticket ini (riset dokumentasi primer Discord, jangan ulangi):**

| Klaim | Bukti |
|---|---|
| Mention di dalam **embed tidak dijanjikan** memicu ping | `allowed_mentions` didokumentasikan hanya untuk "mentions in the message content, or the content of components"; syarat "mention format must also be present in the content of the message or its components" — embed tidak disebut di kedua enumerasi |
| Untuk **komponen**, ping didokumentasikan eksplisit | "pingable mentions (@user, @role, etc) present in this component will ping and send notifications" |
| `parse` saling eksklusif dengan `users`/`roles` | "the `parse` field is **mutually exclusive** with the other fields" |
| `users` dibatasi **100 ID**; `replied_user` default **false** | Message resource, `allowed_mentions` object |
| `AllowedMentions()` kosong **mengizinkan** semua | `_FakeBool()` truthy di `discord/mentions.py`; `to_dict()` mengeluarkan `parse: ["everyone","users","roles"]` |
| `SUPPRESS_NOTIFICATIONS` = **4096** (`1 << 12`) dan mematikan push termasuk mention | Message resource, message flags; settable saat Create Message |
| Tidak ada batas kirim pesan per channel yang terdokumentasi | Halaman rate limits tidak memuat pernyataan soal send; hanya 50 req/detik global dan 10.000 invalid/10 menit |
| Bot **tidak bisa membaca** setelan notifikasi pengguna | Tidak ada endpoint user-settings; `PATCH /users/@me` hanya username/avatar/banner |
| `ONLY_MENTIONS` = **1** ada sebagai **default guild**, bukan pengaturan per pengguna yang bisa dibaca bot | Guild resource, `default_message_notifications` |
| Tidak ada mekanisme notifikasi lain yang terdokumentasi | Activities guides nol kemunculan "notification"/"push"; scheduled events tidak menyebut reminder; tidak ada tipe pesan yang bisa dikirim bot sebagai notifikasi |

**Yang tidak terverifikasi dan tidak diklaim:** apakah push notification benar-benar sampai (dokumentasi menyatakan mention "does not guarantee a push notification will be sent", dan Discord menyebut pengguna bisa mengubah setelan sehingga hanya menerima badge). Juga tidak diklaim bahwa pesan baru ber-mention adalah daftar mekanisme yang lengkap — hanya bahwa tidak ada mekanisme lain yang **terdokumentasi**.

**Yang dihitung, bukan diukur:**

| Klaim | Bukti |
|---|---|
| Plafon 300 detik tidak mengikat pada preset mana pun di giliran pertama | Sisa terbesar 600 s (10+0, 10+5) → `600/4 = 150 < 300` |
| Ambang putus tidak pernah nol | `sisa₀ ≥ 1` → `min(10, sisa₀/10) ≥ 0,1`; pada sisa₀ 10 s nilainya 1 s |
| Ping tidak bisa menumpuk saat bot mati | Langkah hanya masuk lewat Activity; jam tidak maju saat backend mati (ADR-0003/0015) |
| Ambang membeku di awal giliran, bukan menguap | Syarat `elapsed ≥ (sisa₀ − elapsed)/4` **setara** dengan `elapsed ≥ sisa₀/5` — jadi ambang yang dibaca ulang menyala di 20%, bukan 25%. Karena itu `sisa₀` dibekukan. |

**Yang tidak diklaim:** berapa banyak ping yang akan benar-benar terkirim per malam, dan apakah pemain merasa 10 detik terlalu cepat. Keduanya bergantung pada perilaku pemain sungguhan dan hanya bisa dijawab setelah dipakai. Ambangnya satu konstanta per jenis, jadi menyesuaikannya tidak membongkar apa pun.

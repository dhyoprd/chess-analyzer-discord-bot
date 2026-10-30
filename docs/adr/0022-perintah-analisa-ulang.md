# Analisa ulang: satu perintah `/analisa-ulang` bertautan, jatah hanya terpakai bila masuk antrean

## Konteks

`CONTEXT.md` mendefinisikan **Analisa ulang** sejak [ADR-0009](0009-pipeline-analisa.md), dan ADR-0009:71 menyebutnya sebagai satu-satunya jalan keluar untuk game yang analisanya gagal tiga kali. [ADR-0012](0012-penyajian-stats.md):131 dan [ADR-0016](0016-penyajian-klasemen.md):99 sama-sama mencatatnya sebagai **kabut peta yang belum punya pemilik**. Ticket [Perintah analisa ulang](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/26) menunggu dua hal selesai — bentuk pesan hasil analisa (#7) dan penyajian klasemen (#22) — dan keduanya sudah tertutup.

**Premis body ticket salah, dan itu menyingkat separuh pekerjaannya.** Body menyatakan "tidak ada ADR yang memiliki perintahnya". [ADR-0009](0009-pipeline-analisa.md):79 sebenarnya sudah menulis: *"Analisa ulang manual dipicu lewat **satu perintah bot**, boleh siapa pun, dibatasi **1 per pemain per 10 menit**."* Tiga dari enam pertanyaan ticket sudah terjawab sejak ADR itu ditulis. Yang benar-benar terbuka hanyalah apa yang ADR-0009 serahkan ke implementasi: nama perintah, cara menunjuk game, perilaku saat antrean sibuk, dan di mana hasilnya muncul.

Riset sumber primer atas `discord/discord-api-docs` dan `Rapptz/discord.py` menambah fakta yang menentukan bentuk perintahnya, termasuk satu koreksi dua langkah yang layak dicatat.

## Keputusan

**Analisa ulang dijalankan lewat satu perintah `/analisa-ulang` dengan opsi `tautan:` yang wajib, semua balasannya ephemeral, antreannya di belakang FIFO, dan jatah 10 menit hanya terpakai bila permintaannya benar-benar masuk antrean.**

### Premis yang dipertahankan, bukan dibuka kembali

- **ADR-0009:79 berlaku apa adanya**: **satu perintah bot**, **boleh siapa pun**, **1 per pemain per 10 menit**. Ticket ini tidak membuka kembali ketiganya, dan ADR-0009 tidak diamendemen.
- **Alasan untuk menahan diri:** membuka kembali keputusan yang sudah tiga ADR rujuk menuntut alasan yang lebih kuat daripada "keadaan sudah berubah sejak ditulis". Yang berubah hanyalah bahwa permukaan pesan bot kini diketahui — dan itu tidak menyentuh ketiga keputusan itu sama sekali.
- **Konsekuensinya bentuknya sudah terbatas pada perintah**, bukan tombol dan bukan menu konteks. Riset menemukan bahwa **message context-menu command** adalah permukaan terkuat untuk aksi "analisa ulang game ini" — ia menerima pesan sasaran lengkap **tanpa privileged intent** (`gateway.mdx:497-501`, `you-might-not-need-a-privileged-intent.mdx:128`), tanpa parsing tautan, dan tanpa `READ_MESSAGE_HISTORY`. Ia **tidak dipakai**, dan alasannya sama dengan alasan ADR-0020/ADR-0021 memilih satu permukaan: dua permukaan berarti dua jalur masuk yang harus dibuat sepakat. Dicatat di sini supaya tidak ditawarkan lagi sebagai ide baru.

### Nama dan opsi

- **`/analisa-ulang`**, mengikuti istilah `CONTEXT.md` dan bahasa seluruh perintah bot lainnya (`/challenge`, `/komputer`, `/stats`, `/klasemen`, `/impor`, `/klaim`).
- **Satu opsi wajib `tautan:`** berisi **tautan pesan hasil analisa** atau **angka `game_id`** langsung. Dua bentuk, satu pemeriksaan — pemain menempel apa yang ada di layar, atau mengetik angka yang tertulis di footer pesan itu.
- **Bukan "dari pesan yang dibalas"**: jalur itu gagal senyap ketika perintah tidak dipakai sebagai balasan, dan menuntut fetch pesan yang tebal. **Bukan `pemain:`**: "game terakhir orang itu" adalah tebakan yang salah sasaran tanpa terlihat sampai hasilnya keluar.
- **Jembatan tautan ke game adalah footer embed hasil analisa**, yang kini memuat `game 142 · Stockfish 19 · 3 blunder` — nomor game, versi engine (sudah diwajibkan ADR-0009:107 supaya perbedaan antar-analisa bisa dijelaskan), dan satu angka yang membedakan dua analisa pada pandangan pertama. Bot membaca footer itu dari pesan yang ditautkan dan memvalidasi bahwa pesan itu memang pesan hasil analisa bot ini. **Nol tabel pemetaan, nol kolom baru.**

### Kenapa membaca pesan sendiri aman — dan kenapa itu tidak boleh disalahpahami

Ini bagian yang paling mudah salah, jadi ditulis lengkap.

- **Bot boleh membaca `content` dan `embeds` pesan yang ia sendiri kirim tanpa privileged `MESSAGE_CONTENT`.** Terverifikasi dari tiga pernyataan dokumentasi yang saling bebas, termasuk changelog yang menyebut cakupan REST secara eksplisit (*"These restrictions do not apply for messages that a bot or app sends"*).
- **Pengecualian itu sempit dan bersifat isi, bukan penulis**: ia **tidak** berlaku untuk pesan pengguna lain, bot lain, aplikasi lain, atau pesan webhook. `fetch_message` **bukan** jalan pintas untuk membaca pesan orang lain.
- **`READ_MESSAGE_HISTORY` dan `VIEW_CHANNEL` tetap dituntut** oleh `GET /channels/{id}/messages/{id}`. Bot memilikinya di channel tempat ia mengirim pesan hasil, jadi tidak ada izin baru yang perlu diminta.
- **Koreksi dua langkah yang dicatat karena mudah terulang.** Riset pertama menyimpulkan "tautan adalah jalan buntu tanpa intent" — benar untuk pesan **orang lain**, salah untuk pesan **bot sendiri**. Riset lanjutan mengoreksi. Yang membuat koreksi itu perlu adalah bahwa `MESSAGE_CONTENT` membatasi **gateway dan REST sekaligus**, sehingga naluri "fetch saja akan lolos" memang salah; yang menyelamatkan jalur ini adalah pengecualian pesan-sendiri, bukan sifat REST.
- **Fakta ini berlaku lebih luas dari ticket ini**: analisa ulang **tidak menambah satu pun kebutuhan intent**. Diteruskan ke [Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27).

### Game mana yang boleh

- **Semua game selesai dengan minimal 1 langkah.** Termasuk yang analisanya gagal tiga kali, yang angkanya ingin diperbarui, dan yang dianalisa versi engine lama.
- **Alasannya bukan kelonggaran, melainkan koherensi.** ADR-0009:71 menjadikan `analyses` **entitas bersejarah**: analisa ulang menulis baris baru, tidak menimpa. Kalau analisa ulang hanya boleh untuk game yang gagal, **tidak akan pernah ada dua baris analisa untuk satu game** dan "entitas bersejarah" tak pernah berisi apa pun untuk dibedakan.
- **Game tanpa langkah ditolak**, karena ADR-0009:83 melewatinya tanpa mencatat apa pun — tidak ada yang bisa dianalisa. **Game yang belum selesai ditolak**, karena hasil dan ratingnya belum ada (ADR-0015).

### Jalannya perintah

Urutan pemeriksaan dikunci, dan urutannya bagian dari keputusan:

1. **`defer(ephemeral=True)` sebagai tindakan pertama handler**, sebelum pemeriksaan apa pun. Interaksi harus diakui dalam **3 detik** atau token-nya batal, sementara handler ini melakukan fetch pesan dan dua kueri. Keadaan ephemeral **terkunci saat defer dan tidak bisa diubah kemudian**, jadi ia juga memenuhi keputusan bahwa semua balasan ephemeral.
2. **Jatah 10 menit** — bila habis, ditolak dengan sisa waktunya.
3. **Validitas game** — ada, selesai, dan punya minimal satu langkah.
4. **Antrean** — bila game itu sudah menunggu atau sedang dianalisa, ditolak dengan **posisi antreannya**.
5. **Diterima** — masuk antrean, dan **baru di titik ini jatah 10 menit terpakai**.

- **Urutan ini dari yang paling murah ke yang paling mahal**, dan jatah ada di depan karena ia yang melindungi pemeriksaan lain dari dibanjiri.
- **Balasan selalu menyebut alasan yang benar-benar menghentikannya.** Menolak dengan alasan yang salah membuat pemain memperbaiki hal yang tidak rusak.

### Jatah 10 menit

- **Hanya terpakai bila permintaan benar-benar masuk antrean.** Penolakan karena tautan salah, game belum selesai, atau game tanpa langkah **tidak memakan jatah**. Tanpa ini, pemain yang salah tempel tautan dua kali terkunci sepuluh menit karena kesalahannya sendiri, dan ia akan mengira botnya rusak.
- **Dipegang sendiri, bukan oleh `@app_commands.checks.cooldown`.** Dekorator bawaan discord.py menyala **sebelum handler berjalan**, sehingga ia tidak bisa menyatakan "penolakan tidak memakan jatah" — ia justru membalik keputusan di atas. Alasan kedua: bawaan tidak punya API reset atau introspeksi, jadi tidak ada jalan keluar administratif selain membongkar closure-nya.
- **Disimpan di memori proses**, `player_id` → stempel waktu. Restart mengosongkannya, dan itu tidak merugikan siapa pun: bot yang baru hidup tidak sedang menahan siapa pun. Pola yang sama dengan `pinged_ply` (ADR-0019) dan tawaran remis (ADR-0021). **Nol tabel, nol kolom.**

### Antrean

- **Permintaan manual masuk di belakang semua yang sudah menunggu** — FIFO apa adanya (ADR-0009). Di malam turnamen ia bisa menunggu beberapa menit, dan balasan penerimaan menyebut posisinya supaya itu tidak terasa seperti hang.
- **Menyisipkan ke depan ditolak** karena berarti pemain yang tidak meminta apa-apa menunggu lebih lama karena orang lain mengklik dua kali. FIFO juga satu-satunya alasan antrean ini bisa dijelaskan kepada pemain.
- **Pemeriksaan "sudah di antrean?" membaca antrean di MEMORI, bukan database.** Ini konsekuensi ADR-0009:74, bukan pilihan baru: analisa menulis **satu transaksi di akhir**, sehingga game yang sedang dianalisa **tidak punya baris apa pun** di database. Tidak ada keadaan "sedang berjalan" yang bisa dikueri.
- **Satu permintaan ganda ditolak, bukan diantrekan dua kali.** Tanpa ini, dua orang bisa membakar puluhan detik worker FIFO untuk hasil yang hampir identik, dan pemain lain menunggu di belakangnya.

### Percobaan otomatis vs manual

- **Analisa ulang manual tidak pernah menyentuh penghitung 3 percobaan.** Ia bukan percobaan otomatis: tidak menambah, tidak mengurangi.
- **Pada keberhasilan, tidak ada yang perlu direset.** ADR-0009:72 memakai **dedup lewat kueri** — "sudah dianalisa" berarti "sudah ada baris `analyses` berstatus selesai". Begitu analisa ulang manual berhasil, baris selesai itu ada, dan pemindaian saat start berhenti mencoba dengan sendirinya. **Mekanisme reset tidak dibangun karena ia tidak dibutuhkan.**
- **Pada kegagalan, penghitung tetap di angka berapa pun ia berada.** Kegagalannya tetap dikirim ke channel (ADR-0009:64), dan pemain bisa meminta lagi setelah jatahnya pulih. Jalan keluarnya tidak pernah tertutup — itu inti dari "manual adalah jalan keluar setelah tiga kali gagal".

### Keluaran

- **Pesan progres sama persis** dengan jalur otomatis: diedit tiap ~10% dalam satuan langkah, menyebut posisi antrean, **dihapus saat selesai**. Worker tidak perlu tahu apakah analisa ini otomatis atau manual — **nol cabang baru di dalam worker**.
- **Pesan hasil dikirim sebagai pesan BARU di `games.channel_id`**, bentuknya identik dengan hasil otomatis (embed papan 320 px + hitungan + seluruh blunder + urutan langkah penuh, ADR-0017). **TANPA mention** — berbeda dari jalur otomatis yang ber-mention karena pemainnya tidak tahu kapan analisanya selesai. Di sini pemintanya baru saja mengetik perintahnya dan sedang menunggu; mention di titik itu tidak menjawab pertanyaan siapa pun.
- **Pesan hasil LAMA disunting menjadi penunjuk**, bukan dibiarkan dan bukan dihapus: thumbnail dan daftar langkahnya dilepas, diganti satu baris "Analisa game ini sudah diperbarui. Lihat pesan di bawah." Alasannya, dua pesan hasil dengan angka berbeda dan tanpa penanda mana yang berlaku adalah jebakan bagi siapa pun yang membuka yang lama — dan menghapusnya mematikan tautan yang mungkin sudah dibagikan orang lain.
- **Untuk itu `analyses` mendapat kolom `message_id`** (nullable), ditulis **sesudah** pesan terkirim, **bukan di dalam transaksi analisa**. Analisa yang sudah selesai tidak boleh gagal hanya karena Discord menolak pesannya; bila pengiriman gagal, `message_id` tetap NULL dan analisanya tetap tersimpan.

### Angka di `/stats` bergeser, dan itu diterima

- **Analisa ulang menggeser akurasi dan hitungan klasifikasi yang ditampilkan `/stats`, diam-diam.** Ini bukan efek samping yang lolos: ADR-0009:71 mengunci bahwa yang ditampilkan adalah **analisa selesai terbaru**, dan ADR-0009:107 sudah menyatakan analisa ulang boleh menghasilkan angka berbeda. Nol mekanisme baru.
- **Tidak ditambal terhadap "mencari angka bagus".** ADR-0009:106 mengukur variasi antar-run ±5 cp, dan ambang klasifikasi terkecil 0,1 win-chance, jadi sebagian kecil klasifikasi memang bisa berbalik antar-analisa. Dengan jatah 10 menit, menggeser satu klasifikasi menuntut puluhan percobaan. **Menambal dengan menampilkan analisa pertama bukan penambalan** — ia bentuk lain dari masalah yang sama (memilih analisa mana yang tampil berdasarkan angkanya), dan ia mematikan satu-satunya pemakaian yang wajar: menganalisa ulang dengan versi engine baru, atau memperbaiki game yang analisanya gagal.

## Alasan

- **ADR-0009:79 dipertahankan karena ia sudah memutuskan.** Membuka kembali tiga keputusan yang sudah tiga ADR rujuk menuntut alasan baru; "sekarang kita tahu bentuk pesan bot" bukan alasan yang menyentuh ketiganya.
- **Menu konteks ditolak meski secara teknis lebih kuat.** Ia memang menerima pesan sasaran tanpa intent dan tanpa parsing tautan. Tapi ia permukaan **kedua**, dan proyek ini sudah empat kali kena bug dari dua jalur yang seharusnya menghitung hal yang sama (#7); ADR-0020 dan ADR-0021 sama-sama memilih satu permukaan dengan alasan itu. Fakta teknisnya dicatat supaya keputusannya bisa ditinjau ulang dengan alasan, bukan dengan tebakan.
- **Opsi tautan, bukan balasan.** Satu jalur penunjuk sasaran yang selalu bisa dipakai, dan bisa dipakai dari channel mana pun. "Dari pesan yang dibalas" gagal senyap justru pada pemakaian yang paling wajar.
- **Footer sebagai jembatan karena ia sudah ada.** Embed hasil analisa sudah wajib menyebut versi engine (ADR-0009:107); menambahkan nomor game di sebelahnya berbiaya satu string dan menghapus seluruh kebutuhan tabel pemetaan.
- **`defer` lebih dulu karena 3 detik tidak bisa ditawar.** Handler ini melakukan fetch dan dua kueri sebelum bisa menjawab; menaruh pemeriksaan di depan defer berarti kegagalan lambat membatalkan interaksi **tanpa pesan apa pun** kepada pemain.
- **Jatah hanya terpakai bila masuk antrean.** Jatah ada untuk melindungi worker, bukan untuk menghukum salah ketik. Penolakan yang memakan jatah membuat satu kesalahan kecil berharga sepuluh menit.
- **Cooldown sendiri, bukan dekorator.** Dekorator bawaan tidak bisa menyatakan aturan di atas, dan ia tidak punya jalan keluar administratif.
- **FIFO tanpa pengecualian.** Antrean yang bisa disalip bukan lagi FIFO, dan setiap penyisipan menunda orang yang tidak meminta apa-apa.
- **Progres dan bentuk hasil disamakan dengan jalur otomatis.** Dua bentuk pesan untuk satu jenis keluaran adalah dua hal yang harus dirawat agar tetap sepakat — persis keluarga bug yang sudah menggigit proyek ini berulang kali.
- **Pesan lama disunting, bukan dibiarkan atau dihapus.** Membiarkannya memuat angka basi adalah jebakan; menghapusnya mematikan tautan yang sudah beredar. Menyuntingnya memenuhi keduanya dengan satu panggilan API.
- **Tidak menambal "cari angka bagus".** Ia menuntut puluhan percobaan, dan penambalannya menciptakan masalah yang sama dengan nama lain.

## Konsekuensi

- **`CONTEXT.md`: istilah "Analisa ulang" diperbarui, bukan ditambah.** Isinya sudah benar sejak ADR-0009; yang ditambahkan hanya bahwa perintahnya bernama `/analisa-ulang`, bahwa ia boleh dijalankan siapa pun dengan jatah 10 menit, dan bahwa ia menulis baris `analyses` **baru** tanpa menghapus yang lama.
- **Skema bertambah satu kolom: `analyses.message_id`** (nullable), ditulis sesudah pengiriman. Ini pengecualian yang disengaja terhadap "nol perubahan skema" yang ADR-0020/ADR-0021 pegang, dan alasannya konkret: tanpa kolom itu, menyunting pesan lama mustahil setelah restart, dan keputusan pesan-lama gagal senyap.
- **ADR-0009 dilengkapi, tidak diubah.** :79 mendapat bentuk konkretnya (nama, opsi, urutan pemeriksaan, perilaku antrean). Aturan FIFO, anggaran node, rumus, dedup kueri, dan batas 3 percobaan tidak tersentuh. Bentuk pesan hasil mendapat satu field, `footer`.
- **Tidak ada intent Discord baru.** Perintah ini memakai `applications.commands` yang sudah ada, dan membaca pesan sendiri dikecualikan dari `MESSAGE_CONTENT`. Fakta itu diteruskan ke [Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27).
- **`/stats` dan `/klasemen` tidak berubah.** Keduanya sudah membaca "analisa selesai terbaru" (ADR-0009:71), jadi pergeseran angkanya otomatis dan tidak menuntut kode baru di sana.
- **Yang harus dibangun saat implementasi:** perintah `/analisa-ulang` dengan satu opsi, `defer(ephemeral=True)` di baris pertama, cooldown di memori yang hanya terpakai setelah validasi lolos, parser tautan → `game_id` yang memvalidasi footer, footer baru pada embed hasil, kolom `analyses.message_id`, satu penyuntingan pesan lama saat analisa ulang selesai, dan satu penolakan berbasis antrean di memori.

## Verifikasi

**Yang tidak perlu diulang:** antrean FIFO satu worker, `go nodes` 1 juta, dedup lewat kueri, batas 3 percobaan, satu transaksi di akhir, bentuk pesan hasil dan papan 320 px (ADR-0009, ADR-0017). Perintah bot berbahasa Indonesia, balasan publik untuk `/stats` dan `/klasemen` (ADR-0012, ADR-0016). Satu permukaan per aksi (ADR-0020, ADR-0021). Cooldown dan penanda di memori (ADR-0019, ADR-0021). Hasil + rating satu transaksi (ADR-0008).

**Terverifikasi saat ticket ini (riset sumber primer `discord/discord-api-docs` @ `e3ea5890`, `Rapptz/discord.py` @ `65232c38`; jangan ulangi):**

| Klaim | Bukti |
|---|---|
| **Bot boleh membaca `content`/`embeds` pesan yang ia sendiri kirim tanpa `MESSAGE_CONTENT`** | `gateway.mdx:497-501` — daftar pengecualian memuat *"Content in messages that an app sends"*; `you-might-not-need-a-privileged-intent.mdx:109-114` — *"**Messages your app sends**"*; `change-log.mdx:3727` — *"These restrictions do not apply for messages that a bot or app sends"* |
| Pengecualian itu **tidak** mencakup pesan orang lain, bot lain, atau webhook | daftar pengecualian yang sama; `message.mdx:66` — penulis pesan webhook adalah webhook |
| `MESSAGE_CONTENT` membatasi **gateway DAN REST sekaligus** | `you-might-not-need-a-privileged-intent.mdx:97` — *"across both Gateway events and REST API responses"* |
| `GET /channels/{id}/messages/{id}` menuntut **`VIEW_CHANNEL` + `READ_MESSAGE_HISTORY`** | `message.mdx:1068-1073` |
| **Message context-menu** menerima pesan sasaran lengkap tanpa intent | `gateway.mdx:497-501`, `you-might-not-need-a-privileged-intent.mdx:126-128` — *"Your bot receives the full message object, including its content."* |
| Context menu bertipe `MESSAGE 3`, tanpa argumen, boleh huruf campuran dan spasi | `application-commands.mdx:89`, `:954`, `:49` |
| Batas context menu **15 per tipe** (naik dari 5 pada 2026-03-03) | `application-commands.mdx:200-205`; `change-log.mdx:1016` |
| Interaksi harus diakui dalam **3 detik**; token berlaku **15 menit** | `receiving-and-responding.mdx:351`, `:432` |
| **Keadaan ephemeral terkunci saat defer** dan tidak bisa diubah kemudian | `receiving-and-responding.mdx:479` — *"an existing message's ephemeral state cannot be changed"* |
| Respons ephemeral **boleh** membawa lampiran berkas | `receiving-and-responding.mdx:445` — *"This endpoint also supports file attachments"* |
| Batas berkas **20 MiB per berkas**, **25 MiB per permintaan** | `reference.mdx:438`, `message.mdx:1096` |
| `@app_commands.checks.cooldown` menyala **sebelum handler** dan menyimpan keadaan di **closure dict di memori** | `app_commands/checks.py:412-417`, `:371-374` (`mapping: Dict[Any, Cooldown] = {}`); `:429-430` |
| Cooldown bawaan **tidak punya API reset/introspeksi** | tidak ada padanan `Command.reset_cooldown` (`ext/commands/core.py:1008`) di `app_commands` |
| Format tautan pesan **tidak didokumentasikan** sebagai spesifikasi | grep seluruh 207 berkas `.mdx`/`.md`: hanya tautan **channel** 2-segmen di `hosting-on-cloudflare-workers.mdx:76`; bentuk 3-segmen hanya tersirat dari `discord.py` `jump_url` (`message.py:1229-1232`) dan `link_regex` (`converter.py:363-367`) |
| Tidak ada cara mengambil pesan dari tautan tanpa fetch | daftar endpoint `message.mdx:917-1323` — hanya `Get Channel Message` yang menerima `channel.id` + `message.id` |

**Yang tidak diklaim:** bahwa tautan pesan yang sangat lama selalu bisa di-fetch — tidak ada pernyataan usia, cache, atau batas "hanya pesan terbaru" di mana pun, dan ketiadaannya bukan bukti bahwa ia bekerja. Juga tidak diklaim bahwa `resolved.messages` pada menu konteks selalu membawa `embeds` lengkap: dokumentasi menyebutnya *"partial messages"* di satu tempat dan menampilkan objek penuh di tempat lain, dan kontradiksi itu tidak diselesaikan karena jalur menu konteks tidak dipakai.

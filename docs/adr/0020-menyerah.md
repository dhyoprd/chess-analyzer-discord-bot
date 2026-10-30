# Menyerah: satu tombol di papan, setelah langkah pertama, dan jam diselesaikan lebih dulu

## Konteks

Ticket [Tombol Menyerah](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/24) memutuskan **permukaan** menyerah — satu-satunya sebab berakhir yang punya nama di skema tapi tidak punya pemilik. [ADR-0015](0015-perilaku-jam-catur.md) sudah menetapkan kosakata `end_reason='resign'`, aturan bahwa armageddon **boleh** berakhir dengan menyerah, dan bahwa **satu fungsi tutup game** melayani semua sebab. [ADR-0008](0008-konfigurasi-glicko-2.md) menilai game yang diserahkan, dan menetapkan hasil + entri rating ditulis dalam **satu transaksi**. ADR-0015 menutup game sebagai pesan hasil **ber-mention yang dikirim segera**, terpisah dari pesan analisa yang lebih lambat dan bisa gagal tiga kali.

Yang belum ada: dari mana pemain menyerah, apa yang harus ia lakukan untuk memastikan, dan bagaimana jalur ini berdamai dengan jam yang berjalan di tick 1 detik.

**Tiga premis di body ticket yang menyusut sebelum ditanyakan:**

- **"Menyerah saat lawan tidak pernah muncul"** bukan keadaan yang bisa dibedakan. Di ply 0 belum ada langkah sama sekali, sehingga menyerah berarti menyerahkan game yang tidak pernah dimainkan — dan ADR-0014/0015 sudah menerima bahwa game seperti itu menggantung 24 jam waktu bot hidup lalu ditutup `result='none'`/`abandoned` tanpa rating. Di ply ≥ 1, lawan yang belum melangkah dan lawan yang sedang berpikir adalah keadaan yang **sama** bagi backend; tidak ada yang perlu dipisahkan.
- **Hak tekan** bukan keputusan tersendiri. Discord tidak membatasi penekan tombol per-pengguna (terverifikasi, ticket #10), dan di Activity tombolnya kita gambar sendiri — jadi backend memvalidasi lewat identitas terverifikasi yang sudah menjadi jalur semua intent (ADR-0002, ADR-0007).
- **Armageddon** sudah dijawab ADR-0015: "remis = hitam menang" adalah **pembaca hasil akhir**, bukan aturan yang membatasi cara game berakhir. Menyerah dibaca apa adanya — lawannya menang.

Riset dokumentasi primer menambahkan empat fakta yang membentuk jawabannya. Pertama, **Lichess mensyaratkan konfirmasi** untuk menyerah: `confirmResign` default `YES`, dan konfirmasinya bukan modal melainkan **dua tombol inline** yang menggantikan tombol aslinya. Kedua, konfirmasi itu **membatalkan dirinya sendiri**: `setTimeout(() => this.resign(false), 3000)`, dan klien membatalkannya lagi saat ia mengirim langkah. Ketiga, **`resignable` Lichess tidak punya suku giliran** — `def resignable = playable && !abortable`, dan `abortable` hanya soal jumlah ply, bukan warna yang sedang melangkah. Keempat, Lichess **melarang menyerah** pada game dengan kurang dari **2 ply** biasa: `def abortable = status == Status.Started && playedPlies < 2 && nonMandatory`, dan tombolnya dirender `enabled: resignable(d)`. Pembatalan di Lichess adalah jalur tersendiri ("abort"), yang tidak kita punya.

Chess.com meminta konfirmasi di web dan seluler. Tidak ada satu pun dokumentasi Activities Discord yang membahas dialog konfirmasi, tindakan tak-bisa-dibalik, atau menyerah — hasil negatif yang dicatat, bukan diisi dengan tebakan.

## Keputusan

**Menyerah adalah tombol di papan Activity, aktif hanya setelah jam berjalan, dikonfirmasi dua langkah di klien, dan jalurnya menyelesaikan jam lebih dulu sebelum menutup game sebagai kekalahan.**

### Permukaan

- **Activity saja.** Satu tombol **Menyerah** di papan. **Tidak ada perintah bot** dan tidak ada tombol menyerah di pesan Discord mana pun.
- **Alasannya bukan selera.** Permukaan Discord menuntut jawaban atas "game yang mana" — pemain bisa punya beberapa game hidup di channel berbeda (ADR-0018 mengizinkannya tanpa batas) — lalu menuntut jalur hak tekan kedua di sisi pesan. Activity sudah memegang keduanya: sesi terikat ke satu game lewat identitas terverifikasi (ADR-0007), dan tombolnya digambar oleh kode kita sendiri.
- **Intent menyerah menumpang WebSocket yang sudah ada**, bentuknya sama dengan niat langkah: klien mengirim niat, backend memvalidasi bahwa pengirim adalah **peserta** game itu dan bahwa game masih berjalan, lalu memutuskan. Klien tidak pernah memutuskan hasil (ADR-0002).
- **Satu permukaan berarti satu jalur tutup.** Tidak ada jalur "menyerah lewat Discord" yang harus dibuat sepakat dengan jalur Activity — keluarga bug yang sudah empat kali menggigit proyek ini (#7) dan yang ADR-0015:75 sebut sebagai alasan satu fungsi tutup game.

### Kapan tombolnya bisa dipakai

- **Syaratnya `clock_started`**, bukan `status='playing'`. Jam baru berjalan di ply 1 (ADR-0015), jadi menyerah hanya tersedia setelah ada satu langkah yang benar-benar dimainkan.
- **Di ply 0 tombolnya tampil tapi mati.** Ia terlihat sejak papan dibuka, sehingga pemain tahu jalan keluarnya ada, tanpa membuka jalur yang tidak boleh dipakai. Menyembunyikannya membuat pemain yang berubah pikiran sebelum melangkah tidak melihat jalan keluar sama sekali.
- **Game 0-langkah tetap ditutup "Ditinggalkan"** — 24 jam waktu bot hidup, `result='none'`, `end_reason='abandoned'`, tanpa entri rating (ADR-0014, ADR-0015). **Tidak ada nilai `end_reason` baru dan tidak ada jalur "batalkan"**, berbeda dari Lichess yang punya "abort". Alasannya: pembatalan adalah jalan keluar yang bisa disalahgunakan — dua pemain bisa membatalkan setiap kali posisinya memburuk — sedangkan Ditinggalkan sudah menutup keadaan itu tanpa satu pun cabang baru.
- **Boleh di giliran mana pun.** Lichess tidak punya suku giliran di `resignable`, dan menyerah di giliran lawan tetap berarti kau kalah, jadi tidak ada yang bisa disalahgunakan. Melarangnya hanya menghukum pemain yang sudah memutuskan pergi dengan menunggu lawannya melangkah — bisa berarti menit.
- **Game lawan komputer: tombolnya ada.** Manusia boleh menyerah; mesin tidak pernah menyerah (ADR-0018). Game itu `source='engine'`, jadi kekalahan tidak dinilai rating (ADR-0008).

### Konfirmasi

- **Dua langkah, murni di klien.** Menekan **Menyerah** mengubah tombol itu menjadi **Ya** dan **Batal**; tidak ada panggilan jaringan saat mengangkat.
- **Konfirmasi kedaluwarsa 3 detik** dan kembali sendiri ke keadaan awal, mengikuti `setTimeout(…, 3000)` Lichess. Tanpa kedaluwarsa, konfirmasi yang terangkat bisa tersentuh jauh kemudian tanpa sengaja — tepat kegagalan yang konfirmasi ini ada untuk mencegah.
- **Konfirmasi batal oleh langkah siapa pun**, bukan hanya langkah sendiri. Lichess membatalkannya hanya saat kliennya sendiri mengirim langkah; kita lebih lebar karena papan yang berubah berarti keputusan "ya, posisi ini sudah hilang" tidak lagi dibuat atas posisi yang sama. Beda ini disengaja dan dicatat.
- **Bentuk visualnya (dua tombol inline vs modal) diserahkan ke [Desain interaksi papan catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/8).** Yang dikunci di sini adalah: dua langkah, umur 3 detik, dan batal oleh langkah siapa pun.

### Jalur tutupnya

- **Jam diselesaikan lebih dulu oleh jalur menyerah**, memakai fungsi jam yang **sama** dengan tick — bukan salinan, bukan aturan kedua.
- **Tenggang 500 ms milik model jam, bukan milik handler langkah.** Ini menutup balapan yang tidak terlihat: tick berjalan tiap 1 detik, jadi ada jendela sampai satu detik di mana jam lawan sudah melewati nol tapi game belum ditutup. Menyerah yang datang di jendela itu tidak boleh merampas kemenangan yang sudah menjadi hak pemain yang bendera lawannya jatuh. Bila jam menyatakan lawan sudah kehabisan waktu, **hasilnya `timeout` dan kau menang** — bukan `resign` dan kau kalah. Lichess tidak punya persoalan ini karena penutupan game di sana tidak bergantung pada tick.
- **Menyerah selalu kalah. Tidak ada cabang remis.** Lichess memetakan menyerah menjadi `InsufficientMaterialClaim` (remis) bila pelangkah tidak mungkin dikalahkan — `if RoundGame.cannotLose(pov) then finisher.other(pov.game, _.InsufficientMaterialClaim, None)`. Cabang itu **tidak disalin**, dan bukan karena lupa: di sini posisi bahan-tak-cukup sudah ditutup backend di langkah yang melahirkannya lewat `is_insufficient_material()` (ADR-0015), sehingga tidak pernah ada kesempatan menyerah di dalam posisi seperti itu. Cabang yang tidak pernah menyala tidak pernah teruji. Dicatat di sini justru supaya implementor berikutnya tidak menyalin Lichess tanpa berpikir.
- **Menulis lewat satu fungsi tutup game** (ADR-0015): `result` = warna lawan, `end_reason='resign'`, `draw_type` NULL. Predikat berating ADR-0008/0012 dievaluasi **apa adanya** — tidak ada aturan rating baru. Hasil game + entri rating dalam **satu transaksi** (ADR-0008).
- **Sesudah transaksi**, berurutan: hapus **Ping giliran** yang terlacak untuk game itu (ADR-0019 sudah menetapkan penghapusan di jalur tutup game), kirim **pesan hasil ber-mention kedua pemain** (ADR-0015), lalu serahkan ke pipeline analisa (ADR-0009). Tidak ada I/O Discord di dalam transaksi — pola ADR-0018/0019.
- **Langkah yang tiba setelah menyerah ditolak**, sama seperti setelah hasil sebab apa pun (ADR-0015:78). Hasil yang sudah masuk `rating_ledger` tidak pernah bisa ditarik.

### Sesudah menyerah

- **Papan tetap terbuka menampilkan hasil** — langkah terakhir tersorot, hasil tertulis di atas papan, tombol Menyerah hilang. **Activity tidak menutup dirinya** walaupun `discordSdk.close()` tersedia: menutup diri memutus langganan WebSocket, dan pemain kehilangan tempat menonton analisa yang datang ~20-40 detik kemudian.
- **Klien tidak pernah menggambar hasil yang belum dikonfirmasi server.** Setelah **Ya**, papan menampilkan keadaan **mengirim** sampai siaran state dari server menyatakan game selesai. Bila socket sudah mati saat tombol ditekan, intentnya menguap tanpa error — dan tanpa keadaan ini papan akan berbohong sementara jam terus menyusut. **Ini menyimpang dari pola optimistis #6**, di mana klien menggambar langkah lebih dulu lalu membatalkannya bila ditolak. Alasannya: langkah yang ditolak terlihat sebagai papan yang kembali, sedangkan menyerah tidak bisa ditarik, sehingga kepastian lebih bernilai daripada kecepatan.

## Alasan

- **Satu permukaan, bukan dua.** Permukaan Discord menuntut pemilih game, hak tekan kedua, dan satu jalur lagi yang harus sepakat dengan yang pertama. Activity sudah memegang identitas terverifikasi dan papannya sendiri, jadi ia jalur termurah **dan** jalur yang paling sedikit kemungkinan menyimpang.
- **Menyerah hanya setelah langkah pertama.** Menyerah di ply 0 berarti menilai rating game yang tidak pernah dimainkan. Satu-satunya alternatif yang aman adalah pembatalan tak-berating, dan itu jalan keluar yang bisa disalahgunakan setiap kali posisi memburuk. Ditinggalkan 24 jam sudah menutup keadaan itu dengan nol kosakata baru.
- **Dua langkah, bukan satu.** Menyerah menulis `rating_ledger` dalam transaksi yang sama dan tidak bisa ditarik (ADR-0015:78). Di Activity konfirmasi berbiaya nol — tombolnya kita gambar sendiri, dan Lichess maupun Chess.com sama-sama memintanya.
- **Kedaluwarsa 3 detik.** Konfirmasi yang menganggur adalah tombol bahaya yang menunggu tersentuh. Angka Lichess diambil apa adanya karena tidak ada yang lebih baik untuk dihitung: tiga detik cukup untuk mata berpindah dari tombol ke konfirmasi, dan terlalu pendek untuk lupa.
- **Batal oleh langkah siapa pun.** Konfirmasi adalah pernyataan tentang satu posisi. Begitu posisinya berganti, pernyataannya basi — dan pemain yang baru saja melihat langkah lawan punya informasi baru yang seharusnya boleh ia pertimbangkan ulang. Lebih lebar dari Lichess, dengan alasan yang ditulis, bukan disimpulkan.
- **Jam diselesaikan lebih dulu.** Tanpa itu, hasil game bergantung pada apakah tick kebetulan sudah jalan — game yang sama bisa berakhir dua cara berbeda pada dua waktu yang berjarak 900 ms. Ini keluarga bug yang sama dengan empat bug #7: dua jalur yang seharusnya menghitung hal yang sama, menghitung hal yang berbeda.
- **Tenggang 500 ms milik jam, bukan handler langkah.** Tenggang itu ada supaya langkah yang datang terlambat secara jaringan tetap sah; ia sifat model jam, bukan sifat satu jalur masuk. Menaruhnya di handler langkah berarti jalur lain membaca jam yang sama dengan aturan berbeda.
- **Tanpa cabang remis.** Cabang Lichess tidak bisa dicapai di sini karena backend sudah menutup posisi bahan-tak-cukup di langkah yang melahirkannya. Menyalinnya berarti menambah kode yang tidak pernah dijalankan dan tidak pernah teruji.
- **Tetap di papan, dan tunggu server.** Papan yang menampilkan hasil adalah tempat pemain menonton analisa yang menyusul; menutup Activity memutus justru hal yang ia tunggu. Dan karena intent bisa hilang tanpa error, keadaan "mengirim" adalah satu-satunya cara papan tetap jujur.

## Konsekuensi

- **`CONTEXT.md` tidak mendapat istilah baru.** "Menyerah" sudah hidup di dalam **Sebab berakhir**, dan glosarium itu hanya memuat istilah domain — aturan permukaan adalah milik ADR ini.
- **Tidak ada perubahan skema.** Tidak ada kolom, tabel, atau nilai `end_reason` baru. `resign` sudah bernama sejak ADR-0015.
- **ADR-0015 dilengkapi, tidak diubah.** Tenggang 500 ms kini eksplisit milik **model jam** dan dibaca dua jalur — tick dan jalur menyerah. Satu fungsi tutup game mendapat pemakai baru tanpa perubahan bentuk.
- **ADR-0008 tidak berubah.** Menyerah sudah menjadi salah satu sebab yang menilai rating; predikat berating dievaluasi apa adanya.
- **[ADR-0007](0007-pencocokan-klien-ke-game.md) mendapat pemakai baru** untuk WebSocket yang sudah ada. Intent menyerah adalah pesan lain di jalur terverifikasi yang sama.
- **[ADR-0019](0019-notifikasi-giliran.md) memakai pembersihan ini.** Ping giliran game yang diserahkan dihapus di jalur tutup game — perilaku yang sudah ditetapkan ADR-0019:79, bukan tambahan baru.
- **ADR-0018 tidak berubah.** Mesin tetap tidak pernah menyerah, dan permukaan permainannya tidak memperoleh apa pun dari keputusan ini.
- **[Desain interaksi papan catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/8) mendapat tiga keadaan yang wajib digambar**: tombol **mati** (ply 0), tombol **terangkat** (konfirmasi Ya/Batal), dan keadaan **mengirim**. Ukuran, warna, dan penempatannya tetap milik #8.
- **Tidak ada intent Discord baru.** Tombol di dalam Activity bukan message component; tidak ada `custom_id` dan tidak ada interaksi Discord yang terlibat.
- **Yang harus dibangun saat implementasi:** satu tombol di papan dengan tiga keadaan, satu pesan WebSocket `resign` yang divalidasi backend, satu pemanggilan "selesaikan jam" di depan fungsi tutup game, dan penghapusan ping giliran yang sudah menjadi bagian jalur tutup game.

## Verifikasi

**Yang tidak perlu diulang:** Discord tidak membatasi penekan tombol per-pengguna (ticket #10). Satu fungsi tutup game, kosakata `end_reason`, tenggang 500 ms, dan aturan armageddon boleh berakhir dengan cara apa pun (ADR-0015). Hasil + rating satu transaksi (ADR-0008). Predikat berating (ADR-0012). WebSocket terverifikasi terikat `game_id` (ADR-0007). Ping giliran dihapus di jalur tutup game (ADR-0019). Hasil akhir pipa analisa dipicu setelah commit (ADR-0009).

**Terverifikasi saat ticket ini (riset sumber primer, jangan ulangi):**

| Klaim | Bukti |
|---|---|
| Lichess meminta konfirmasi menyerah, dan default-nya menyala | `Pref.scala:485` — `confirmResign = ConfirmResign.YES` |
| Konfirmasi Lichess **inline**, bukan modal | `ui/round/src/view/table.ts:104-112` mengganti tombol dengan `button.resignConfirm(ctrl)`; `view/button.ts:166-173` menggambarnya sebagai `div.act-confirm` berisi tombol ya/batal |
| Konfirmasi Lichess **kedaluwarsa 3 detik** | `ui/round/src/ctrl.ts:739-753` — `this.resignConfirm = setTimeout(() => this.resign(false), 3000)` |
| Langkah **sendiri** membatalkan konfirmasi Lichess | `ctrl.ts:362` dan `:379` keduanya memanggil `this.resign(false)` |
| Lichess **tidak punya suku giliran** di `resignable` | `modules/core/src/main/game/Game.scala:163` — `def resignable = playable && !abortable` |
| Lichess **melarang menyerah di bawah 2 ply** | `Game.scala:157` — `def abortable = status == Status.Started && playedPlies < 2 && nonMandatory`; klien `ui/lib/src/game/index.ts:41` mencerminkannya |
| Lichess memetakan menyerah menjadi **remis** bila pelangkah tidak mungkin kalah | `modules/round/src/main/RoundAsyncActor.scala:201-206` — `if RoundGame.cannotLose(pov) then finisher.other(pov.game, _.InsufficientMaterialClaim, None)` |
| Menyerah **dinilai rating** di Lichess | `modules/round/src/main/PerfsUpdater.scala:21` — `game.rated.yes && game.finished && (game.playedPlies >= 2 || game.isTournament)`; `Status.Resign = 31 >= Status.Mate = 30` |
| Chess.com meminta konfirmasi di web dan seluler | Help centre artikel 8614799 — *"Click it, then confirm by selecting 'Yes' in the pop-up"* (web); *"confirm by tapping the checkmark on the confirmation message"* (seluler) |
| Activity **bisa menutup dirinya**, tapi itu tidak dipakai | `embedded-app-sdk/src/interface.ts:36` — `close(code: RPCCloseCodes, message: string): void`; `RPCCloseCodes.CLOSE_NORMAL = 1000` |
| Dokumentasi Activities Discord **tidak membahas** konfirmasi, tindakan tak-bisa-dibalik, atau menyerah | Grep nol kemunculan `resign`/`forfeit`/`irreversible` di `activities/{overview,how-activities-work,building-an-activity,design-patterns}.mdx` dan tiga development guide-nya |

**Yang tidak diklaim:** bahwa Chess.com mengizinkan menyerah di giliran lawan — artikel bantuannya tidak pernah menyebut giliran, dan tidak ada sumber primer lain yang ditemukan. Juga tidak diklaim bahwa `RoundGame.cannotLose` berarti persis "lawan tidak punya bahan skakmat"; definisinya tidak ikut terbaca, dan justru karena itu cabangnya tidak disalin.

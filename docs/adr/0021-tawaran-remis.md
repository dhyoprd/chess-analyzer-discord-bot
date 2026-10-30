# Tawaran remis: negosiasi dua pihak di papan, mati oleh langkah penerima, dan jam tidak pernah dijeda

## Konteks

[ADR-0015](0015-perilaku-jam-catur.md):104 sudah menamai `draw_type='agreed'` dan ADR-0012 sudah menilai remis sebagai rating, tapi **tidak ada ADR yang memutuskan bahwa pemain boleh menawarkan remis**. Remis yang punya sumber tanpa fitur ini sudah lengkap — stalemate, lima puluh langkah, pengulangan tiga kali, bahan tak cukup — jadi ticket [Tawaran remis](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/25) hanya menyangkut remis **yang dinegosiasikan**.

Ticket ini sengaja terpisah dari [Tombol Menyerah](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/24) meski sama-sama elemen papan, dan [ADR-0020](0020-menyerah.md) memberi tiga preseden langsung: **permukaan Activity** untuk aksi dalam game, **jam diselesaikan lebih dulu** di setiap jalur tutup, dan **klien tidak menggambar hasil yang belum dikonfirmasi server** untuk tindakan tak-bisa-ditarik. Yang membedakan remis: ia **mekanisme dua pihak** dengan keadaan yang harus disimpan (siapa menawar, di ply mana), dan ia satu-satunya cara sah menghentikan jam orang lain tanpa ia melangkah.

Dua premis di body ticket menyusut sebelum ditanyakan. Pertama, **"berapa lama tawaran berlaku" bukan pertanyaan konstanta**: tawaran mati oleh langkah penerima, jadi umurnya adalah sisa giliran itu — dan itu sudah dibatasi jam, bukan timer. Kedua, **"apakah jam lawan tetap berjalan"** punya jawaban yang sama untuk kedua arah, sehingga tidak perlu dibelah per peran.

Riset sumber primer atas `lichess-org/lila` @ `ba82ec2` menambahkan fakta yang membentuk jawabannya, termasuk satu jebakan yang tidak terlihat dari dokumentasi mana pun.

## Keputusan

**Penawaran remis adalah tombol di papan Activity, boleh di giliran siapa pun, tidak pernah menjeda jam, hidup sampai langkah penerima, dan ditutup lewat satu fungsi tutup game sebagai `draw_type='agreed'`.**

### Permukaan

- **Activity saja.** Dua tombol di papan: **Menyerah** (ADR-0020) dan **Tawar remis**. Tidak ada perintah bot dan tidak ada tombol remis di pesan Discord.
- **Alasannya sama dengan ADR-0020, dan di sini lebih kuat.** Kandidat tawaran selalu punya sesi terikat lewat identitas terverifikasi (ADR-0007), jadi pertanyaan "game yang mana" sudah terjawab. Yang tersisa hanyalah jalur hak tekan kedua di sisi pesan — dan itu jalur tutup game kedua yang harus dibuat sepakat dengan yang pertama, keluarga bug yang sudah empat kali menggigit proyek ini (#7) dan alasan ADR-0015:75 menetapkan satu fungsi tutup.
- **Intent menumpang WebSocket yang sudah ada**, bentuknya sama dengan niat langkah dan intent menyerah: klien mengirim niat, backend memvalidasi peserta dan status game, lalu memutuskan. Klien tidak pernah memutuskan hasil (ADR-0002).

### Jam tidak pernah dijeda

- **Jam berjalan seperti biasa selama tawaran terbuka.** Kedua pemain, kedua arah. Tidak ada mekanisme jeda, tidak ada `clock_paused`.
- **Menjeda jam membuka celah termahal di seluruh platform.** Pemain yang kalah waktu menawar remis berulang kali untuk membekukan jamnya — dan tanpa batas jumlah tawaran, flag-fall praktis terhapus. Karena itu keputusan ini bukan soal keadilan rasa, melainkan penutup lubang.
- **Konsekuensi yang diterima dan ditulis apa adanya:** menawar kepada lawan yang sudah pergi **tidak menyelamatkannya** — ia tetap kalah waktu. Tawaran remis bukan alat belas kasihan, dan tidak dirancang sebagai alat belas kasihan.
- **Lichess juga tidak menjeda.** Bukti tidak langsung tapi kuat: `Finisher.scala:52-53` secara eksplisit menangani keadaan "bendera jatuh sementara tawaran terbuka", yang hanya bisa tercapai bila jamnya terus berjalan.

### Kapan tombolnya bisa dipakai

- **Syaratnya `clock_started`, sama persis dengan Menyerah** — tombol tampil sejak papan dibuka dan **mati di ply 0**. Satu aturan untuk semua elemen papan, dan pemain tidak perlu mengingat dua syarat berbeda pada dua tombol bersebelahan.
- **Menyimpang dari Lichess, dengan alasan.** Lichess menuntut `g.ply >= 2` (`Game.scala:77`), tapi ambang itu ada karena Lichess punya jalur **abort** — remis di ply 0 di sana adalah pembatalan dengan nama lain. Jalur itu sudah ditolak ADR-0020 di sini, dan remis butuh persetujuan lawan sehingga tidak bisa disalahgunakan untuk kabur dari posisi buruk.
- **Boleh di giliran siapa pun.** Lichess tidak punya suku giliran sama sekali: `data.scala:43-44` menyatakannya terang-terangan — *"lichess allows to offer draw on either turn"* — dan `drawable` (`Game.scala:167`) tidak menyebut `turnColor`. Menawar di giliran lawan wajar: yang kau serahkan adalah posisi, bukan tempo.
- **Keduanya berguna, dan itu bukan kebetulan.** Menawar di giliran sendiri berarti kau masih bisa melangkah, dan langkahmu **tidak** mematikan tawaran (lihat di bawah) sehingga tak ada ongkos menunggu. Menawar di giliran lawan berarti jamMu tidak berjalan sama sekali. Tidak ada keadaan di mana penawar terjebak memegang tawarannya sendiri.
- **Game lawan komputer: tombolnya tampil dan ditolak seketika.** Menekannya mengirim intent; backend menjawabnya dengan penolakan sesuai ADR-0018 ("mesin selalu menolak tawaran remis"). Tawaran **tidak pernah terbuka**, dan papan menampilkan "Komputer menolak." Nol kondisi baru di papan, dan pemain melihat jawaban mesin alih-alih tombol yang lenyap tanpa penjelasan. Game itu `source='engine'`, jadi tidak dinilai rating (ADR-0008).

### Umur tawaran

- **Mati oleh langkah PENERIMA saja** — bukan langkah siapa pun. Lichess persis: `MovePlayer.scala:77` memicu penolakan sintetis setelah langkah lawan penawar disimpan.
- **Koreksi atas rumusan awal ticket ini.** "Mati oleh langkah siapa pun" punya cacat yang tidak terlihat sampai digambar: penawar yang menawar **di giliran sendiri** wajib melangkah, dan langkah itu akan mematikan tawarannya sebelum lawan sempat menerimanya — sehingga penawaran di giliran sendiri mati sebelum berguna, padahal itu momen paling wajar untuk menawar.
- **Tidak ada kedaluwarsa berbasis waktu, dan itu bukan kelalaian.** Lichess tidak punya timeout sama sekali: tawaran adalah `isOfferingDraw: Boolean` (`Player.scala:18`) ditambah ply (`data.scala:31`), dan grep menyeluruh atas seluruh pohon `lila` tidak menemukan satu scheduler, timer, atau auto-decline pun yang menyentuh tawaran remis. Satu-satunya pembersihan otomatis adalah langkah lawan, ditambah `$unset` saat game selesai (`GameRepo.scala:365-373`).
- **Karena itu nol konstanta baru, nol timer, nol keadaan yang mati sendiri di tengah.** Umur tawaran adalah sisa giliran penerima, dan jam yang berjalan sudah membatasinya.
- **Celah yang ditutup oleh aturan ini.** Bila tawaran bertahan melewati langkah penerima, ia bisa mencoba langkah bagus lebih dulu lalu menerima remis bila langkahnya buruk — setiap game menjadi opsi milik penerima. Langkah penerima yang mematikan tawaran menutupnya tanpa timer.

### Tawaran berulang

- **Bebas menawar lagi selama tidak ada tawaran aktif.** Satu tawaran hidup per game; tawaran kedua — dari siapa pun — **ditolak backend**.
- **Menyimpang dari Lichess, dengan alasan yang dicatat.** Lichess menegakkan cooldown **20 ply per pemain** (`Game.scala:72-73`: `g.drawOffers.lastBy(color).exists(_ >= g.ply - 20)`). Cooldown itu ada untuk membatasi **kebisingan chat**: setiap tawaran Lichess menulis pesan sistem ke chat game (`Drawer.scala:58`, `whiteOffersDraw`/`blackOffersDraw`). Di sini tawaran **tidak menulis apa pun ke Discord** — ia hidup hanya di papan dan di satu kalimat opsional pada ping giliran. Kebisingan yang cooldown itu batasi tidak pernah tercipta, dan ongkos penolakan berulang hanyalah satu klik di papan penerima.
- **Tawaran saat tawaran masih terbuka ditolak seluruhnya**, termasuk bila yang menekan adalah **penerima**. Lichess memperlakukannya sebagai **penerimaan** (`Drawer.scala:47`), tapi di sana tidak ada tombol Terima — tawaran adalah satu-satunya cara menerima. Di sini tombol Terima ada dan tertulis, jadi menerjemahkan tawaran menjadi penerimaan berarti satu tombol melakukan hal yang tidak tertulis di labelnya. Satu aturan tunggal lebih murah daripada satu pengecualian yang harus dijelaskan di papan.
- **Tanpa tombol tarik tawaran.** Lichess tidak punya, dan di sini tidak dibutuhkan: penawar yang menawar di giliran sendiri tidak kehilangan apa pun dengan melangkah (langkahnya tidak membunuh tawaran), dan penawar yang menawar di giliran lawan tidak kehilangan waktu sama sekali.

### Menerima dan menolak

- **Terima: satu tekan**, lalu papan menampilkan keadaan **mengirim** sampai siaran state dari server menyatakan game selesai — pola ADR-0020 apa adanya, dan dengan alasan yang sama: menerima remis menulis `rating_ledger` dan tidak bisa ditarik.
- **Terima tidak butuh dua langkah seperti Menyerah.** Pemain sedang **menjawab pertanyaan eksplisit** yang diajukan lawannya; konfirmasi kedua untuk tindakan yang sudah berupa jawaban hanya menunda jawabannya. Menyerah berbeda karena tidak ada yang bertanya apa pun.
- **Tolak: satu tekan, tanpa konfirmasi.** Menolak aman dan bisa diulang; ia hanya mematikan tawaran.
- **Penolakan tidak menulis apa pun ke Discord.** Ia terlihat di papan kedua pemain lewat siaran state. Konsekuensi yang diterima: penawar yang papannya tertutup tidak tahu tawarannya ditolak sampai ia membuka papannya lagi.

### Jalur tutupnya

- **Menerima remis menulis lewat satu fungsi tutup game** (ADR-0015): `result='draw'`, **`end_reason` NULL**, `draw_type='agreed'`. Predikat berating ADR-0008/0012 dievaluasi **apa adanya** — remis yang disepakati menilai rating, seperti remis sejak ADR-0012. Hasil game + entri rating dalam **satu transaksi** (ADR-0008).
- **`end_reason` NULL adalah bentuk yang sudah diputuskan ADR-0015:104**, bukan lubang baru: `stalemate`, `fifty_move`, `threefold`, dan `agreed` semuanya hidup di `draw_type`, dan tidak ada satu pun dari keempatnya yang mengisi `end_reason`. Menambah nilai `agreed` di `end_reason` akan membuat dua kolom menjawab pertanyaan yang sama — persis yang ADR-0015:127 tolak.
- **Jam diselesaikan lebih dulu, lewat fungsi jam yang sama dengan tick** — aturan ADR-0020, dan ia berlaku di sini dari arah yang lain. Bila penerima menekan Terima di jendela 1 detik di mana **jamnya sendiri** sudah melewati nol tapi tick belum menutup game, hasilnya **`timeout` dan ia kalah**, bukan remis. Tanpa ini, menerima remis adalah cara menyelamatkan diri dari bendera yang sudah jatuh.
- **Bendera yang jatuh saat tawaran terbuka tetap kalah.** Bila penerima membiarkan jamnya habis tanpa menjawab, hasilnya `timeout` — bukan remis. **Lichess menyimpang di sini**: `Finisher.scala:52-53` mengubah flag-fall menjadi `Draw` ketika lawannya punya tawaran terbuka. Cabang itu **tidak disalin**, dengan alasan yang ditulis: penerima tidak boleh lolos dari kekalahan dengan mengabaikan pertanyaan, dan penawar tidak boleh memenangkan apa pun karena tawarannya sendiri. ADR-0015 tidak berubah, dan pengecualian pada "kehabisan waktu = kalah" tetap satu: bahan tak cukup.
- **Sesudah transaksi**, berurutan: hapus **Ping giliran** yang terlacak untuk game itu (ADR-0019), kirim **pesan hasil ber-mention kedua pemain** (ADR-0015), lalu serahkan ke pipeline analisa (ADR-0009). Tidak ada I/O Discord di dalam transaksi.
- **Langkah yang tiba setelah remis disepakati ditolak**, sama seperti setelah sebab apa pun (ADR-0015:78).

### Kabar sampai ke lawan

- **Ping giliran ADR-0019 yang membawanya**, bukan jenis pesan baru. Isi ping bertambah **satu kalimat opsional**: bila saat ping disusun ada tawaran terbuka dari lawan penerima ping, kalimat *"<nama> menawarkan remis."* ditambahkan.
- **Nol jenis pesan keempat, nol pengecualian pada aturan "satu ping per ply".** ADR-0019 sudah memutuskan bahwa mengulang pemberitahuan kepada orang yang sudah dipanggil adalah kebisingan yang Discord hukum; ping remis adalah pengulangan semacam itu.
- **Penawaran di giliran sendiri tetap sampai ke lawan lewat jalur ini**, dan itu bukan kebetulan: langkah penawar tidak membunuh tawaran, jadi ketika giliran berpindah ke lawan dan pingnya disusun, tawarannya masih terbuka dan kalimatnya ikut terkirim.
- **Lubang yang diterima sadar:** ping menyala paling cepat 75 detik ke dalam giliran di 5+3 (ADR-0019). Tawaran yang lahir **sesudah** ping untuk ply itu terkirim tidak akan pernah sampai ke lawan yang terputus. Menutupnya menuntut ping kedua untuk keadaan yang sama, atau menyunting pesan yang — karena edit tidak memicu notifikasi (fakta #10) — tidak memberi tahu siapa pun. Keduanya lebih mahal daripada lubangnya.
- **Hasil remis diumumkan lewat pesan baru ber-mention kedua pemain, segera**, terpisah dari pesan analisa — seragam dengan ADR-0015 dan ADR-0020. Remis yang disepakati menggerakkan rating, jadi ia sama pentingnya dengan menyerah dan tidak boleh bergantung pada pipeline yang bisa gagal tiga kali.

### Armageddon

- **Tawaran remis diizinkan, tanpa kode tambahan.** ADR-0015:84 sudah mengunci bahwa armageddon boleh berakhir dengan cara apa pun dan bahwa "remis = hitam menang" adalah **pembaca hasil akhir**, bukan larangan. Pembacanya sudah ada, jadi mengizinkan berarti nol kondisi baru.
- **Secara rasional tawarannya mati**: putih tidak pernah menang dengan menerima, hitam tidak pernah butuh menawar. Tombolnya tetap tampil dan tetap berfungsi, dan hasilnya dibaca apa adanya. Kode mati-lemah lebih murah daripada satu cabang kondisi yang menyala pada satu game per pertandingan.
- **Lichess tidak punya penanganan armageddon sama sekali** di pohon `lila` (`grep -ril "armag" .` → 0 berkas), jadi tidak ada preseden yang perlu disalin atau ditolak di sini.

### Cabang Lichess yang sengaja tidak disalin

Dua cabang Lichess berhubungan dengan tawaran remis dan tidak satu pun disalin. Keduanya dicatat supaya implementor berikutnya tidak menyalinnya tanpa berpikir.

- **Pengulangan tiga kali diperiksa sebelum tawaran** (`Drawer.scala:43-46`): menekan tombol remis pada posisi tiga kali langsung menjadi **klaim**, bukan tawaran. Cabang ini **tidak bisa dicapai di sini** dengan alasan yang sama seperti ADR-0020 menolak cabang remis-menyerah: bila backend menutup game tiga kali di langkah yang melahirkannya, tidak pernah ada posisi tiga kali yang menggantung saat tombol tawaran diperiksa. **Ketergantungan ini ditiketkan: [Remis otomatis](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/28)** — bila ticket itu memutuskan tiga kali **tidak** menutup game, cabang ini berubah dari tak-tercapai menjadi wajib.
- **Menawar saat tidak bisa kalah dikonversi menjadi klaim bahan-tak-cukup** (`Drawer.scala:54-55`): `if RoundGame.cannotLose(pov) then finisher.other(pov.game, _.InsufficientMaterialClaim, None)`. Sama seperti ADR-0020: posisi bahan-tak-cukup sudah ditutup backend di langkah yang melahirkannya (ADR-0015), jadi cabangnya tak bisa tercapai.

## Alasan

- **Satu permukaan, bukan dua.** Sama dengan ADR-0020, dan di sini alasannya lebih kuat karena lawan sudah pasti punya sesi terikat. Menambah tombol Discord berarti menambah jalur hak tekan dan jalur tutup kedua untuk satu tindakan yang sudah punya rumah.
- **Jam tidak dijeda, titik.** Ini satu-satunya keputusan di ticket ini yang tidak punya kompromi: jeda apa pun membuat tawaran remis menjadi mesin penghenti jam, dan pemain yang kalah waktu akan memakainya terus. Alternatif "hanya jam penerima dijeda" lebih buruk lagi — ia memberi waktu berpikir gratis untuk setiap posisi yang ditawari.
- **Mati oleh langkah penerima, bukan langkah siapa pun.** Versi "siapa pun" terdengar lebih aman tapi membunuh tawaran di giliran penawar sendiri, yaitu setengah dari seluruh penawaran yang mungkin. Versi penerima menutup celah posisi-berubah dengan tepat: yang berubah adalah posisi yang **penerima** hadapi ketika ia harus menjawab.
- **Tanpa timer.** Tawaran tidak butuh kedaluwarsa karena umurnya sudah dibatasi jam yang berjalan dan giliran penerima. Menambah timer berarti menambah satu konstanta yang harus dipertanggungjawabkan tanpa preseden — dan Lichess sendiri tidak punya.
- **Tanpa cooldown.** Cooldown 20 ply Lichess lahir dari kebisingan chat yang di sini tidak ada. Menyalinnya berarti menambah penghitung per pemain per game untuk masalah yang tidak tercipta.
- **Tawaran ganda ditolak, bukan diterjemahkan menjadi penerimaan.** Lichess boleh melakukan itu karena ia tidak punya tombol Terima. Di sini tombolnya ada, dan tombol yang melakukan hal berbeda dari labelnya adalah bug yang menunggu dilaporkan.
- **Terima satu tekan, Menyerah dua.** Bedanya bukan tingkat kerusakan — keduanya menulis rating dan tak bisa ditarik — melainkan **apakah ada yang bertanya**. Menyerah adalah tindakan yang pemain mulai sendiri; menerima adalah jawaban atas pertanyaan yang sudah diajukan lawan.
- **Bendera tetap kalah walau tawaran terbuka.** Menyalin Lichess berarti penerima yang kalah posisi bisa memaksa remis hanya dengan **tidak menjawab**. Dan penawar akan diuntungkan oleh tawarannya sendiri, yang membuat menawar menjadi langkah bertahan yang sah — tepat yang Q kemarin tolak saat memilih "jam tidak dijeda".
- **Ping yang ada, bukan pesan baru.** ADR-0019 sudah membangun jalur memberi tahu pemain yang tidak menatap papannya. Menambah jenis pesan keempat untuk satu kalimat berarti satu lagi yang harus dihapus, dilacak, dan disepakati dengan jalur tutup.
- **`end_reason` NULL.** ADR-0015 sudah memisahkan "siapa" dari "kenapa" dan menaruh semua jenis remis di `draw_type`. Menyimpang di sini berarti mengamendemen ADR-0015 untuk satu kasus yang bentuknya sudah benar.

## Konsekuensi

- **`CONTEXT.md` mendapat satu istilah baru: Tawaran remis** — keadaan sebuah game di mana satu pemain telah mengajukan remis dan lawannya belum menjawab, berlangsung sampai penerima melangkah, menolak, atau game ditutup. Presedennya ADR-0019, yang menamai **Ping giliran** dan **Terhubung (Activity)** untuk keadaan sesaat yang dipakai ticket lain. "Kesepakatan" sudah hidup di dalam **Jenis remis** dan tidak butuh istilah kedua.
- **Tidak ada perubahan skema.** Tidak ada kolom, tabel, atau nilai `end_reason` baru. `draw_type='agreed'` sudah bernama sejak ADR-0015.
- **Tawaran hidup di memori proses**, seperti `pinged_ply` ADR-0019: `game_id` → (penawar, ply). **Restart menghapus semua tawaran**, dan itu tidak merugikan siapa pun — posisi tidak berubah, jam tidak berjalan saat bot mati, dan penawar bisa menawar lagi. Aman justru karena tidak ada yang perlu dipulihkan.
- **ADR-0019 dilengkapi, tidak diubah.** Isi pesan ping bertambah satu kalimat opsional; aturan satu-ping-per-ply, ambang, penghapusan, dan larangan `SUPPRESS_NOTIFICATIONS` semuanya tetap. Tidak ada jenis pesan baru.
- **ADR-0020 mendapat pemakai kedua polanya.** Fungsi "selesaikan jam lebih dulu" dipanggil jalur terima remis; keadaan **mengirim** di klien dipakai lagi untuk tindakan tak-bisa-ditarik; tenggang 500 ms tetap milik model jam dan kini dibaca tiga jalur (tick, menyerah, terima remis).
- **ADR-0015 tidak berubah.** Satu fungsi tutup game mendapat pemakai baru, pengecualian "kehabisan waktu = kalah" tetap satu (bahan tak cukup), dan `end_reason`/`draw_type` dievaluasi apa adanya.
- **ADR-0008/0012 tidak berubah.** Remis yang disepakati menilai rating lewat predikat yang sudah ada.
- **ADR-0018 tidak berubah.** Mesin tetap selalu menolak; yang baru hanyalah bahwa penolakannya terlihat sebagai penolakan.
- **[ADR-0007](0007-pencocokan-klien-ke-game.md) mendapat pemakai baru** untuk WebSocket yang sudah ada: intent tawar, terima, dan tolak adalah pesan lain di jalur terverifikasi yang sama.
- **Ticket baru lahir: [Remis otomatis](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/28).** Cabang "pengulangan tiga kali sebelum tawaran" yang tidak disalin bergantung padanya — alasan tak-tercapainya hanya sah bila ticket itu memutuskan game memang ditutup di langkah yang melahirkan remis-remis itu.
- **[Desain interaksi papan catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/8) mendapat lima keadaan untuk tombol Tawar remis**: **mati** (ply 0), **diam**, **kutawarkan** (menunggu jawaban lawan), **lawan-menawarkan** (prompt Terima/Tolak), dan **mengirim**. Ditambah tiga keadaan tombol Menyerah dari ADR-0020, papan kini menggambar dua tombol dengan total delapan keadaan. Ukuran, warna, dan penempatannya tetap milik #8.
- **Yang harus dibangun saat implementasi:** dua tombol papan dengan keadaannya, tiga pesan WebSocket (`offer_draw`, `accept_draw`, `decline_draw`) yang divalidasi backend, satu peta tawaran di memori, pembersihan tawaran di jalur commit langkah (sisi penerima) dan jalur tutup game, satu pemanggilan "selesaikan jam" di depan fungsi tutup game pada jalur terima, dan satu kalimat opsional di penyusun isi ping giliran.
- **Tidak ada intent Discord baru.** Tombol di dalam Activity bukan message component; tidak ada `custom_id` dan tidak ada interaksi Discord yang terlibat.

## Verifikasi

**Yang tidak perlu diulang:** Activity hanya bisa dibuka lewat HTTPS publik dan sinkronisasi harus WebSocket (ticket #2). Satu fungsi tutup game, kosakata `end_reason`/`draw_type`, tenggang 500 ms, dan aturan armageddon boleh berakhir dengan cara apa pun (ADR-0015). Hasil + rating satu transaksi (ADR-0008). Predikat berating (ADR-0012). WebSocket terikat `game_id` (ADR-0007). Ping giliran: satu per ply, dihapus di jalur tutup, mention di `content`, `SUPPRESS_NOTIFICATIONS` dilarang (ADR-0019). Jam diselesaikan lebih dulu dan keadaan mengirim untuk tindakan tak-bisa-ditarik (ADR-0020). Mesin selalu menolak remis (ADR-0018). Edit pesan tidak memicu notifikasi (ticket #10).

**Terverifikasi saat ticket ini (riset sumber primer `lichess-org/lila` @ `ba82ec25ac70af057ca5c217446ec4d517ba0b57`, jangan ulangi):**

| Klaim | Bukti |
|---|---|
| Tawaran hidup hanyalah **boolean per pemain**, tanpa timestamp | `modules/core/src/main/game/Player.scala:18` — `isOfferingDraw: Boolean = false,` |
| Riwayat tawaran dicatat sebagai **himpunan ply per warna**, bukan waktu | `modules/core/src/main/game/data.scala:31` — `case class GameDrawOffers(white: Set[Ply], black: Set[Ply]):` |
| Lichess **mengizinkan tawaran di giliran siapa pun**, dinyatakan eksplisit | `data.scala:43-44` — `// lichess allows to offer draw on either turn,` / `// normalize to pretend it was done on the opponent turn.` |
| **Tidak ada timeout, expiry, atau auto-decline** di seluruh pohon `lila` | grep menyeluruh; satu-satunya penulis `isOfferingDraw=false` adalah `Drawer.scala:72` (tolak) dan `:83` (set), plus `$unset` DB saat game selesai di `GameRepo.scala:369-370`. Tidak ada scheduler/timer yang menyentuh tawaran |
| **Langkah lawan** memicu penolakan sintetis otomatis | `modules/round/src/main/MovePlayer.scala:77` — `if pov.opponent.isOfferingDraw then round ! RoundBus.Draw(pov.player.id, false)` |
| **Cooldown 20 ply per pemain** | `modules/game/src/main/Game.scala:72-73` — `def playerHasOfferedDrawRecently(color: Color) = g.drawOffers.lastBy(color).exists(_ >= g.ply - 20)` |
| Syarat menawar, termasuk **tanpa suku giliran** dan **tanpa lawan AI** | `Game.scala:75-82` — `g.started && g.playable && g.ply >= 2 && !g.player(color).isOfferingDraw && !g.opponent(color).isAi && !g.playerHasOfferedDrawRecently(color) && !g.swissPreventsDraw && !g.rulePreventsDraw` |
| **Lantai 2 ply** untuk tawaran | `Game.scala:77` (`g.ply >= 2`) dan `modules/core/src/main/game/Game.scala:157,167` — `drawable = playable && !abortable && …`, `abortable = status == Status.Started && playedPlies < 2 && nonMandatory` |
| **Menawar saat tawaran terbuka = MENERIMA**, bukan tawaran baru | `modules/round/src/main/Drawer.scala:47-53` — `case pov if pov.opponent.isOfferingDraw =>` … `_.Draw,` |
| **Pengulangan tiga kali diperiksa SEBELUM cabang tawaran** | `Drawer.scala:43-46` — `case pov if pov.game.history.threefoldRepetition => finisher.other(pov.game, _.Draw, None)` |
| Menawar saat tidak bisa kalah dikonversi jadi **klaim bahan tak cukup** | `Drawer.scala:54-55` — `if RoundGame.cannotLose(pov) then finisher.other(pov.game, _.InsufficientMaterialClaim, None)` |
| **Tidak ada status "remis disepakati"** — hanya satu `Draw` | `scalachess core/src/main/scala/Status.scala:22` — `case Draw extends Status(34)`; `:27-29` memberi `InsufficientMaterialClaim` sebagai status **berbeda** |
| Alasan remis **diturunkan saat dibaca**, tidak disimpan | `modules/game/src/main/Game.scala:199-203` — `else if g.drawOffers.normalizedPlies.exists(g.ply <= _) then DrawReason.MutualAgreement.some` |
| **Bendera yang jatuh saat tawaran terbuka menghasilkan DRAW, bukan kemenangan** | `modules/round/src/main/Finisher.scala:52-53` — `else if game.player(!game.player.color).isOfferingDraw then apply(game, _.Draw, None, …drawOfferAccepted…)` |
| Setiap tawaran Lichess **menulis pesan sistem ke chat game** — sumber kebisingan yang cooldown batasi | `Drawer.scala:58` — `messenger.system(g, color.fold(trans.site.whiteOffersDraw, trans.site.blackOffersDraw).txt())`, dipasangkan dengan cooldown `Game.scala:72-73` |
| Tawaran Lichess **membersihkan dirinya saat game selesai** | `modules/game/src/main/GameRepo.scala:365-373` — `("p0." + PF.isOfferingDraw) -> true` / `("p1." + PF.isOfferingDraw) -> true` |
| Klien menampilkan **bar pertanyaan inline** dengan tombol ya/tidak, bukan modal | `ui/round/src/view/table.ts:59-62` — `promptVNode: hl('div.question', …[noBtn, hl('p', o.prompt), yesBtn])`; `ui/round/src/ctrl.ts:708-714` |
| Tawaran Lichess memakai **konfirmasi 3 detik** yang membatalkan diri | `ui/round/src/ctrl.ts:866-878` — `this.drawConfirm = setTimeout(() => { this.offerDraw(false); }, 3000);` |
| **Tidak ada penanganan armageddon** di seluruh pohon `lila` | `grep -ril "armag" .` → 0 berkas pada commit ini |
| Chess.com **tidak mendokumentasikan** umur tawaran, cooldown, atau auto-decline | `support.chess.com/en/articles/8572743-how-do-draws-work` hanya memuat cara menekan tombol; `8615342-what-is-spamming` hanya menyebut tawaran berulang sebagai spam |

**Yang tidak diklaim:** bahwa Chess.com punya aturan umur atau cooldown tertentu — tidak ada angka yang terbit publik, dan tidak ada yang dikarang. Juga tidak diklaim bahwa `Drawer.scala` cabang tawaran-ganda adalah satu-satunya jalur penerimaan Lichess; board/bot API `PlayApi.scala:89-91` memiliki jalur `draw true` tersendiri yang tidak diperiksa lebih jauh karena tidak relevan bagi platform ini.

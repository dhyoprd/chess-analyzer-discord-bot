# CONTEXT — Platform Catur Discord

Glosarium domain. Hanya istilah dan artinya — tanpa detail implementasi.

## Istilah inti

**Activity** — aplikasi web tertanam di dalam Discord, dimuat di iframe lewat Embedded App SDK. Di proyek ini: tempat pemain bermain catur dengan papan drag-and-drop. Dibedakan dari "bot" yang berbasis pesan.

**Bot** — aplikasi Discord berbasis slash command dan pesan. Di proyek ini: menyediakan `/challenge`, `/stats`, dan mengelola turnamen. Satu application object Discord merangkap keduanya (Activity dan bot).

**Game** — satu permainan catur antara dua pemain, dari langkah pertama sampai berakhir. Memiliki varian, format jam, hasil, dan alasan berakhir.

**Papan** — tampilan permainan di dalam Activity: posisi, langkah, dan jam. Satu Activity menampilkan satu papan pada satu waktu.

**Pemilih game** — daftar game hidup milik pemain, ditampilkan di Activity saat ia punya lebih dari satu. Memilih satu game membuka papannya. Seorang pemain hanya bisa menempel ke game di mana ia peserta.

**Buka Papan** — tindakan pemain membuka papan sebuah game dari Discord. Berbeda dari **Masuk**, yang menyatakan kehadiran; kehadiran tidak membuka papan, dan papan bisa dibuka tanpa menekan Masuk.

**Pertandingan** — satu slot bracket turnamen knockout: dua pemain yang harus menghasilkan tepat satu pemenang. Berbeda dari game, satu pertandingan bisa memuat beberapa game (game pertama, game ulang, armageddon). Di luar turnamen tidak ada pertandingan — hanya game.

**Langkah (Move)** — satu giliran pemain, dalam notasi SAN. Setiap langkah menyimpan FEN setelahnya dan waktu berpikir. Eval dan klasifikasi **bukan** milik langkah, melainkan milik **Analisa** — supaya menjalankan analisa ulang tidak menghancurkan hasil sebelumnya.

**Posisi** — satu keadaan papan yang dievaluasi engine. Satu game dengan N langkah punya N+1 posisi: posisi awal, lalu satu posisi setelah tiap langkah. Engine bekerja per **posisi**, bukan per langkah; satu posisi melayani dua langkah sekaligus — ia menjadi "sesudah" bagi langkah sebelumnya dan "sebelum" bagi langkah berikutnya.

**Analisa** — satu kali evaluasi engine atas seluruh posisi sebuah game. Menghasilkan akurasi tiap pemain dan klasifikasi tiap langkah, keduanya menempel pada analisa itu. Satu game bisa punya beberapa analisa; yang ditampilkan adalah **analisa selesai yang terbaru**. Analisa yang gagal juga tercatat, supaya tidak dicoba ulang tanpa henti.

**Analisa ulang** — menjalankan analisa baru atas game yang sudah pernah dianalisa, menghasilkan catatan analisa tersendiri tanpa menghapus yang lama. Dipicu pemain lewat perintah, bukan otomatis.

**Klasifikasi langkah** — penilaian kualitas satu langkah berdasarkan **selisih win-chance sebelum dan sesudah langkah**, bukan selisih centipawn mentah. Ini mengikuti Lichess. Tiga tingkat:

| Tingkat | Selisih win-chance |
|---|---|
| Inaccuracy | ≥ 0.1 |
| Mistake | ≥ 0.2 |
| Blunder | ≥ 0.3 |

Win-chance dihitung dengan `wc(cp) = 2/(1 + exp(-0.00368208 × cp)) − 1`, pada skala −1 sampai +1, dengan cp di-clamp ke ±1000 lebih dulu. Selisihnya dibalik sesuai pihak yang melangkah, sehingga perbandingan selalu dari sudut pandang pelangkah.

Alasan memakai win-chance dan bukan centipawn: kehilangan 300cp di posisi seimbang adalah blunder besar, tapi kehilangan 300cp di posisi yang sudah menang telak hampir tidak berarti apa-apa. Centipawn tidak punya arti bagi manusia tanpa konteks posisi.

**Akurasi** — skor 0-100% per pemain per game, dihitung dengan rumus Lichess (berbasis win-percentage, bukan centipawn mentah).

**Rating** — angka kekuatan pemain, memakai sistem Glicko-2. Berubah hanya dari **game berating**. Setiap game selesai langsung memperbarui rating — tidak ada pembaruan berkala. Ketidakpastian rating (RD) melebar seiring waktu nyata sejak game berating terakhir, sehingga pemain yang lama hilang kembali dengan rating yang tidak lagi dipercaya penuh.

**Berating** — sebutan untuk game yang **dinilai rating**, dan untuk populasi game itulah statistik rating bermakna. Lawannya adalah game yang **tidak memenuhi predikat berating**: lawan komputer, game impor, armageddon, dan game yang ditinggalkan. Hanya game berating yang mengubah rating, dan hanya game berating yang dihitung di blok rating `/stats` serta di klasemen. Game non-berating tetap punya pemain, langkah, dan analisa — ia hanya tidak pernah menyentuh rating. **Walkover dan bye bukan game**, jadi keduanya tidak termasuk populasi mana pun dan tidak muncul di rekor.

**Provisional** — status pemain yang ratingnya belum mapan karena **ketidakpastiannya (RD) masih lebar**, bukan karena jumlah game yang sedikit. Ambangnya satu dan berlaku di seluruh platform, termasuk penentuan unggulan turnamen. Pemain provisional tetap tampil di klasemen, dengan penanda. Pemain yang belum pernah memainkan satu pun game berating **belum punya rating** dan belum muncul di klasemen.

**Pemain (Player)** — profil yang dibuat otomatis dari ID Discord saat pertama bermain. Tidak ada registrasi. Menyimpan rating, statistik, dan tautan opsional ke akun Lichess/Chess.com.

**Pemain putih / Pemain hitam** — dua peran dalam satu game. Bukan "pemain 1" dan "pemain 2" — warna menentukan siapa melangkah lebih dulu.

**Jam catur** — waktu berpikir yang tersisa untuk tiap pemain. Dijeda saat bot mati; **tetap berjalan** saat pemain menutup Activity. Kehabisan waktu = kalah langsung.

**Ditinggalkan** — status game yang tidak menerima langkah selama 24 jam **waktu bot hidup**. Saat bot mati, hitungannya berhenti — bot yang mati berhari-hari tidak menghukum pemain. Game tetap dianalisa sampai langkah terakhir, tanpa pemenang.

Di dalam turnamen, game yang ditinggalkan **tetap tanpa pemenang di papan** — tapi pertandingannya dimenangkan pemain yang tidak sedang giliran, karena pertandingan knockout wajib menghasilkan tepat satu pemenang. Hasil papan dan hasil pertandingan dicatat terpisah.

**Peringkat** — posisi seorang pemain dalam urutan rating seluruh platform. Peringkat hanya dimiliki pemain yang sudah punya rating; pemain yang belum pernah memainkan game berating tidak punya peringkat, bukan peringkat terakhir. Urutannya rating menurun, lalu jumlah game berating menurun, lalu **`player_id` menaik**. Pemain provisional ikut bersaing tanpa dipisahkan.

**Klasemen** — daftar terurut pemain platform menurut **Peringkat**-nya. Hanya memuat pemain yang punya rating; pemain bayangan tidak pernah muncul di sini.

**Tanpa hasil** — hasil sebuah game yang selesai tanpa pemenang dan tanpa remis, yaitu game yang **ditinggalkan**. Dihitung terpisah dari menang, kalah, dan remis, karena papan tidak menyatakan siapa yang menang dan remis bukan kesimpulan yang benar.

**Komposisi** — rincian asal-usul game di blok "semua game" pada `/stats`: **platform**, **impor**, atau **lawan komputer**. Ketiganya berasal dari satu fakta yang sama (asal game), sehingga setiap game jatuh tepat di satu jenis dan jumlahnya selalu cocok dengan total rekor di sebelahnya. Berbeda dari **Berating**, yang merupakan predikat penilaian rating dan memotong populasi di dalam "platform".

**Format jam** — pasangan waktu dasar dan increment, misalnya "3+2" berarti 3 menit dasar dengan tambahan 2 detik tiap langkah. Dua angka inilah yang disimpan; kategorinya diturunkan darinya.

**Kategori kecepatan** — penggolongan game berdasarkan perkiraan durasi totalnya: **bullet**, **blitz**, **rapid**, **classical**. Diturunkan dari format jam, bukan disimpan terpisah. Ambangnya mengikuti Lichess.

**Pool rating** — ruang lingkup tempat sebuah rating berlaku. Platform bisa punya satu rating untuk semua game, atau rating terpisah per kategori kecepatan (seperti Lichess). Rating selalu terikat pada satu pool. Di platform ini hanya ada **satu pool**: semua game berating — semua kategori kecepatan dan semua varian, termasuk Chess960 — memakai rating yang sama.

**Pemain bayangan** — pemain yang tidak berasal dari Discord. Ada **dua jenis**, dan aturan klaimnya berbeda:

- **Berbasis akun** — berasal dari tautan Lichess/Chess.com. Punya identitas `(platform, username)`, bisa diklaim.
- **Berbasis nama** — berasal dari header PGN. Hanya punya nama, **tidak bisa diklaim**, karena nama bukan bukti kepemilikan.

Keduanya tidak muncul di klasemen dan tidak pernah menyatu otomatis satu sama lain.

**Akun eksternal** — identitas pemain di Lichess atau Chess.com, ditulis `platform` + `username`. Satu akun hanya boleh tertaut ke satu pemain, dan seorang pemain boleh punya satu akun per platform.

**Klaim akun** — tindakan pemain menautkan akun eksternal ke profil Discord-nya. Untuk Lichess dibuktikan dengan kode verifikasi di bio akun; Chess.com tidak punya cara pembuktian apa pun, sehingga klaimnya ditandai **belum terverifikasi**. Klaim memindahkan **semua** game akun itu ke pemain sekaligus, dan tautannya bisa dilepas — game yang sudah dipindahkan tetap miliknya.

**Impor** — tindakan memasukkan satu game eksternal ke platform lewat tautan atau berkas PGN, untuk dianalisa. Game impor **tidak** mengubah rating. Game yang belum selesai tidak bisa diimpor.

**Challenge** — tawaran bermain dari satu pemain ke pemain lain lewat bot: format jam, pilihan warna, dan batas waktu berlaku. Menerima challenge berarti memulai game. Challenge yang tidak dijawab akan kedaluwarsa.

**Varian** — bentuk aturan catur yang dimainkan. Proyek ini mendukung **catur standar** dan **Chess960** (posisi awal acak dari 960 kemungkinan).

**Turnamen** — kompetisi format **gugur (knockout)** antara 4–16 pemain, dilengkapi **bye** ke pangkat dua terdekat. Siapa pun boleh membuatnya tanpa admin; pembuat otomatis terdaftar dan menjadi **pengendali**-nya. Game yang benar-benar dimainkan mengubah rating; walkover dan bye tidak. Satu guild hanya boleh punya satu turnamen aktif.

**Pengendali** — pemain yang memegang kendali administratif atas satu turnamen: menutup pendaftaran dan membatalkannya. Awalnya pembuat; berpindah ke peserta terlama yang masih terdaftar bila pembuat mundur sebelum turnamen dimulai.

**Pendaftaran** — jendela saat pemain bisa masuk dan keluar dari turnamen, sebelum bracket disusun. Ditutup oleh pengendali, atau otomatis setelah **24 jam waktu bot hidup**. Jendela mulai berjalan saat turnamen dibuat, tidak bisa diperpanjang, dan tidak punya plafon waktu nyata. Seperti **Ditinggalkan**, ia hanya maju saat bot hidup — turnamen yang dibuat lalu ditinggalkan tetap kehilangan jendelanya.

**Bye** — pemain yang lolos satu ronde tanpa bertanding, karena jumlah peserta bukan pangkat dua. Bye diberikan ke unggulan teratas dan **tidak** mengubah rating.

**Walkover** — kemenangan tanpa game, karena lawan tidak hadir atau meninggalkan pertandingan di tengah jalan. **Tidak** mengubah rating — tidak ada game yang dimainkan.

**Mundur (withdraw)** — pemain keluar dari turnamen **sebelum pertandingannya dimulai**; lawan otomatis maju. Berbeda dari walkover, yang terjadi setelah pertandingan berjalan. Mundur sebelum bracket disusun boleh ditarik kembali; setelah bracket disusun, mundur bersifat final.

**Masuk** — tindakan pemain menekan tombol pada pesan pairing untuk menyatakan kehadirannya. Pertandingan dimulai saat **kedua** pemain sudah masuk. Tidak menekan sampai batas waktu berarti walkover.

**Batas waktu pertandingan** — lama bot menunggu pemain menekan Masuk atau menyelesaikan game, dihitung dalam **waktu bot hidup** (bukan waktu nyata), konsisten dengan definisi Ditinggalkan. Lewat batas ini, pertandingan diputuskan sebagai walkover secara otomatis.

**Waktu bot hidup** — penghitung yang **hanya** maju selama proses bot berjalan, dan berhenti saat bot mati. Ia dasar dari seluruh batas waktu di platform: **Ditinggalkan** (24 jam), **Batas waktu pertandingan** (24 jam), **Pendaftaran** (24 jam), dan auto-abandon turnamen (72 jam). Ketiga yang bernilai 24 jam memakai **satu konstanta yang sama**. Karena penghitungnya tidak terlihat pemain, durasi yang tersisa selalu ditampilkan sebagai perkiraan ("sekitar"), bukan janji jam dinding.

**Armageddon** — game penentu terakhir pada pertandingan knockout yang masih seri setelah game ulang. **Putih mendapat waktu lebih banyak** daripada hitam (hitam 80% dari waktu putih), dan **remis berarti hitam menang**. Ini mengikuti konvensi FIDE dan Chess.com. Armageddon **tidak** mengubah rating, karena kondisinya sengaja tidak setara.

**Lawan komputer** — mode bermain melawan Stockfish pada tingkat preset (800/1200/1600/2000 Elo). **Tidak** memengaruhi rating.

**State otoritatif** — sumber kebenaran posisi papan. Di proyek ini **backend Python**, bukan Activity. Activity hanya mengirim *niat* langkah; backend yang memvalidasi dan menentukan hasilnya.

**Game eksternal** — game yang tidak dimainkan di Activity kita, melainkan diimpor lewat PGN atau tautan dari Lichess/Chess.com untuk dianalisa.

## Istilah Discord yang dipakai

**Guild** — satu server Discord. Proyek ini dirancang untuk **satu guild** saja.

**Instance** — satu sesi Activity yang sedang berjalan, diidentifikasi `instance_id`. Setiap kali Activity dibuka, instance baru dibuat; semua yang bergabung ke instance yang sama mendapat `instance_id` yang sama. Backend **tidak** memakainya untuk mengenali klien atau mencocokkannya ke game — `instance_id` berubah tiap Activity dibuka, jadi ia tidak bisa menjadi kunci apa pun yang bertahan.

**Embed** — pesan kaya berformat di Discord. Batas: **6000 karakter gabungan** (title + description + field.name + field.value + footer.text + author.name) untuk semua embed dalam satu pesan; **25 field** per embed; **10 embed** per pesan. Per-field: description 4096, title dan field.name 256, **field.value 1024**, footer.text 2048. Yang mengikat untuk daftar langkah adalah `field.value` 1024, bukan total 6000. Discord **menghitung** penanda markdown seperti `**tebal**` sebagai bagian dari batas ini.

## Istilah yang sengaja dihindari

- **"Bot catur Discord"** untuk menyebut Activity — bot dan Activity adalah dua hal berbeda di sini.
- **"Elo"** untuk menyebut rating pemain — sistemnya Glicko-2. "Elo" hanya dipakai untuk menyebut preset tingkat lawan komputer.
- **"Skor"** tanpa keterangan — selalu sebutkan "akurasi" atau "rating", karena keduanya berbeda.

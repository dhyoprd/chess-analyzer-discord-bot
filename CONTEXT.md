# CONTEXT — Platform Catur Discord

Glosarium domain. Hanya istilah dan artinya — tanpa detail implementasi.

## Istilah inti

**Activity** — aplikasi web tertanam di dalam Discord, dimuat di iframe lewat Embedded App SDK. Di proyek ini: tempat pemain bermain catur dengan papan drag-and-drop. Dibedakan dari "bot" yang berbasis pesan.

**Bot** — aplikasi Discord berbasis slash command dan pesan. Di proyek ini: menyediakan `/challenge`, `/stats`, dan mengelola turnamen. Satu application object Discord merangkap keduanya (Activity dan bot).

**Game** — satu pertandingan catur antara dua pemain, dari langkah pertama sampai berakhir. Memiliki varian, format jam, hasil, dan alasan berakhir.

**Langkah (Move)** — satu giliran pemain, dalam notasi SAN. Setiap langkah menyimpan FEN setelahnya, waktu berpikir, eval, dan klasifikasi.

**Analisa** — proses evaluasi engine atas seluruh langkah sebuah game. Menghasilkan akurasi tiap pemain dan daftar langkah bermasalah.

**Klasifikasi langkah** — penilaian kualitas satu langkah berdasarkan **selisih win-chance sebelum dan sesudah langkah**, bukan selisih centipawn mentah. Ini mengikuti Lichess. Tiga tingkat:

| Tingkat | Selisih win-chance |
|---|---|
| Inaccuracy | ≥ 0.1 |
| Mistake | ≥ 0.2 |
| Blunder | ≥ 0.3 |

Win-chance dihitung dengan `wc(cp) = 2/(1 + exp(-0.00368208 × cp)) − 1`, pada skala −1 sampai +1, dengan cp di-clamp ke ±1000 lebih dulu. Selisihnya dibalik sesuai pihak yang melangkah, sehingga perbandingan selalu dari sudut pandang pelangkah.

Alasan memakai win-chance dan bukan centipawn: kehilangan 300cp di posisi seimbang adalah blunder besar, tapi kehilangan 300cp di posisi yang sudah menang telak hampir tidak berarti apa-apa. Centipawn tidak punya arti bagi manusia tanpa konteks posisi.

**Akurasi** — skor 0-100% per pemain per game, dihitung dengan rumus Lichess (berbasis win-percentage, bukan centipawn mentah).

**Rating** — angka kekuatan pemain, memakai sistem Glicko-2. Berubah hanya dari game lawan manusia. Game lawan komputer tidak mengubah rating. Game turnamen ikut mengubah rating.

**Provisional** — status pemain yang ratingnya belum mapan karena baru bermain sedikit game. Rating provisional ditampilkan dengan ketidakpastian lebar.

**Pemain (Player)** — profil yang dibuat otomatis dari ID Discord saat pertama bermain. Tidak ada registrasi. Menyimpan rating, statistik, dan tautan opsional ke akun Lichess/Chess.com.

**Pemain putih / Pemain hitam** — dua peran dalam satu game. Bukan "pemain 1" dan "pemain 2" — warna menentukan siapa melangkah lebih dulu.

**Jam catur** — waktu berpikir yang tersisa untuk tiap pemain. Dijeda saat bot mati; **tetap berjalan** saat pemain menutup Activity. Kehabisan waktu = kalah langsung.

**Ditinggalkan** — status game yang tidak menerima langkah lebih dari 24 jam. Game tetap dianalisa sampai langkah terakhir, tanpa pemenang.

**Varian** — bentuk aturan catur yang dimainkan. Proyek ini mendukung **catur standar** dan **Chess960** (posisi awal acak dari 960 kemungkinan).

**Turnamen** — kompetisi format **gugur (knockout)** antara 4/8/16 pemain. Siapa pun boleh membuatnya tanpa admin. Game turnamen mengubah rating.

**Lawan komputer** — mode bermain melawan Stockfish pada tingkat preset (800/1200/1600/2000 Elo). **Tidak** memengaruhi rating.

**State otoritatif** — sumber kebenaran posisi papan. Di proyek ini **backend Python**, bukan Activity. Activity hanya mengirim *niat* langkah; backend yang memvalidasi dan menentukan hasilnya.

**Game eksternal** — game yang tidak dimainkan di Activity kita, melainkan diimpor lewat PGN atau tautan dari Lichess/Chess.com untuk dianalisa.

## Istilah Discord yang dipakai

**Guild** — satu server Discord. Proyek ini dirancang untuk **satu guild** saja.

**Instance** — satu sesi Activity yang sedang berjalan, diidentifikasi `instance_id`. Backend memakai ini untuk memverifikasi klien.

**Embed** — pesan kaya berformat di Discord. Batas: 2000 karakter total, 25 field.

## Istilah yang sengaja dihindari

- **"Bot catur Discord"** untuk menyebut Activity — bot dan Activity adalah dua hal berbeda di sini.
- **"Elo"** untuk menyebut rating pemain — sistemnya Glicko-2. "Elo" hanya dipakai untuk menyebut preset tingkat lawan komputer.
- **"Skor"** tanpa keterangan — selalu sebutkan "akurasi" atau "rating", karena keduanya berbeda.

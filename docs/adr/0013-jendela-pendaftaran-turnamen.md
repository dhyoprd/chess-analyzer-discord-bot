# Jendela pendaftaran turnamen dihitung waktu bot hidup, lewat satu tick platform

## Konteks

Ticket [Jam jendela pendaftaran turnamen](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/19) menutup satu celah yang ditinggalkan [ADR-0006](0006-alur-turnamen-knockout.md). ADR itu memutuskan prinsipnya dengan tegas untuk dua batas waktu — batas no-show dan batas game ditinggalkan sama-sama dihitung **waktu bot hidup**, bukan waktu nyata (Q9, Q50) — tapi **jendela pendaftaran tidak ikut diputuskan** di sana (Q6 hanya menyebut "otomatis setelah 24 jam").

Celah itu lebih tajam daripada yang terlihat:

- Pemain **tidak bisa menekan Daftar saat bot mati** — tombolnya tidak dilayani siapa pun.
- Jadi bila jendela 24 jam dihitung waktu nyata dan bot mati 20 jam di tengahnya, pendaftaran efektif hanya terbuka **4 jam**. Peserta yang tidak kebagian bukan karena lambat, tapi karena bot mati.
- Itu persis ketidakadilan yang [ADR-0003](0003-self-hosted-with-paused-clocks.md) dan ADR-0006 ada untuk mencegah.

Dua kendala ikutan membentuk jawabannya. Pertama, sisa waktu berbasis bot-hidup **tidak bisa dihitung pemain dari jam dinding**, jadi ia harus ditampilkan. Kedua, `tournaments.registration_closes_at` yang dicatat ADR-0006 (Q54) berbentuk timestamp **waktu nyata**, sehingga ia tidak bisa menyatakan batas waktu berbasis bot-hidup.

## Keputusan

### Dasar jam dan durasi

- Jendela pendaftaran dihitung **waktu bot hidup**, sama seperti batas no-show dan batas game ditinggalkan.
- **Satu konstanta `24 jam waktu bot hidup` dipakai ketiganya.** Tidak ada konstanta tersendiri untuk pendaftaran.
- **Tanpa plafon waktu nyata.** Jendela hanya maju saat bot hidup; bot yang hampir tidak pernah hidup berarti platformnya sendiri tidak berjalan.
- Jendela **mulai berjalan saat turnamen dibuat**, bukan saat peserta pertama mendaftar.
- Jendela **tidak bisa diperpanjang maupun dibuka ulang.** Pengendali yang butuh lebih banyak waktu membatalkan lalu membuat turnamen baru — jalur yang sudah ada, karena hanya satu turnamen aktif per guild.

### Skema

- `tournaments.registration_closes_at` (Q54) **diganti** oleh **`registration_closes_in_alive_seconds`** — sisa detik waktu bot hidup, dihitung turun oleh tick. Mengikuti idiom `tournament_matches.deadline_alive_seconds` yang sudah dipakai ADR-0006 (Q30) untuk batas yang sama jenisnya.
- **`registration_reminder_sent`** (boolean) menjaga pengingat agar tidak terkirim berulang tiap tick.
- Saat jendela tutup, `registration_closes_in_alive_seconds` **di-NULL-kan**. Terisi berarti "pendaftaran masih berjalan"; NULL berarti "sudah tutup". Satu pembacaan, satu arti — dan "habis" tidak bisa tertukar dengan "ditutup manual sebelum habis".

### Tick platform

- **Ada satu tick platform**, dan ticket ini menamainya. Kontraknya: satu loop, dipanggil saat bot hidup, **memajukan semua penghitung bot-hidup lalu menutup yang habis**.
- **Interval, presisi, dan pemakaiannya untuk jam catur diserahkan ke ticket [Perilaku jam catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/21).** Jam catur menuntut ketelitian yang jauh lebih ketat daripada jendela pendaftaran, jadi mengunci interval di sini berisiko mengunci pilihan yang salah untuk #21. Yang ditetapkan di sini hanya keberadaan dan kontraknya, supaya #21 tidak menemukan mekanisme ketiga.
- Tick memajukan penghitung dengan **delta waktu nyata sejak tick terakhir**, di-clamp **≥ 0** dan **≤ 2× interval**. Mengurangi sebesar interval nominal akan menumpuk galat; membaca ulang dari agregat `bot_uptime` tiap tick menuntut kueri agregat rutin. Clamp bawah menahan jam yang mundur (penyesuaian NTP), clamp atas menahan lompatan.
- **Tick pertama berjalan segera saat start**, sebelum tick berkala, memakai jalur tutup yang sama. Keadaan "sudah habis tapi belum ditutup" tidak bisa bertahan melewati restart.
- Keterlambatan penutupan hingga satu interval **diterima**. Jendela pendaftaran tidak diukur pemain sampai detik, dan tick-bangun-tepat-di-ambang menambah penjadwalan yang harus diuji untuk keuntungan nol.

### Penutupan

- **Satu jalur kode, dua pemicu**: tombol Mulai milik pengendali, dan jendela yang habis. Bedanya hanya sebab yang dicatat. Dua jalur yang seharusnya melakukan hal sama adalah sumber bug yang berulang di proyek ini.
- Penutupan **selalu diumumkan lewat pesan baru ber-mention peserta terdaftar**: "pendaftaran ditutup — turnamen dimulai", atau "dibatalkan, peserta kurang dari 4". Jalur otomatis dan jalur manual berbunyi sama, jadi peserta tidak perlu tahu mana yang terjadi.
- **Mencapai 16 peserta tidak menutup jendela.** Peserta ke-16 hanya mengisi slot terakhir; Q64 memang sudah mengasumsikan pendaftaran tetap terbuka di angka itu.
- **Suksesi pengendali tidak mereset hitungan.** Jendela milik turnamen, bukan milik pengendali — reset akan memberi peserta baru 24 jam tambahan hanya dengan membuat pengendali mundur.
- Tombol **Daftar/Keluar dinonaktifkan** di pesan saat tutup, **dan** handler tetap menolak penekan yang lolos secara ephemeral. Dua lapis, karena pesan lama bisa gagal termutakhirkan — dan ADR-0006 menegaskan Discord tidak membatasi tombol per-pengguna sehingga hak tekan harus ditegakkan app-side.

### Sisa waktu ke pemain

- Sisa waktu **ditampilkan di pesan pendaftaran**, dibungkus kata **"sekitar"** supaya terbaca estimasi.
- Angka **diperbarui hanya saat roster berubah**, ditambah sekali oleh pesan pengingat. Tidak ada tick yang mengedit pesan: edit tidak memicu notifikasi (Q47), jadi yang dibeli hanya kesegaran angka dengan ongkos rate limit — dan angka yang sedikit basi tetap benar sebagai estimasi.
- **Satu pengingat** dikirim sebagai pesan baru ber-mention saat 12 jam waktu bot hidup terpakai, mengikuti pola pengingat batas pertandingan (Q47, Q69).

## Alasan

- **Jam bot hidup untuk semua batas waktu, tanpa kecuali.** Alasannya sama dengan yang melahirkan definisi `Ditinggalkan` di ADR-0005, dan membiarkan satu batas waktu memakai jam dinding akan membuat turnamen menghukum pemain atas kegagalan infrastruktur — hanya lewat pintu yang berbeda.
- **Satu konstanta, bukan tiga.** Ketiganya menjawab pertanyaan yang sama ("berapa lama bot menunggu manusia sebelum memutuskan sendiri"), dan tidak ada kebutuhan nyata yang membedakannya. Satu nilai berarti satu tempat mengubah, satu hal yang dijelaskan ke pemain.
- **Tanpa plafon waktu nyata.** Plafon menghidupkan kembali ketidakadilan yang ADR-0003 tolak, hanya pada skenario bot yang jarang hidup — dan dalam skenario itu plafon jadi **mengikat**, bukan jaring pengaman. Pengendali selalu bisa menutup manual.
- **Tick dinamai di sini, dispesifikkan di #21.** Tanpa kontrak bersama, tiga ADR akan menemukan tiga mekanisme penghitung bot-hidup. Tapi interval jendela pendaftaran dan interval jam catur punya tuntutan berbeda, jadi menetapkannya di sini berarti menjawab pertanyaan milik #21.
- **Delta waktu nyata, bukan interval nominal.** Galat yang menumpuk berarti jendela melenceng makin jauh pada turnamen panjang, dan melencengnya tidak terlihat sampai ada yang menghitung ulang.
- **Diagnosis yang bisa dibaca belakangan.** NULL setelah tutup berarti kejadian "sempat habis" tidak lagi tercampur dengan "ditutup manual". Membiarkannya di 0 membuat dua riwayat berbeda terbaca sama.

## Konsekuensi

- **ADR-0006 diperluas, bukan digantikan.** Kolom `tournaments.registration_closes_at` (Q54) tidak dipakai; penggantinya dua kolom di atas, ditambahkan saat implementasi.
- **ADR-0006 mendapat invarian baru yang eksplisit**: jendela 24 jam dan auto-abandon 72 jam **keduanya mulai berjalan saat turnamen dibuat**, dan 24 < 72, sehingga **auto-abandon tidak mungkin menyala selama pendaftaran masih berjalan**. Invarian ini yang membuat keputusan "satu konstanta" aman.
- **Ticket [Perilaku jam catur](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/21) mewarisi tick ini** — keberadaan dan kontraknya sudah ditetapkan; interval dan presisinya menjadi miliknya.
- **Dilengkapi oleh [ADR-0015](0015-perilaku-jam-catur.md)**: **interval tick = 1 detik**, dan penghitung bot-hidup yang ia majukan **adalah jam platform itu sendiri** — jam catur, jendela pendaftaran, dan "Ditinggalkan" semuanya mengukur terhadap angka yang sama. Penghitungnya disimpan **satu baris** di `bot_uptime` dan di-flush tiap 60 detik. Clamp `[0, 2×interval]` yang sudah ditetapkan di sini ternyata sekaligus menutup lubang tidur/hibernate PC: `time.monotonic()` di Windows adalah `QueryPerformanceCounter`, yang **tetap maju selama sleep**, sehingga jangkar monotonic mentah akan membebankan tidur ke pemain.
- **`CONTEXT.md` diperbarui**: **Pendaftaran** menyebut lamanya dan dasar jamnya; **Batas waktu pertandingan** menjadi bagian dari satu keluarga konstanta, bukan aturan tunggal.
- **Menambah satu pesan per turnamen** (pengumuman tutup) di samping pesan bracket dan pesan pairing yang sudah ada. Ketiganya pesan baru ber-mention, tidak ada DM dan tidak ada scheduled event.
- **Tombol yang dinonaktifkan menuntut pesan pendaftaran disimpan id-nya** di `tournaments` untuk diedit saat tutup — pola yang sama dengan `bracket_message_id` yang sudah ada.

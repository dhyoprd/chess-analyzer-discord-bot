# Bot dijalankan di komputer sendiri, dengan jam catur yang dijeda saat mati

## Konteks

Tiga keputusan saling tarik-menarik:

- Bot harus **online 24/7** (Q24) supaya jam catur berjalan dan game tidak menggantung.
- Hosting di **komputer sendiri** (Q29, dikonfirmasi tiga kali).
- Jam catur adalah hal yang harus dibangun sendiri seluruhnya — `python-chess` tidak menyediakannya.

Komputer pribadi akan mati: restart, mati listrik, tidur. Menjalankan bot 24/7 di sana secara harfiah tidak mungkin. Keputusan ini mencatat konsekuensi yang **diterima secara sadar**, bukan pura-pura tidak ada.

## Keputusan

Bot, backend, dan jam catur berjalan di komputer pengguna (Windows). Frontend Activity di cloud karena Discord mewajibkan URL HTTPS publik.

**Jam catur dijeda saat bot mati** dan dilanjutkan dari sisa waktu terakhir saat bot hidup lagi. Jam **tetap berjalan** saat pemain menutup Activity sementara bot masih hidup.

## Alasan

- Pengguna memilih komputer sendiri secara konsisten; keputusan ini menghormati itu.
- Jeda saat bot mati adalah pilihan yang **adil**: tidak ada pemain yang kalah karena listrik pengguna padam. Alternatifnya (waktu nyata berjalan terus) akan menghukum pemain atas kegagalan infrastruktur yang bukan salah mereka.
- Membedakan "bot mati" dari "pemain menutup Activity" penting: yang pertama kegagalan sistem, yang kedua keputusan pemain — dan yang kedua tidak boleh dijadikan celah untuk berfikir tanpa kehabisan waktu.

## Konsekuensi

- Backend **wajib** menyimpan timestamp monotonic dan sisa waktu tiap pemain, lalu menghitung ulang jeda saat start. Ini memperbesar item "bangun jam catur" yang sudah besar.
- Tidak ada jaminan bot online. `/challenge` dan turnamen bisa gagal di tengah, dan pemain akan mengalaminya.
- Turnamen dengan jadwal ronde menjadi rapuh — peserta tidak datang bisa berarti bot mati, bukan pemain kabur. Ticket alur turnamen harus memperhitungkan ini.
- Migrasi ke VPS nanti sebaiknya tetap mudah: konfigurasi lewat environment variable, supaya perpindahan tidak menuntut penulisan ulang.
- **Diamendemen oleh [ADR-0010](0010-dev-lokal-dan-deployment-windows.md)**: jalur migrasi VPS bukan lagi "orkestrasi Docker Compose" melainkan `uv sync` + unit systemd + binary Stockfish Linux. Docker dibuang karena Docker Desktop tidak bisa start tanpa sesi login dan VM WSL2 mematikan dirinya saat idle. Konfigurasi tetap lewat environment variable, jadi sifat portabelnya bertahan.
- **Diamendemen oleh [ADR-0015](0015-perilaku-jam-catur.md)**: "timestamp monotonic dan hitung ulang saat start" dilaksanakan sebagai **satu penghitung bot-hidup** (tick ADR-0013), bukan timestamp per pemain. Jangkar `time.monotonic()` mentah **ditolak** karena Microsoft mendokumentasikan bahwa `QueryPerformanceCounter` — implementasinya di Windows — **tetap maju selama sleep/hibernate**, sehingga tidur PC akan membebankan waktu ke pemain yang sedang berpikir. Penghitung di-clamp `[0, 2×interval]`, jadi lompatan apa pun terpotong 2 detik ke arah yang menguntungkan pemain. **Downtime tidak dikodekan sama sekali** — penghitungnya tidak maju, jadi ia tidak pernah masuk hitungan. Catatan: Lichess **tidak** menjeda jam saat server mati; penyimpangan ini adalah pilihan sadar, bukan kelalaian.

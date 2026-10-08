# Backend adalah pemegang state otoritatif permainan

## Konteks

Activity berjalan di browser pemain sebagai aplikasi React. Activity bisa menyimpan state papan sendiri dan mengirimkan hasil akhirnya ke backend — itu yang paling responsif dan paling sederhana. Alternatifnya, backend menyimpan state resmi dan Activity hanya mengirim niat langkah.

Ini trade-off nyata antara kelincahan UI dan integritas permainan.

## Keputusan

**Backend Python adalah satu-satunya sumber kebenaran** untuk posisi papan, riwayat langkah, dan jam catur. Activity mengirim *niat* langkah ("bidak e2 ke e4"); backend memvalidasi dengan `python-chess`, menentukan hasilnya, lalu menyiarkan state baru ke kedua pemain.

Activity tidak pernah menjadi penentu posisi yang sah.

## Alasan

- **Anti-curang.** State di klien bisa dimanipulasi oleh pemain yang paham teknis. Rating Glicko-2 dan turnamen bergantung pada hasil yang tidak bisa dipalsukan.
- **Dokumentasi Discord sendiri mewajibkannya secara praktis:** *"Do not trust data coming from the Discord client as truth."*
- **Pemulihan.** Karena state ada di server, pemain bisa menutup Activity dan melanjutkan nanti (keputusan Q35) — ini mustahil kalau state hanya ada di browser.
- **Jam catur tidak bisa dipercaya dari klien.** Waktu yang dilaporkan browser tidak dapat dijadikan dasar flag-fall.

## Konsekuensi

- Setiap langkah menempuh perjalanan bolak-balik ke server. Perlu optimistic UI di Activity supaya drag-and-drop tetap terasa mulus.
- Sinkronisasi harus lewat WebSocket (WebRTC tidak didukung Discord), dan perlu logika rekonsiliasi saat kedua pemain melangkah bersamaan.
- Backend menyimpan game yang sedang berjalan, bukan hanya yang sudah selesai — dan harus memulihkannya setelah restart.
- `python-chess` menyediakan validasi, tapi **`board.push()` tidak memeriksa legalitas**. Semua input dari Discord wajib melewati `parse_uci()`, `push_uci()`, atau `find_move()`.

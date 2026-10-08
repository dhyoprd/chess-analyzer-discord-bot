# Membangun Activity catur sendiri, bukan membaca game yang sudah ada di Discord

## Konteks

Kebutuhan awal adalah menganalisa game catur yang dimainkan di Discord. Discord punya Activity catur resmi ("Chess in the Park", app ID `832012774040141894`) dan banyak bot catur pihak ketiga. Yang wajar diasumsikan: cukup membaca game dari salah satunya, lalu analisa.

## Keputusan

Kita **membangun Activity catur sendiri** dengan Embedded App SDK, dan bot kita sendiri sebagai host permainan. Kita tidak mencoba membaca game dari Activity atau bot pihak ketiga mana pun.

## Alasan

Riset terhadap dokumentasi resmi Discord membuktikan pembacaan itu **mustahil**, bukan sekadar sulit:

- Embedded App SDK hanya berfungsi di dalam iframe Activity milik app itu sendiri. Tidak ada API untuk membaca state app lain.
- Endpoint `GET /applications/{id}/activity-instances/{instance_id}` hanya mengembalikan daftar user ID dan lokasi channel — **tidak ada** field papan, langkah, atau PGN.
- Interaction Discord hanya dikirim ke app pemiliknya. Bot lain tidak bisa mengamati klik tombol bot catur lain.
- Legacy RPC hanya punya `SET_ACTIVITY`, `SEND_ACTIVITY_JOIN_INVITE`, `CLOSE_ACTIVITY_REQUEST` — tidak ada perintah baca.
- "Chess in the Park" tidak menyediakan ekspor PGN.

Satu-satunya jalur yang mungkin adalah membaca pesan yang dirender bot catur lain memakai intent `MESSAGE_CONTENT` — yang bergantung pada persetujuan Discord, rapuh, dan hanya memberi papan hasil render, bukan riwayat langkah yang otoritatif.

## Konsekuensi

- Proyek menjadi jauh lebih besar: Activity frontend, backend, bot, dan pipeline analisa — bukan sekadar pipeline analisa.
- Kita **memiliki** seluruh state game, sehingga masalah keterbacaan data hilang total dan analisa bisa sangat akurat.
- Kita menanggung beban yang tidak dimiliki pembaca pasif: jam catur, validasi langkah, sinkronisasi WebSocket, dan OAuth.
- Belum ada Activity catur publik yang diketahui — kita mengerjakan sesuatu yang belum ada presedennya, sehingga prototype kerangka Activity menjadi langkah de-risk yang wajib.

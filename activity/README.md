# Activity — frontend React/TypeScript

Aplikasi web tertanam di dalam Discord lewat Embedded App SDK. Tempat pemain
bermain: papan drag-and-drop, Chess960, jam catur, mode lawan komputer.

**Belum ada kode.** Kerangkanya adalah ticket "Prototype: kerangka Activity +
sinkronisasi langkah" — de-risk terbesar di peta, karena riset menemukan
**belum pernah ada Activity catur publik** (0 hasil pencarian).

## Yang sudah dipastikan riset

Batasan ini membentuk seluruh desain Activity, bukan pilihan gaya:

| Batasan | Konsekuensi |
|---|---|
| Activity **wajib** HTTPS publik | Dev lokal harus lewat `cloudflared tunnel`; tidak ada dev proxy resmi |
| Discord **tidak mendukung WebRTC** | Sinkronisasi langkah harus WebSocket |
| Cookie wajib `SameSite=None Partitioned` | Di domain `{clientId}.discordsays.com` |
| URL Mapping: target **harus direktori**, **tanpa** protokol | Prefix terpanjang ditulis lebih dulu |
| Discord tidak merender SVG inline | Jalur render papan untuk PNG belum diputuskan |

## Batasan arsitektur

Activity **bukan** pemegang state otoritatif (ADR-0002). Ia mengirim *niat*
langkah; backend memvalidasi dan menyiarkan state baru. Karena setiap langkah
menempuh perjalanan bolak-balik, **optimistic UI wajib** supaya drag-and-drop
tetap terasa mulus.

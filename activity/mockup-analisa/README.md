# MOCKUP — tampilan hasil analisa

> ⚠️ **KODE BUANGAN.** Ini menjawab satu pertanyaan, lalu dibuang. Tidak ada
> backend, tidak ada penyimpanan, tidak ada penanganan error yang layak.
> Jangan diangkat ke produksi apa adanya.
>
> Ticket: [Mockup: tampilan hasil analisa](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/7)
> Peta: [Peta: Platform Catur Discord](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/1)

## Pertanyaan yang dijawab

> Bagaimana bentuk konkret output analisa — di dalam Activity dan sebagai embed
> di channel Discord?

## Cara membuka

Klik dua kali `index.html`. Tidak butuh server, tidak butuh build, tidak butuh
Node. Datanya sudah tertanam sebagai variabel global (`data/analisa-nyata.js`),
karena `fetch()` dari `file://` diblokir CORS.

Varian bisa dipilih lewat tombol di bawah, atau langsung lewat URL:

```
index.html?variant=A&surface=embed&scenario=normal
index.html?variant=B&surface=activity&scenario=long
```

| Param | Nilai |
|---|---|
| `variant` | `A` (ringkas) · `B` (papan dulu) · `C` (analis) |
| `surface` | `embed` (Discord) · `activity` (panel Activity) |
| `scenario` | `normal` · `engine` · `abandoned` · `import` · `oneply` · `long` |

Tombol ← → juga berpindah varian.

## Angkanya NYATA, bukan karangan

Semua eval, klasifikasi, dan akurasi dihasilkan **Stockfish 19 sungguhan** dengan
konfigurasi persis ADR-0009 — `go nodes 1.000.000`, `Threads=4`, `Hash=128 MB`,
MultiPV 1 — lalu dihitung dengan rumus yang sudah diverifikasi terhadap nilai
emas unit test Lichess (`backend/tools/verify_analysis_formulas.py`).

Ini bukan kemewahan. Keputusan tata letak di ticket ini bergantung pada **berapa
banyak karakter** yang dibutuhkan daftar langkah nyata; angka karangan akan
menghasilkan keputusan yang salah. Dan memang begitu — lihat temuan di bawah.

Dua game dipakai:

| Game | Ply | Akurasi (putih/hitam) | Kenapa |
|---|---|---|---|
| Anderssen–Kieseritzky, London 1851 ("Immortal Game") | 45 | 44,0% / 71,6% | Game nyata yang penuh kesalahan — beban khas daftar langkah |
| Stockfish self-play, kedua sisi lemah | 101 | 54,0% / 65,8% | Menguji kasus **game panjang (100+ langkah)** |

Game panjang **tidak bisa dipesan** — percobaan pertama berakhir skakmat dalam 39
ply, terlalu pendek untuk menguji apa pun. Generatornya karena itu memainkan
beberapa game dan memakai yang terpanjang.

Rumusnya **disalin** ke `tools/generate_data.py` supaya skrip itu berdiri sendiri.
Salinan adalah tempat bug bersembunyi, jadi `tools/crosscheck_formulas.py`
menjalankan kedua implementasi atas nilai emas yang sama dan membandingkannya —
termasuk perangkap POV klasifikasi. Kalau keduanya menyimpang, seluruh angka di
mockup salah walau terlihat wajar.

## Cara menjalankan ulang semuanya

```sh
python -I tools/run_all.py <path-ke-stockfish.exe>
```

Enam langkah: hasilkan data → cocokkan rumus dengan ADR-0009 → uji anggaran
embed → **periksa panel anggaran mockup menghitung bagian yang benar** → ubah ke
`.js` → tangkap layar. Terakhir dijalankan: **6/6 lulus**, termasuk **10/10 nilai
emas Lichess** dan **11/11 tangkapan layar**.

Langkah 4 berjalan di **Node**, bukan Python: ia menjalankan `src/mockup.js` yang
sesungguhnya dengan DOM palsu dan membaca angka yang benar-benar ditampilkan
panel. Ia ada karena dua bug "menghitung bagian yang salah" sudah lolos dari
langkah 3 — langkah 3 mengukur *salinan* logikanya, langkah 4 mengukur *kodenya*.
Keduanya kini harus melaporkan angka yang sama (1.705 pada game 137 ply).

## ✅ Keputusan (pemilik proyek, 2026-10-15)

| Pertanyaan | Keputusan |
|---|---|
| **Embed Discord** | **Varian B — "papan dulu"** |
| **Panel Activity** | **Varian B — papan + eval bar + grafik di atas, filmstrip di bawah** |
| **Daftar langkah di embed** | **Tampilkan daftar penuh** (bukan dipangkas) |
| **Blunder di embed** | **Selalu tampilkan semua**, walau 20+ |

**Catatan penting:** pilihan ini menggabungkan dua hal yang **belum pernah ada
bersama** di varian mana pun — struktur B (papan + hitungan) **dan** daftar
langkah penuh **dan** seluruh blunder. Karena itu gabungannya diukur terpisah,
bukan diasumsikan muat karena bagian-bagiannya muat sendirian:

| Game | Total | Field terbesar |
|---|---|---|
| Immortal (45 ply, 4 blunder) | 630 / 6000 (**10,5%**) | — |
| Self-play (137 ply, **41 blunder**) | 1.705 / 6000 (**28,4%**) | `field.urutan.v` 843 / 1024 (**82%**) |

Keduanya muat. Tapi perhatikan baris kedua: pada game 137 ply dengan 41 blunder,
daftar langkah penuh memakai **82% dari batas `field.value`**. Ini bukan lagi
"jauh di bawah batas" — game yang lebih panjang akan menyentuhnya. Ambangnya
sekitar **ply 170**.

**Yang perlu diingat saat implementasi:** keputusan "tampilkan daftar penuh"
berlaku sampai sekitar ply 170. Di atas itu embed **akan ditolak Discord**
dengan `Bad Request`. Implementasinya butuh penjaga pemotongan, bukan karena
keputusannya salah, tapi karena batas keras `field.value` 1024 memang ada.
Titik potong yang disarankan: **ply 170** (~87 langkah penuh).

## Tiga varian

Varian di sini berbeda **struktur**, bukan warna. **B adalah yang dipilih.**

- **A — Ringkas.** Akurasi di depan sebagai angka terbesar; daftar langkah hanya
  yang bermasalah. Embed kecil, panel Activity menaruh tabel momen kritis di atas
  dan urutan lengkap sebagai rujukan.
- **B — Papan dulu. ✅ DIPILIH.** Papan dan grafik eval jadi pusat. Embed memakai
  thumbnail papan, hitungan per pemain, seluruh blunder, dan urutan langkah penuh;
  panel Activity menaruh papan + eval bar + grafik di baris atas, filmstrip langkah
  di bawah.
- **C — Analis.** Daftar langkah jadi sumbu navigasi. Embed hanya menampilkan
  blunder + urutan yang bermasalah; panel Activity membuat daftar langkah bisa
  diklik untuk menelusuri, dengan papan dan detail langkah di samping.

## 🔴 Temuan utama: batas karakter BUKAN alasan memangkas daftar langkah

Body ticket ini menyebut batas **2000 karakter**. Itu keliru. Dari
`discord-api-docs` (`developers/resources/message.mdx`):

- **2000** adalah batas `content` pesan — teks biasa di luar embed
- Batas embed: **6000 karakter gabungan** (title + description + field.name +
  field.value + footer.text + author.name) untuk **semua** embed dalam satu pesan
- **25 field** per embed, **10 embed** per pesan
- Per-field: title 256, description 4096, **field.name 256, field.value 1024**,
  footer 2048

Terhadap batas yang benar itu, diukur dari teks yang benar-benar dirender:

| Isi | Immortal (45 ply) | Game panjang (101 ply) |
|---|---|---|
| Daftar langkah **LENGKAP** | 269 karakter | **779 karakter** |
| Varian A total | 331 / 6000 (**5,5%**) | 402 / 6000 (**6,7%**) |
| Varian C total | 298 / 6000 (5,0%) | 660 / 6000 (**11,0%**) |

**Daftar langkah lengkap untuk game 101 ply hanya 779 karakter — 13% dari
anggaran.** Bahkan daftar lengkap **muat** di dalam satu embed.

Batas yang benar-benar mengikat adalah **`field.value` = 1024 karakter**, dan itu
baru tersentuh sekitar **ply 173 (~87 langkah penuh)** pada rata-rata 5,92
karakter/ply:

| Ply | Karakter daftar | Muat di field.value 1024? |
|---|---|---|
| 100 | 540 | ✅ |
| 150 | 815 | ✅ |
| 200 | 1.091 | ❌ |
| 300 | 1.691 | ❌ |

**Konsekuensinya untuk keputusan:** memangkas daftar langkah adalah pilihan
**keterbacaan**, bukan keharusan teknis. Embed yang menampilkan daftar lengkap
untuk game normal **bisa** dibuat. Kalau daftar penuh tetap dipangkas, alasannya
harus dinyatakan sebagai "channel jadi berisik", bukan "tidak muat" — supaya
tidak ada yang membangun penjaga teknis untuk masalah yang tidak ada.

Skrip pembuktian: `tools/verify_embed_budget.py` (dijalankan dengan `python -I`).

## Item ticket yang dijawab

| # | Item | Di mana |
|---|---|---|
| 1 | Embed Discord (akurasi, daftar langkah berpenanda, ringkasan pembukaan) | Varian A/B/C, panel "Anggaran embed" mengukur tiap field |
| 2 | Panel Activity (eval bar, daftar langkah, navigasi antar langkah) | Varian A/B/C pada `surface=activity` |
| 3 | Pesan progres tanpa kena rate limit | Bagian "Kasus khusus & pesan progres" (hanya di `surface=embed`) |
| 4 | Kasus khusus (ditinggalkan, tanpa pemenang, 100+ langkah) | Tombol skenario + tabel kasus khusus |
| 5 | Manusia vs lawan komputer | Tombol skenario "Lawan komputer" & "Impor" — lencana, tanpa mention |

## Yang perlu dinilai

Sudah dijawab 2026-10-15 — lihat **Keputusan** di atas. Pertanyaan aslinya,
kalau nanti ada yang ingin ditinjau ulang:

- Embed mana yang dibuka di channel — daftar langkahnya kurang/kebanyakan?
- Panel Activity: eval bar + daftar, grafik + filmstrip, atau daftar yang jadi pusat?
- Apakah blunder harus selalu ditampilkan walau 20+?
- Pesan progres: cukup satu baris, atau perlu sisa waktu?
- Bagaimana membedakan lawan komputer — lencana saja cukup?

## Berkas

```
index.html                    mockup (satu berkas, klik dua kali)
src/mockup.js                 tiga varian × dua permukaan (B = dipilih)
src/shared.js                 pemformat angka & teks bersama
data/analisa-nyata.js         data Stockfish nyata (dihasilkan, jangan diedit tangan)
tools/run_all.py              jalankan semua pemeriksaan, satu perintah
tools/generate_data.py        jalankan Stockfish → JSON
tools/to_js.py                JSON → .js yang bisa dimuat <script>
tools/crosscheck_formulas.py  buktikan rumusnya identik dengan ADR-0009
tools/verify_embed_budget.py  uji anggaran terhadap batas resmi Discord
tools/check_budget_consistency.mjs  pastikan mockup menghitung bagian yang benar
tools/screenshot.py           tangkapan layar Chrome headless
docs/tangkapan/               11 tangkapan layar
```

## Jebakan yang sudah terverifikasi (jangan ulangi)

### Chrome headless

- **`--user-data-dir` wajib.** Tanpanya Chrome meneruskan perintah ke instans
  yang sudah berjalan, keluar dengan kode **0**, dan tidak menulis berkas apa
  pun — gagal secara senyap.
- **Semua path harus absolut.** `--screenshot` atau `--user-data-dir` dengan
  path relatif membuat Chrome **menggantung**, bukan gagal.
- **Jangan `subprocess.run(capture_output=True)`.** Di Windows Chrome
  mewariskan pipe ke proses anak yang hidup lebih lama, sehingga Python
  menunggu selamanya walau Chrome-nya sudah keluar.
- **`--virtual-time-budget`** membuat Chrome versi ini tidak menulis berkas sama
  sekali.

### Menghasilkan data

- **PGN karangan tangan rawan langkah ilegal.** Percobaan pertama memakai PGN
  Berlin Defence yang ditulis tangan dan gagal di langkah 17 (`Rxe5` ilegal).
  Pakai self-play atau PGN sumber.
- **Self-play dua engine sama kuat tidak menghasilkan kesalahan** — terukur 0
  klasifikasi dalam 104 ply, sehingga tidak menguji tata letak daftar penuh
  penanda. Kedua sisi harus dilemahkan.
- **Panjang game tidak bisa dipesan.** Percobaan pertama berakhir skakmat dalam
  39 ply. Mainkan beberapa game, pakai yang terpanjang.
- **`fetch()` dari `file://` diblokir CORS** — data harus jadi variabel global
  supaya mockup bisa dibuka dengan klik dua ganda tanpa server.

### Bug yang benar-benar terjadi di sesi ini (ditemukan oleh skrip, bukan oleh mata)

| Bug | Gejala | Ditemukan oleh |
|---|---|---|
| `eval_before` kehilangan jenisnya | Eval mate dirender `0,00` — terlihat wajar tapi salah | Pemeriksaan mata pada tangkapan layar |
| Nilai mate diperlakukan sebagai centipawn | `mate 3` jadi 3cp, delta `−0,0055` | Penjaga kewarasan di generator |
| `game_accuracy` membagi nol pada daftar kosong | `ZeroDivisionError` pada game 0/1 ply | `crosscheck_formulas.py` |
| Anggaran diukur dari HTML, bukan teks Discord | Panel menampilkan 3.977 karakter padahal ~200 | Pemeriksaan mata pada tangkapan layar |
| **Panel lupa menghitung `title` + `footer`** | Mockup 1.655 vs verifikator 1.693 | Membandingkan dua jalur pengukuran |
| Deskripsi verifikator tidak sama dengan mockup | 1.242 vs 1.316 — mengukur hal berbeda | Membandingkan dua jalur pengukuran |
| Verifikator mengabaikan penanda `**` | 1.693 vs 1.705 — Discord menghitungnya | Membandingkan dua jalur pengukuran |
| Perbandingan delta dengan `==` | Dua implementasi setara aljabar gagal cocok di bit terakhir | `crosscheck_formulas.py` |
| Harapan label klasifikasi salah tulis | 3 "GAGAL" padahal implementasinya sepakat | `crosscheck_formulas.py` |
| `!array` dianggap benar untuk array kosong | Semua skenario dilaporkan GAGAL padahal lolos | `check_budget_consistency.mjs` |

Pelajaran yang berulang: **hampir semua bug di atas terlihat wajar saat
dilihat.** Yang menemukannya adalah skrip yang membandingkan angka, bukan
membaca kode.

Empat bug terakhir punya akar yang sama: **dua jalur yang seharusnya menghitung
hal yang sama, menghitung hal yang berbeda.** Karena itu
`check_budget_consistency.mjs` sekarang menjadi langkah tetap di `run_all.py` —
selama kedua jalur tidak dipaksa melaporkan angka yang sama, mereka akan
menyimpang lagi.

## Catatan untuk ADR-0009: tangga mate hanya menutup 2 dari 4 bentuk

Penjaga kewarasan di generator awalnya menuntut **semua** langkah yang
melibatkan mate terklasifikasi, dan gagal dua kali:

- **Immortal Game ply 41** (`Nxg7+`, mate 3 → 2) — ini **mate tertunda**, dan
  ADR-0009 memang menyatakan tanpa penilaian.
- **Self-play ply 125** (`Kc2`, mate −3 → 0cp) — ini **lolos dari skakmat**,
  arah yang tidak disebut ADR-0009 sama sekali.

Ada **empat** bentuk perpindahan yang melibatkan mate, dan ADR-0009 hanya
memberi tangga untuk dua:

| Bentuk | Tangga ADR-0009 | Catatan |
|---|---|---|
| cp → mate untuk lawan | `MateCreated` | dinilai dari eval sebelumnya |
| mate untuk kita → cp | `MateLost` | dinilai dari eval sesudahnya |
| mate → mate | tanpa penilaian | disebut eksplisit sebagai "mate tertunda" |
| **mate untuk lawan → cp** | **tidak disebut** | **lolos dari skakmat** — seharusnya tanpa penilaian, tapi ADR-0009 tidak menyatakannya |
| **cp → mate untuk kita** | **tidak disebut** | **menemukan skakmat** — jelas bukan kesalahan |

Dua baris terakhir **tidak menghasilkan bug** (keduanya jatuh ke jalur
selisih win-chance dan tidak melewati ambang), tapi ketiadaannya di ADR berarti
implementor berikutnya harus menebak. Layak ditambahkan sebagai catatan saat
ADR-0009 diamendemen.

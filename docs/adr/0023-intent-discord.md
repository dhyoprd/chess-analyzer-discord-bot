# Intent Discord: satu flag, nol privileged, diperiksa literal saat start

## Konteks

Ticket [Intent Discord yang dinyalakan bot](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/27) lahir saat **Penyajian klasemen** ([#22](https://github.com/dhyoprd/chess-analyzer-discord-bot/issues/22)) dikerjakan, dengan dugaan bahwa menampilkan nickname menuntut **Server Members intent**. Riset di ticket itu membalik dugaan tersebut, dan [ADR-0016](0016-penyajian-klasemen.md) menyerahkan keputusan intent ke [ADR-0010](0010-dev-lokal-dan-deployment-windows.md) — padahal ADR-0010 tidak pernah memutuskan satu intent pun. Ia seluruhnya soal **cara menjalankan** platform: proses native, tunnel, Task Scheduler.

Yang tersisa setelah itu adalah pertanyaan yang lebih sempit dan lebih tajam: **permukaan data apa yang benar-benar dibutuhkan bot ini?** Ini keputusan arsitektur bot, bukan deployment — himpunan intent tidak berubah saat platform dipindah ke VPS, sedangkan seluruh isi ADR-0010 berubah.

Sembilan pertanyaan, tiga ronde. Riset sumber primer (`discord/discord-api-docs` @ `e3ea589`, `Rapptz/discord.py` @ tag `v2.7.1`) menutup dua pertanyaan sebelum ditanyakan: apakah lampiran `/impor` menuntut `MESSAGE_CONTENT`, dan apakah `members` membeli sesuatu tanpa `presences`.

## Keputusan

**Satu intent: `guilds`. Nol privileged intent.**

```python
intents = discord.Intents.none()
intents.guilds = True

# Literal, BUKAN diturunkan dari intents yang sama: kalau dibandingkan
# dengan objek yang sama, assert tidak bisa gagal dan penjaganya jadi hiasan.
assert intents.value == 0x1, (
    f'intent menyala {intents.value:#x}, seharusnya 0x1 (guilds saja)'
)

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
```

- **`guilds` adalah satu-satunya flag.** Ia mengisi cache guild dan channel; tanpa itu discord.py memwarning `Guilds intent seems to be disabled` (`state.py:237-238`) dan setiap lookup channel jatuh ke HTTP.
- **`members`, `presences`, `message_content` mati.** Ketiganya privileged, dan ketiganya punya nol konsumen di seluruh desain terkunci.
- **Seluruh flag lain mati**, termasuk `voice_states` dan keenam flag keluarga pesan (`guild_messages`, `dm_messages`, `guild_reactions`, `dm_reactions`, `guild_typing`, `dm_typing`).
- **Deklarasi eksplisit lewat `Intents.none()`, bukan `Intents.default()`.** `default()` menyala dengan nilai `53575421` — termasuk keenam flag keluarga pesan di atas, yang tidak pernah diaudit siapa pun.
- **Assert memakai literal `0x1`**, bukan konstanta yang diturunkan dari intent yang sama. Menyalakan intent berlebih harus **gagal saat start**, bukan lolos karena kedua sisi berubah bersama.
- **Set yang sama untuk aplikasi Discord dev dan produksi** (ADR-0010 mewajibkan keduanya). Yang berbeda hanya token, client ID, database, dan port.
- **Kelas klien: `discord.Client` + `app_commands.CommandTree`**, bukan `commands.Bot`. Bot ini nol perintah prefix.
- **Developer Portal: ketiga toggle privileged dibiarkan MATI.** Dicatat sebagai konsekuensi; tidak ada langkah deploy tambahan.

## Alasan

- **Tidak ada satu pun permukaan yang membaca data gateway di luar interaksi.** Seluruh permukaan pengguna adalah slash command, tombol komponen, dan Activity — dan `INTERACTION_CREATE` **tidak terikat intent mana pun**. Dokumentasi menyatakannya secara struktural: *"Any events not listed means it's not associated with an intent and will always be sent to your app"* (`gateway.mdx:308`), dan `INTERACTION_CREATE` tidak muncul di blok daftar intent (`gateway.mdx:312-431`, nol kemunculan).
- **Lampiran `/impor` datang lewat interaksi, bukan lewat pesan.** Ini fakta yang menutup pertanyaan terbesar ticket ini, dan ia bukan selera: tipe opsi `ATTACHMENT` (11) dideklarasikan membawa "attachment object" (`application-commands.mdx:142`), objeknya sampai di `resolved.attachments` pada payload interaksi (`receiving-and-responding.mdx:180`), dan dokumentasi menyebut `attachment` sebagai salah satu tipe opsi slash command secara eksplisit (`you-might-not-need-a-privileged-intent.mdx:124`). Jadi `/impor berkas:` **tidak menuntut `MESSAGE_CONTENT`**.
- **`members` tanpa `presences` adalah kombinasi terburuk dari kedua dunia.** Ia privileged, dan `GUILD_CREATE.members` tetap hanya berisi bot sendiri plus pengguna voice (`gateway-events.mdx:776`); discord.py tetap mencoba chunk tiap guild saat start. Membayar intent untuk cache yang sama isinya dengan yang didapat tanpa intent.
- **`query_members(user_ids=[...])` sudah terbukti tidak menuntut intent** (ADR-0016, diverifikasi ulang: `guild.py:4519-4520` hanya memeriksa `presences`, dan `query_members` tidak pernah memeriksa `members`). Nama di `/klasemen` karena itu tidak membeli satu intent pun.
- **`voice_states` membeli cache yang berubah menurut keadaan tak terlihat.** Ia mengisi `_members` hanya untuk pengguna yang sedang di voice channel. Platform ini tidak punya fitur voice, jadi hasilnya adalah nama di klasemen yang bergantung pada siapa yang kebetulan masuk voice — keluaran yang berubah tanpa ada yang bermain. `Pemain <id>` yang deterministik lebih baik.
- **Enam flag keluarga pesan adalah bawaan yang tidak pernah diaudit.** `Intents.default()` menyalakannya semua. Tidak ada `on_message` di seluruh desain, jadi keenamnya hanya menambah traffic gateway. Pola yang sama dengan penolakan `games.source` tanpa default (ADR-0012:70): jalur yang tidak dibenarkan harus gagal keras, bukan diwarisi diam-diam.
- **Literal `0x1` karena assert yang dibandingkan dengan dirinya sendiri tidak menjaga apa pun.** Bila `EXPECTED` diturunkan dari intent yang sama, suntingan yang menyalakan flag tambahan mengubah kedua sisi sekaligus dan pemeriksaannya lolos. Angka mentah memutus tautan itu.
- **`discord.Client` karena `ext.commands` tidak dipakai satu perintah pun.** Ia juga menghapus satu-satunya jalur di discord.py yang memeriksa `message_content` (`ext/commands/bot.py:228-235`) — warning yang hanya muncul pada konfigurasi prefix, dan karena itu tidak pernah relevan di sini. Memilih kelas yang tidak memiliki jalur itu lebih kuat daripada memastikan jalurnya tidak aktif.
- **Keputusan dicatat sebagai ADR baru, bukan amendemen ADR-0010.** ADR-0016 menunjuk ke sana, tapi yang diputuskan di sini adalah **permukaan data yang diterima bot** — dan ia tidak berubah saat deployment berubah. Amendemen akan menaruh keputusan permanen di dalam dokumen yang seluruh isinya bisa gugur.

## Konsekuensi

- **`CONTEXT.md` diperluas** dengan istilah **Intent**, berisi set yang dinyalakan (`guilds` saja), nol privileged, dan alasan singkatnya.
- **ADR-0016 dikoreksi arahnya.** Konsekuensinya menyebut intent "diputuskan di ticket Intent Discord", dan itu sudah selesai: tidak ada intent yang dibutuhkan klasemen, dan tidak ada yang dinyalakan untuknya.
- **[ADR-0022](0022-perintah-analisa-ulang.md) terkonfirmasi, bukan berubah.** Ia menyatakan analisa ulang menuntut nol intent baru; keputusan ini menegaskan bahwa seluruh bot memang menuntut nol intent privileged.
- **Developer Portal tidak punya langkah otomatis.** Ia tidak punya API — pola yang sama dengan URL mapping di ADR-0010. Ketiga toggle privileged dibiarkan mati, dan yang tak sengaja menyala tidak mengubah kode, hanya membuka permukaan.
- **Ambang verifikasi tidak relevan.** Sejak 10 Juni 2026 ambang review privileged intent berbasis **10.000 pengguna unik** (`getting-started-with-privileged-intent-review.mdx:28-32`), dan bot ini hidup di satu guild kecil. Dengan nol privileged intent, pertanyaan itu gugur sepenuhnya — bukan "belum tercapai", melainkan "tidak pernah ditanyakan".
- **Yang harus dibangun saat implementasi:** satu fungsi pembuat intent dengan assert literal, pemasangan `Intents` ke `discord.Client`, dan `app_commands.CommandTree` — bukan `commands.Bot`.
- **Tidak ada perubahan skema.** Keputusan ini tidak menyentuh database sama sekali.

## Verifikasi

**Yang tidak perlu diulang:** `query_members(user_ids)` tanpa intent privileged, batas 100 ID, `fetch_member` tanpa peringatan intent, `fetch_user` tanpa `nick` (ADR-0016); bot boleh membaca pesannya sendiri tanpa `MESSAGE_CONTENT` (ADR-0022).

**Terverifikasi saat ticket ini (`discord/discord-api-docs` @ `e3ea589`, `Rapptz/discord.py` @ `v2.7.1`; jangan ulangi):**

| Klaim | Bukti |
|---|---|
| **Lampiran slash command datang di payload interaksi** | `application-commands.mdx:142` — `\| ATTACHMENT \| 11 \| [attachment] object \|`; `receiving-and-responding.mdx:180` — `attachments?` di bawah `resolved` |
| Slash command menerima tipe opsi `attachment` | `you-might-not-need-a-privileged-intent.mdx:124` — *"Slash commands accept `string`, `integer`, `number`, `boolean`, `user`, `channel`, `role`, `mentionable`, and `attachment` option types"* |
| **Event yang tidak terdaftar di daftar intent selalu dikirim** | `gateway.mdx:308` — *"Any events not listed means it's not associated with an intent and will always be sent to your app"* |
| **`INTERACTION_CREATE` tidak terikat intent mana pun** | grep `INTERACTION` pada `gateway.mdx:312-431` = **0 kemunculan**; `gateway-events.mdx:420` mendaftarkannya sebagai receive-event tanpa penanda intent |
| `Intents.default()` = `53575421`, menyalakan enam flag keluarga pesan | `flags.py:833-842` — `all()` lalu mematikan `presences`, `members`, `message_content`; `flags.py:818-824` |
| `Intents.all()` = `53608447`; `Intents.none()` = `0` | `flags.py:818-831`; `DEFAULT_VALUE = 0` di `flags.py:150` |
| **Tiga intent privileged: `GUILD_PRESENCES`, `GUILD_MEMBERS`, `MESSAGE_CONTENT`** | `gateway.mdx:447-451` |
| `members` ON + `presences` OFF → `GUILD_CREATE.members` hanya bot + pengguna voice | `gateway-events.mdx:776`; op 8 sama di `:196` |
| `query_members` hanya memeriksa intent `presences`, tidak pernah `members` | `guild.py:4519-4520`; `Guild.chunk` memeriksa `members` di `:4458-4459` |
| `voice_states` mengisi `MemberCacheFlags.voice`, hanya untuk pengguna voice | `flags.py:1500-1508`, `:1540-1541` |
| `MemberCacheFlags` diturunkan otomatis dari intent, jadi `none()+guilds` tidak mungkin memicu `ValueError` | `state.py:248-253` — `from_intents` dipakai bila `member_cache_flags` tidak diberikan; `_verify_intents` hanya jalan pada flag eksplisit (`flags.py:1545-1550`) |
| discord.py **tidak** memeriksa intent terhadap Developer Portal | kegagalan muncul sebagai `PrivilegedIntentsRequired` **setelah** koneksi ditutup `4014` (`client.py:773-775`; `opcodes-and-status-codes.mdx:51`), dan `4014` adalah close code final (`gateway.py:629`) |
| Warning `message_content` hanya menyala untuk bot prefix | `ext/commands/bot.py:228-235` — syarat prefix ≠ `when_mentioned`, atau string, atau iterable berisi |
| Cache guild mati → hanya warning, bukan galat | `state.py:237-238` |
| `guilds` = `1<<0` = `0x1` | `flags.py:872` |
| Ambang review privileged intent kini **10.000 pengguna unik**, bukan 100 guild | `getting-started-with-privileged-intent-review.mdx:28-32`; `gateway.mdx:465-467`; `change-log.mdx:540` (10 Juni 2026) |
| Verifikasi app dan review privileged intent **dipisah** | `change-log.mdx:569-571` |

**Yang tidak diklaim:**

- **Tidak ada satu kalimat pun di dokumentasi yang berbunyi "intent tidak berlaku untuk interaksi".** Kesimpulan itu dibangun dari tiga bukti tidak langsung: event tak-terdaftar selalu dikirim, `INTERACTION_CREATE` absen dari blok intent, dan dokumentasi menyebut data member pada interaksi datang *"with no intent required"*.
- **Apakah `GUILDS` wajib untuk menerima `INTERACTION_CREATE`** — **tidak terverifikasi**, baik secara dokumen maupun empiris. `guilds` dinyalakan karena cache dan warning, bukan karena interaction menuntutnya.
- **Bentuk `user_ids` pada op 8 bebas dari `GUILD_MEMBERS`** tetap **inferensi**, bukan kutipan. Yang dikutip dokumentasi membatasi frasa "entire member list" ke bentuk `(query='', limit=0<=n)` (`gateway-events.mdx:201`).
- **Masa berlaku URL lampiran interaksi** — **tidak terverifikasi**. `attachment.url` dari payload interaksi punya URL bertanda tangan, dan dokumentasi tidak menyebut berapa lama ia valid. Jalur `/impor` mengunduh berkas itu **saat perintah dijalankan**, jadi tidak ada ketergantungan pada URL yang lama; bila kelak ada jalur yang menunda unduhan, fakta ini harus diverifikasi lebih dulu.
- **Batas ukuran berkas untuk opsi `ATTACHMENT`** — tidak ada angka di dokumentasi; yang ada hanya field `attachment_size_limit` tanpa nilai (`receiving-and-responding.mdx:43`). ADR-0011 memakai batas 25 MB milik Discord, bukan angka dari halaman ini.

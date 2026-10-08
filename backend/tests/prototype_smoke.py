"""PROTOTYPE — uji asap end-to-end lewat WebSocket. Bukan bagian runtime.

Menjalankan server backend dulu, lalu:
  .venv\\Scripts\\python.exe -I tests\\prototype_smoke.py http://127.0.0.1:8000

Argumen kedua opsional: base URL (default backend langsung). Untuk menguji
lewat proxy Vite, pakai http://127.0.0.1:3000 — itu jalur yang dipakai Activity
sungguhan, dan memastikan proxy WebSocket benar-benar bekerja.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.parse
import urllib.request

import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
WS_BASE = BASE.replace("http://", "ws://").replace("https://", "wss://")

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK    {label}")
    else:
        FAIL += 1
        print(f"  GAGAL {label}  {detail}")


def http_get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode())


def ws_url(instance: str, discord: str, name: str, bot: bool = False) -> str:
    q = urllib.parse.urlencode(
        {"instance": instance, "discord": discord, "name": name, "bot": "1" if bot else "0"}
    )
    return f"{WS_BASE}/api/ws?{q}"


async def recv_state(ws, timeout: float = 5.0) -> dict:
    """Terima pesan sampai satu bertipe 'state'."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") == "state":
            return msg


async def recv_until(ws, kind: str, timeout: float = 5.0) -> dict:
    """Terima pesan sampai satu bertipe `kind` — melewati state yang menyusul."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") == kind:
            return msg


async def drain_state(ws, quiet: float = 0.4) -> dict:
    """Kuras semua pesan yang tertunda, kembalikan state terakhir.

    Pemain yang bergabung memicu siaran ke SEMUA koneksi, jadi satu klien bisa
    menerima beberapa 'state' berturut-turut. Klien yang benar harus tahan
    terhadap itu — dan Activity memang hanya menimpa state-nya tiap pesan.
    """
    last: dict = {}
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=quiet)
        except asyncio.TimeoutError:
            return last
        msg = json.loads(raw)
        if msg.get("type") == "state":
            last = msg


async def main() -> None:
    print(f"== uji asap terhadap {BASE} ==")

    # Suffix unik per proses: room hidup di memori server, jadi tanpa ini
    # uji ulang akan mewarisi riwayat dari jalan sebelumnya.
    run = str(int(asyncio.get_running_loop().time() * 1000) % 100000)

    # 0. Kesehatan.
    sehat = http_get("/api/sehat")
    check("/api/sehat menjawab", sehat.get("ok") is True, str(sehat))
    check("oauth_configured terlaporkan", "oauth_configured" in sehat, str(sehat))

    instance = f"smoke-1-{run}"

    # 1. Dua pemain menyambung ke instance yang sama.
    print("== dua pemain, satu instance ==")
    async with (
        websockets.connect(ws_url(instance, "u-putih", "Putih")) as w,
        websockets.connect(ws_url(instance, "u-hitam", "Hitam")) as b,
    ):
        # `w` sudah menerima state awal SEBELUM `b` masuk, jadi ia punya satu
        # siaran tambahan yang harus dikuras. `b` baru masuk, jadi pesan
        # pertamanya sudah state terkini.
        sw = await drain_state(w)
        sb = await recv_state(b)

        check("pemain pertama dapat putih", sw["yourColor"] == "white", str(sw["yourColor"]))
        check("pemain kedua dapat hitam", sb["yourColor"] == "black", str(sb["yourColor"]))
        check("kedua melihat instance sama", sw["instanceId"] == instance == sb["instanceId"])
        check("FEN awal benar", sw["fen"].startswith("rnbqkbnr/pppppppp"), sw["fen"])
        check("giliran awal putih", sw["turn"] == "white", sw["turn"])
        check("pemain terlihat di kursi", sw["players"]["black"]["discordId"] == "u-hitam")

        # 2. Tujuan legal dari server.
        await w.send(json.dumps({"type": "legal", "from": "e2"}))
        legal = await recv_until(w, "legal")
        check("server mengirim tujuan legal", legal["type"] == "legal", str(legal))
        check("e2 punya e3/e4", set(legal["targets"]) >= {"e3", "e4"}, str(legal["targets"]))

        # 3. Langkah legal, dan sinkronisasi ke pemain kedua.
        await w.send(json.dumps({"type": "move", "from": "e2", "to": "e4"}))
        sw2 = await drain_state(w)
        sb2 = await drain_state(b)
        check("putih: langkah diterapkan", sw2["lastMove"]["san"] == "e4", str(sw2["lastMove"]))
        check("putih: giliran pindah", sw2["turn"] == "black", sw2["turn"])
        check("HITAM IKUT TER-UPDATE (sinkronisasi)", sb2["lastMove"]["san"] == "e4", str(sb2["lastMove"]))
        check("hitam melihat gilirannya", sb2["turn"] == "black", sb2["turn"])
        check("riwayat tersinkron", len(sb2["history"]) == 1, str(len(sb2["history"])))

        # 4. Putih melangkah dua kali ditolak.
        print("== penegakan giliran ==")
        await w.send(json.dumps({"type": "move", "from": "d2", "to": "d4"}))
        err = await recv_until(w, "error")
        check("giliran salah ditolak", err["type"] == "error", str(err))
        check("kode = refused", err["code"] == "refused", str(err))
        # State korektif menyusul.
        correction = await drain_state(w)
        check("state korektif dikirim", correction["turn"] == "black", correction["turn"])

        # 5. Langkah ilegal dari sisi yang benar-benar giliran.
        await b.send(json.dumps({"type": "move", "from": "e7", "to": "e4"}))
        err2 = await recv_until(b, "error")
        check("langkah ilegal ditolak", err2["type"] == "error", str(err2))
        check("kode = illegal", err2["code"] == "illegal", str(err2))
        await drain_state(b)

        # 6. Hitam melangkah benar.
        await b.send(json.dumps({"type": "move", "from": "e7", "to": "e5"}))
        sw3 = await drain_state(w)
        check("hitam melangkah, putih melihat", sw3["lastMove"]["san"] == "e5", str(sw3["lastMove"]))
        check("giliran kembali ke putih", sw3["turn"] == "white", sw3["turn"])

        # 7. Reset.
        await w.send(json.dumps({"type": "reset"}))
        sr = await drain_state(w)
        check("reset mengosongkan riwayat", sr["history"] == [], str(sr["history"]))
        check("reset mengembalikan FEN", sr["fen"].startswith("rnbqkbnr"), sr["fen"])

        # 8. Penonton tidak bisa melangkah.
        print("== penonton ==")
        async with websockets.connect(ws_url(instance, "u-tonton", "Penonton")) as spec:
            ss = await drain_state(spec)
            check("penonton yourColor = None", ss["yourColor"] is None, str(ss["yourColor"]))
            await spec.send(json.dumps({"type": "move", "from": "e2", "to": "e4"}))
            es = await recv_until(spec, "error")
            check("penonton ditolak", es["type"] == "error" and es["code"] == "spectator", str(es))

    # 9. Lawan simulasi mengisi kursi kosong dan melangkah sendiri.
    print("== lawan simulasi (uji satu akun) ==")
    async with websockets.connect(ws_url(f"smoke-bot-{run}", "u-solo", "Solo", bot=True)) as solo:
        s0 = await drain_state(solo)
        check("kursi hitam diisi bot", s0["players"]["black"]["isBot"] is True, str(s0["players"]))
        check("solo dapat putih", s0["yourColor"] == "white", str(s0["yourColor"]))

        await solo.send(json.dumps({"type": "move", "from": "e2", "to": "e4"}))

        # Langkah putih dan balasan bot bisa tiba dalam satu kurasan atau dua,
        # tergantung latensi (langsung vs lewat proxy Vite). Jadi jangan
        # menuntut melihat state ANTARA — periksa riwayat akhir saja.
        final_state: dict = {}
        deadline = asyncio.get_running_loop().time() + 6.0
        while asyncio.get_running_loop().time() < deadline:
            st = await drain_state(solo, quiet=1.5)
            if st:
                final_state = st
                if len(st["history"]) >= 2:
                    break

        history = final_state.get("history", [])
        check("langkah putih e4 ada di riwayat", any(
            m["san"] == "e4" and m["color"] == "white" for m in history
        ), str(history))
        check("BOT IKUT MELANGKAH", len(history) >= 2, str(len(history)))
        check("bot melangkah hitam", any(m["color"] == "black" for m in history), str(history))
        check("giliran kembali ke putih", final_state.get("turn") == "white",
              str(final_state.get("turn")))

    # 10. Skakmat lewat WebSocket.
    print("== skakmat lewat protokol ==")
    async with websockets.connect(ws_url(f"smoke-mate-{run}", "m1", "Mate1")) as w, \
               websockets.connect(ws_url(f"smoke-mate-{run}", "m2", "Mate2")) as b:
        await drain_state(w)
        await drain_state(b)
        script = [("e2", "e4"), ("e7", "e5"), ("f1", "c4"), ("b8", "c6"),
                  ("d1", "h5"), ("g8", "f6"), ("h5", "f7")]
        final: dict = {}
        for i, (frm, to) in enumerate(script):
            mover = w if i % 2 == 0 else b
            await mover.send(json.dumps({"type": "move", "from": frm, "to": to}))
            # Kuras kedua klien setiap langkah; state terakhir dari langkah
            # terakhir adalah yang kita periksa.
            final = await drain_state(w)
            await drain_state(b)
        check("status = checkmate", final["status"] == "checkmate", final["status"])
        check("pemenang = white", final["winner"] == "white", str(final["winner"]))
        check("alasan = skakmat", final["endReason"] == "skakmat", str(final["endReason"]))

    # 11. Introspeksi room.
    rooms = http_get("/api/rooms")
    ids = {r["instanceId"] for r in rooms["rooms"]}
    expected = {instance, f"smoke-bot-{run}", f"smoke-mate-{run}"}
    check("room terlihat di /api/rooms", expected <= ids, str(expected - ids))

    print()
    print(f"lulus {PASS}, gagal {FAIL}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())

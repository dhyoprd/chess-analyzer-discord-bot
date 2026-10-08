"""PROTOTYPE — render papan di browser sungguhan lewat DevTools Protocol.

`--dump-dom` tidak menunggu WebSocket, jadi ia memotret papan sebelum state
tiba. Skrip ini menyalakan Chrome dengan remote debugging, menavigasi, menunggu
sampai papan benar-benar tergambar, lalu memeriksa DOM-nya.

Jalankan dari activity/prototype:
  python check_render.py <path-ke-python-venv-backend> <path-chrome>

Bukan bagian runtime.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

PY = sys.argv[1]
CHROME = sys.argv[2]
PORT = 9222
URL = "http://127.0.0.1:3000/?debug=1&room=render-uji&name=Putih"

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


async def cdp_call(ws, msg_id: int, method: str, params: dict | None = None) -> dict:
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        raw = json.loads(await ws.recv())
        if raw.get("id") == msg_id:
            return raw


async def evaluate(ws, msg_id: int, expr: str) -> object:
    resp = await cdp_call(ws, msg_id, "Runtime.evaluate", {
        "expression": expr,
        "returnByValue": True,
        "awaitPromise": True,
    })
    return resp.get("result", {}).get("result", {}).get("value")


async def main() -> None:
    print("== render papan di browser ==")

    profile = tempfile.mkdtemp(prefix="proto-chrome-")
    chrome = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Tunggu endpoint debugging hidup.
        target = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                    targets = json.loads(r.read().decode())
                pages = [t for t in targets if t.get("type") == "page"]
                if pages:
                    target = pages[0]
                    break
            except Exception:
                time.sleep(0.5)

        if target is None:
            check("chrome remote debugging hidup", False, "tidak ada target page")
            return
        check("chrome remote debugging hidup", True)

        async with websockets.connect(
            target["webSocketDebuggerUrl"], max_size=20_000_000
        ) as ws:
            await cdp_call(ws, 1, "Page.enable")
            await cdp_call(ws, 2, "Runtime.enable")
            await cdp_call(ws, 3, "Page.navigate", {"url": URL})

            # Tunggu sampai papan tergambar (state tiba lewat WebSocket).
            squares = 0
            for i in range(60):
                await asyncio.sleep(0.5)
                squares = await evaluate(
                    ws, 100 + i,
                    "document.querySelectorAll('[data-square]').length",
                ) or 0
                if squares >= 64:
                    break

            check("64 kotak papan tergambar", squares == 64, f"dapat {squares}")

            pieces = await evaluate(
                ws, 300, "document.querySelectorAll('[data-piece]:not([data-piece=\"\"])').length"
            )
            check("32 bidak tergambar", pieces == 32, f"dapat {pieces}")

            # FEN awal harus tergambar di papan.
            fen_ok = await evaluate(
                ws, 301,
                "!!document.querySelector('[data-square=\"e1\"] [data-type=\"k\"]')"
                " && !!document.querySelector('[data-square=\"d8\"] [data-type=\"q\"]')",
            )
            check("bidak di kotak yang benar (Ke1, qd8)", fen_ok is True, str(fen_ok))

            # Identitas debug terbaca.
            who = await evaluate(ws, 302, "document.body.innerText.includes('Putih')")
            check("nama pemain tampil", who is True, str(who))

            mode = await evaluate(ws, 303, "document.body.innerText.includes('MODE DEBUG')")
            check("mode debug terdeteksi", mode is True, str(mode))

            turn = await evaluate(ws, 304, "document.body.innerText.includes('GILIRANMU')")
            check("giliran putih ditandai", turn is True, str(turn))

            # Papan bisa diklik: pilih e2, tunggu sorotan tujuan legal.
            await evaluate(
                ws, 305,
                "document.querySelector('[data-square=\"e2\"]').dispatchEvent("
                "new MouseEvent('click', {bubbles:true}))",
            )
            targets = 0
            for i in range(20):
                await asyncio.sleep(0.3)
                targets = await evaluate(
                    ws, 400 + i, "document.querySelectorAll('.square.target').length"
                ) or 0
                if targets > 0:
                    break
            check("klik bidak menyorot tujuan legal", targets >= 2, f"dapat {targets}")

            # Jalur klik: klik e4 -> langkah terkirim -> riwayat bertambah.
            await evaluate(
                ws, 500,
                "document.querySelector('[data-square=\"e4\"]').dispatchEvent("
                "new MouseEvent('click', {bubbles:true}))",
            )
            san = ""
            for i in range(24):
                await asyncio.sleep(0.4)
                san = await evaluate(
                    ws, 600 + i,
                    "document.querySelector('.history .san')?.textContent ?? ''",
                ) or ""
                if san:
                    break
            check("langkah terkirim lewat klik (e4)", san == "e4", f"san={san!r}")

            # Server harus melihat papan berubah, bukan hanya UI.
            fen_after = await evaluate(
                ws, 700, "document.querySelector('[data-square=\"e4\"] [data-type=\"p\"]') ? 'ya' : 'tidak'"
            )
            check("papan menampilkan bidak di e4 setelah langkah", fen_after == "ya", str(fen_after))

            glitch = await evaluate(
                ws, 701, "document.body.innerText.includes('Ditolak server')"
            )
            check("tidak ada penolakan server untuk langkah legal", glitch is False, str(glitch))

    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except Exception:
            chrome.kill()

    print()
    print(f"lulus {PASS}, gagal {FAIL}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())

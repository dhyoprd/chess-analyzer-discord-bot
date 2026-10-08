"""PROTOTYPE — ambil tangkapan layar Activity. Bukan bagian runtime.

  python shot.py <path-chrome> <keluaran.png> [query]
"""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = sys.argv[1]
OUT = sys.argv[2]
QUERY = sys.argv[3] if len(sys.argv) > 3 else "?debug=1&room=shot1&name=Putih"
PORT = 9223
URL = f"http://127.0.0.1:3000/{QUERY}"


async def cdp(ws, mid: int, method: str, params: dict | None = None) -> dict:
    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        raw = json.loads(await ws.recv())
        if raw.get("id") == mid:
            return raw


async def evaluate(ws, mid: int, expr: str) -> object:
    r = await cdp(ws, mid, "Runtime.evaluate", {
        "expression": expr, "returnByValue": True, "awaitPromise": True,
    })
    return r.get("result", {}).get("result", {}).get("value")


async def main() -> None:
    profile = tempfile.mkdtemp(prefix="proto-shot-")
    chrome = subprocess.Popen(
        [
            CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--window-size=1280,900",
            f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        target = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                    pages = [t for t in json.loads(r.read().decode()) if t.get("type") == "page"]
                if pages:
                    target = pages[0]
                    break
            except Exception:
                time.sleep(0.5)
        if target is None:
            raise SystemExit("tidak ada target chrome")

        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
            await cdp(ws, 1, "Page.enable")
            await cdp(ws, 2, "Runtime.enable")
            await cdp(ws, 3, "Emulation.setDeviceMetricsOverride", {
                "width": 1280, "height": 900, "deviceScaleFactor": 2, "mobile": False,
            })
            await cdp(ws, 4, "Page.navigate", {"url": URL})

            # Tunggu papan tergambar, lalu mainkan beberapa langkah agar
            # tangkapan layar menunjukkan sesuatu yang berarti.
            for i in range(60):
                await asyncio.sleep(0.5)
                n = await evaluate(ws, 100 + i, "document.querySelectorAll('[data-square]').length") or 0
                if n >= 64:
                    break

            for i, sq in enumerate(["e2", "e4", "e7", "e5", "g1", "f3", "b8", "c6"]):
                await evaluate(ws, 200 + i,
                    f"document.querySelector('[data-square=\"{sq}\"]')?.dispatchEvent("
                    "new MouseEvent('click', {bubbles:true}))")
                await asyncio.sleep(0.55)

            await asyncio.sleep(1.2)
            shot = await cdp(ws, 900, "Page.captureScreenshot", {"format": "png"})
            data = shot.get("result", {}).get("data", "")
            if not data:
                raise SystemExit("tangkapan layar kosong")
            with open(OUT, "wb") as fh:
                fh.write(base64.b64decode(data))
            print(f"tersimpan: {OUT}")
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except Exception:
            chrome.kill()


if __name__ == "__main__":
    asyncio.run(main())

"""Verifikasi cloudflared: tunnel HTTPS publik benar-benar bisa dibuat.

Ticket: "Setup environment & fondasi repo" (#5), item 5.

Activity Discord **wajib** HTTPS publik, dan tidak ada dev proxy resmi — jadi
`cloudflared tunnel` adalah satu-satunya jalur pengembangan lokal. Kalau ini
tidak jalan, tidak ada cara menguji Activity sama sekali.

Skrip ini:
1. Menyalakan server HTTP lokal di port acak
2. Membuat quick tunnel ke port itu
3. Menunggu URL publik muncul
4. **Mengambil URL publik itu** dan memastikan isinya sampai
5. Mematikan keduanya

Dua jebakan yang sudah ditemukan dan ditangani di sini:

- **stdout cloudflared harus dikuras.** Pipa stdout punya buffer terbatas.
  Kalau berhenti membacanya, cloudflared memblokir saat menulis log dan
  tunnel-nya berhenti melayani (gejala: HTTP 530). Karena itu ada thread
  penguras terpisah.
- **DNS perlu waktu.** Hostname quick tunnel baru bisa butuh ~60-90 detik
  sebelum resolver mana pun mengenalnya. Tunnel sudah "siap" di sisi
  cloudflared jauh sebelum hostname-nya bisa di-resolve. Jendela tunggu
  di sini 180 detik, dan kegagalan resolve dilaporkan sebagai "menunggu
  propagasi", bukan kegagalan.

Dijalankan dengan `python -I`.
"""

from __future__ import annotations

import http.server
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLOUDFLARED_CANDIDATES = [
    Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
    Path(r"C:\Program Files\cloudflared\cloudflared.exe"),
]

TOKEN = "tunnel-verifikasi-ok"
PROPAGATION_WINDOW = 180  # detik


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - API http.server
        body = TOKEN.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # senyapkan log akses
        pass


def find_cloudflared() -> Path:
    for candidate in CLOUDFLARED_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "cloudflared tidak ditemukan di lokasi yang diketahui: "
        + ", ".join(str(c) for c in CLOUDFLARED_CANDIDATES)
    )


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    binary = find_cloudflared()
    print(f"cloudflared : {binary}")

    version = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, timeout=30
    )
    print(f"versi       : {version.stdout.strip() or version.stderr.strip()}")

    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"server lokal: http://127.0.0.1:{port}")

    # Pastikan server lokal benar-benar melayani sebelum menyalahkan tunnel.
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
        assert r.read().decode() == TOKEN
    print("server lokal: OK")

    proc = subprocess.Popen(
        [str(binary), "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    url_holder: list[str] = []

    def drain() -> None:
        """Kuras stdout terus-menerus — kalau tidak, cloudflared memblokir."""
        assert proc.stdout is not None
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not url_holder:
                url_holder.append(m.group(0))

    threading.Thread(target=drain, daemon=True).start()

    deadline = time.time() + 90
    while time.time() < deadline and not url_holder:
        time.sleep(0.5)

    if not url_holder:
        proc.kill()
        print("\nGAGAL: URL tunnel tidak muncul dalam 90 detik")
        return 1

    url = url_holder[0]
    host = url.removeprefix("https://")
    dibuat = time.time()
    print(f"URL publik  : {url}")
    print(f"menunggu propagasi DNS (maks {PROPAGATION_WINDOW}s)...\n")

    try:
        last_error = ""
        while time.time() - dibuat < PROPAGATION_WINDOW:
            elapsed = int(time.time() - dibuat)
            try:
                with urllib.request.urlopen(f"{url}/", timeout=15) as r:
                    body = r.read().decode()
                if body != TOKEN:
                    last_error = f"isi tidak cocok: {body!r}"
                else:
                    print(f"[{elapsed:>3}s] OK — isi cocok")
                    print(f"\nSELESAI — tunnel HTTPS publik berfungsi")
                    print(f"           {url}")
                    print(f"           siap setelah ~{elapsed} detik propagasi DNS")
                    return 0
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                label = (
                    "menunggu propagasi DNS"
                    if "getaddrinfo" in last_error
                    else "menunggu edge Cloudflare"
                )
                print(f"[{elapsed:>3}s] {label} ({last_error})")
            time.sleep(10)

        print(f"\nGAGAL: URL dibuat tapi tidak bisa diambil dalam {PROPAGATION_WINDOW}s")
        print(f"       kesalahan terakhir: {last_error}")
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        server.shutdown()
        print("dibersihkan: tunnel & server lokal dimatikan")


if __name__ == "__main__":
    raise SystemExit(main())

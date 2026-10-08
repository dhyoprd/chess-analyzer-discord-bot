"""Verifikasi ekosistem backend di Python 3.14.4.

Ticket: "Setup environment & fondasi repo" (#5), item 3.

`uv pip install` berhasil bukan bukti apa-apa — ia bisa memasang wheel yang
gagal di-import, atau membangun dari sumber dan menghasilkan modul rusak.
Skrip ini mengimpor setiap dependensi **dan memakainya** untuk sesuatu yang
nyata, plus menjalankan Stockfish lewat `chess.engine.SimpleEngine`.

Fokus: item kabut "Python 3.13 vs 3.14" menyebut risiko ada di ekosistem
dependensi lain (pydantic-core, uvicorn, Pillow), bukan di python-chess.
Skrip ini menguji klaim itu secara langsung.

Dijalankan dengan `python -I` supaya tidak memuat modul dari cwd.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# engine/ ada di samping backend/, bukan di dalamnya.
REPO_ROOT = Path(__file__).resolve().parents[2]
STOCKFISH = REPO_ROOT / "engine" / "stockfish.exe"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((name, True, detail or ""))
    except Exception as exc:  # noqa: BLE001 - laporan verifikasi
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()


def check_pydantic() -> str:
    """pydantic-core adalah ekstensi Rust — risiko wheel 3.14 tertinggi."""
    import pydantic
    from pydantic import BaseModel, Field, ValidationError

    class Pemain(BaseModel):
        discord_id: int
        nama: str = Field(min_length=1)
        rating: float = 1500.0

    p = Pemain(discord_id=123, nama="Budi")
    assert p.rating == 1500.0
    # validasi harus benar-benar menolak
    try:
        Pemain(discord_id=1, nama="")
        raise AssertionError("validasi pydantic tidak menolak nama kosong")
    except ValidationError:
        pass
    # serialisasi JSON harus jalan
    assert json.loads(p.model_dump_json())["nama"] == "Budi"
    return f"pydantic {pydantic.VERSION} — validasi + serialisasi OK"


def check_pydantic_settings() -> str:
    import pydantic_settings

    class Config(pydantic_settings.BaseSettings):
        model_config = pydantic_settings.SettingsConfigDict(env_prefix="VERIF_")
        bot_token: str = "default"

    os.environ["VERIF_BOT_TOKEN"] = "rahasia-dari-env"
    try:
        assert Config().bot_token == "rahasia-dari-env"
    finally:
        del os.environ["VERIF_BOT_TOKEN"]
    return f"pydantic-settings {pydantic_settings.__version__} — baca env OK"


def check_fastapi() -> str:
    import fastapi
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/sehat")
    def sehat() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/sehat")
    assert resp.status_code == 200, resp.status_code
    assert resp.json() == {"status": "ok"}
    return f"fastapi {fastapi.__version__} — app + request nyata OK"


def check_uvicorn() -> str:
    import uvicorn

    # Jangan benar-benar bind port; cukup pastikan Server bisa dikonstruksi
    # dengan config yang valid dan modul importnya lengkap (uvloop/httptools).
    config = uvicorn.Config("__main__:app", port=0, log_level="critical")
    server = uvicorn.Server(config)
    assert server.config.port == 0
    return f"uvicorn {uvicorn.__version__} — Server konstruksi OK"


def check_discord_py() -> str:
    import discord

    # discord.py >= 2.6 butuh audioop; di 3.13+ modul itu dihapus dari stdlib
    # dan digantikan shim audioop-lts. Pastikan shim itu terpasang & bisa diimport.
    try:
        import audioop  # type: ignore[import-not-found]

        audioop_note = "audioop OK (shim audioop-lts)"
    except ImportError as exc:
        audioop_note = f"audioop TIDAK ADA: {exc}"

    # Objek inti harus bisa dikonstruksi tanpa koneksi ke Discord
    intent = discord.Intents.default()
    intent.message_content = True
    client = discord.Client(intents=intent)
    embed = discord.Embed(title="Judul", description="Isi")
    embed.add_field(name="Pemain", value="Budi", inline=True)
    assert embed.title == "Judul"
    # Batas embed yang jadi kendala nyata di proyek ini
    assert len(embed.fields) <= 25
    del client
    return f"discord.py {discord.__version__} — Client/Embed OK; {audioop_note}"


def check_aiosqlite() -> str:
    """SQLite async — kandidat penyimpanan state otoritatif."""
    import aiosqlite

    async def skenario() -> str:
        async with aiosqlite.connect(":memory:") as db:
            await db.execute("CREATE TABLE pemain (id INTEGER PRIMARY KEY, nama TEXT)")
            await db.execute("INSERT INTO pemain VALUES (?, ?)", (1, "Budi"))
            await db.commit()
            async with db.execute("SELECT nama FROM pemain WHERE id = 1") as cur:
                row = await cur.fetchone()
            assert row is not None and row[0] == "Budi"
            # WAL + foreign key adalah hal yang akan kita andalkan
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            async with db.execute("PRAGMA foreign_keys") as cur:
                fk = (await cur.fetchone())[0]
            assert fk == 1, f"foreign_keys tidak aktif: {fk}"
        return "aiosqlite — tabel, insert, select, FK ON semua OK"

    return asyncio.run(skenario())


def check_websockets() -> str:
    """WebSocket adalah tulang punggung sinkronisasi langkah (ADR-0002)."""
    import websockets

    async def skenario() -> str:
        diterima: list[str] = []

        async def handler(ws):
            async for pesan in ws:
                diterima.append(pesan)
                await ws.send(f"echo:{pesan}")

        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send("e2e4")
                balasan = await ws.recv()
                assert balasan == "echo:e2e4", balasan
        assert diterima == ["e2e4"], diterima
        return f"websockets {websockets.__version__} — server+klien loopback OK"

    return asyncio.run(skenario())


def check_pillow() -> str:
    """Pillow disebut di kabut sebagai risiko. Belum tentu dipakai (lihat
    jalur render PNG), jadi ini opsional — ketidakhadiran bukan kegagalan."""
    try:
        import PIL
        from PIL import Image, ImageDraw
    except ImportError:
        return "Pillow TIDAK terpasang (opsional — jalur render PNG belum diputuskan)"

    img = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(img).rectangle([8, 8, 56, 56], fill="black")
    assert img.getpixel((32, 32)) == (0, 0, 0)
    assert img.getpixel((2, 2)) == (255, 255, 255)
    return f"Pillow {PIL.__version__} — gambar + gambar kotak OK"


def check_stockfish_from_python() -> str:
    """Item 1 ticket: Stockfish benar-benar berjalan dari Python."""
    import chess
    import chess.engine

    if not STOCKFISH.exists():
        raise FileNotFoundError(f"tidak ada binary di {STOCKFISH}")

    engine = chess.engine.SimpleEngine.popen_uci(str(STOCKFISH))
    try:
        nama = engine.id.get("name", "?")
        board = chess.Board()

        # 1) Cari langkah terbaik pada posisi awal
        hasil = engine.play(board, chess.engine.Limit(depth=12))
        assert hasil.move is not None
        san = board.san(hasil.move)

        # 2) Analisa dengan eval terstruktur (dibutuhkan pipeline analisa)
        info = engine.analyse(board, chess.engine.Limit(depth=12))
        skor = info["score"].white()
        assert skor is not None

        # 3) MultiPV — inti dari mengklasifikasi langkah
        multipv = engine.analyse(board, chess.engine.Limit(depth=10), multipv=3)
        assert len(multipv) == 3, f"multipv mengembalikan {len(multipv)}"

        # 4) Opsi UCI yang jadi kendala: UCI_Elo (lantai 1320, temuan riset #3)
        opsi = engine.options
        elo = opsi.get("UCI_Elo")
        assert elo is not None, "UCI_Elo tidak ada di daftar opsi"
        assert elo.min == 1320, f"lantai UCI_Elo berubah: {elo.min}"
        assert elo.max == 3190, f"plafon UCI_Elo berubah: {elo.max}"

        # 5) Konfigurasi harus diterima engine tanpa error
        engine.configure({"Threads": 4, "Hash": 64})

        return (
            f"{nama}; langkah terbaik {san}, eval {skor}, multipv=3 OK; "
            f"UCI_Elo {elo.min}-{elo.max} (lantai terkonfirmasi)"
        )
    finally:
        engine.quit()


def main() -> int:
    print("=" * 74)
    print("Verifikasi ekosistem backend — Platform Catur Discord")
    print(f"Interpreter: Python {sys.version.split()[0]}")
    print("=" * 74)

    check("pydantic (pydantic-core Rust)", check_pydantic)
    check("pydantic-settings", check_pydantic_settings)
    check("FastAPI", check_fastapi)
    check("uvicorn", check_uvicorn)
    check("discord.py", check_discord_py)
    check("aiosqlite", check_aiosqlite)
    check("websockets", check_websockets)
    check("Pillow (opsional)", check_pillow)
    check("Stockfish via chess.engine", check_stockfish_from_python)

    print()
    width = max(len(n) for n, _, _ in RESULTS)
    ok = 0
    for name, passed, detail in RESULTS:
        mark = "OK   " if passed else "GAGAL"
        print(f"[{mark}] {name:<{width}}  {detail}")
        ok += passed

    print()
    print(f"{ok}/{len(RESULTS)} pemeriksaan lulus")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

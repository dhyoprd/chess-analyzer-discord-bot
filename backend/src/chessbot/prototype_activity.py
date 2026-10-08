"""PROTOTYPE — kerangka Activity + sinkronisasi langkah.

BUKAN kode produksi. Tidak ada penyimpanan, tidak ada jam catur, tidak ada
analisa, tidak ada penanganan error yang layak. Tujuannya satu: menjawab
apakah drag-and-drop + sinkronisasi dua pemain benar-benar bisa di dalam
iframe Discord. Lihat activity/PROTOTYPE.md.

Yang dibuktikan di sini:
  1. Backend otoritatif (ADR-0002) — Activity mengirim NIAT langkah ("e2 ke e4"),
     backend yang memvalidasi dengan python-chess dan menentukan hasilnya.
  2. Satu room per `instance_id` Discord, disiarkan lewat WebSocket.
  3. `find_move()` memvalidasi legalitas; `board.push()` tidak.

Jalankan:  uvicorn chessbot.prototype_activity:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

import chess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prototype")

app = FastAPI(title="PROTOTYPE — kerangka Activity")

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")


# ─────────────────────────────────────────────────────────────────────────────
# State — di memori saja. Prototype tidak punya database.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Seat:
    """Satu kursi warna. `ws is None` berarti kursi kosong."""

    color: chess.Color
    discord_id: Optional[str] = None
    username: Optional[str] = None
    ws: Optional[WebSocket] = None
    # Lawan simulasi yang digerakkan server (untuk pengujian satu akun).
    is_bot: bool = False


@dataclass
class Room:
    """Satu instance Activity. Kunci: `instance_id` dari Discord."""

    instance_id: str
    board: chess.Board = field(default_factory=chess.Board)
    history: list[dict[str, Any]] = field(default_factory=list)
    status: str = "playing"  # playing | checkmate | stalemate | draw
    winner: Optional[str] = None  # "white" | "black" | None
    end_reason: Optional[str] = None
    white: Seat = field(default_factory=lambda: Seat(chess.WHITE))
    black: Seat = field(default_factory=lambda: Seat(chess.BLACK))
    spectators: list[WebSocket] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ── kursi ───────────────────────────────────────────────────────────────

    def seat_for(self, color: chess.Color) -> Seat:
        return self.white if color == chess.WHITE else self.black

    def color_of(self, ws: WebSocket) -> Optional[chess.Color]:
        for seat in (self.white, self.black):
            if seat.ws is ws:
                return seat.color
        return None

    def color_name(self, color: Optional[chess.Color]) -> Optional[str]:
        if color is None:
            return None
        return "white" if color == chess.WHITE else "black"

    def opponent_color(self, color: chess.Color) -> chess.Color:
        return not color

    # ── langkah ─────────────────────────────────────────────────────────────

    def apply_move(self, color: chess.Color, frm: str, to: str, promotion: Optional[str]) -> dict[str, Any]:
        """Validasi dan terapkan langkah. Melempar ValueError kalau ilegal.

        Ini inti ADR-0002: `board.push()` TIDAK memvalidasi legalitas.
        `board.find_move()` memvalidasi dan melempar IllegalMoveError.
        """
        if self.status != "playing":
            raise ValueError("game sudah berakhir")

        if self.board.turn != color:
            raise ValueError(
                f"bukan giliranmu — giliran {self.color_name(self.board.turn)}"
            )

        try:
            from_sq = chess.parse_square(frm)
            to_sq = chess.parse_square(to)
        except ValueError as exc:
            raise ValueError(f"kotak tidak dikenal: {frm} -> {to}") from exc

        promo = None
        if promotion:
            promo = {
                "q": chess.QUEEN,
                "r": chess.ROOK,
                "b": chess.BISHOP,
                "n": chess.KNIGHT,
            }.get(promotion.lower())
            if promo is None:
                raise ValueError(f"promosi tidak dikenal: {promotion}")

        # Melempar chess.IllegalMoveError kalau tidak ada langkah legal yang cocok.
        move = self.board.find_move(from_sq, to_sq, promo)

        san = self.board.san(move)
        self.board.push(move)

        entry = {
            "ply": len(self.history) + 1,
            "color": self.color_name(color),
            "from": frm,
            "to": to,
            "uci": move.uci(),
            "san": san,
            "fen": self.board.fen(),
            "promotion": promotion if promo else None,
            "captured": None,
            "check": self.board.is_check(),
        }
        self.history.append(entry)

        self._settle_outcome()
        return entry

    def _settle_outcome(self) -> None:
        if self.board.is_checkmate():
            # Sisi yang gilirannya sekarang adalah yang kalah.
            loser = self.board.turn
            winner_color = self.opponent_color(loser)
            self.status = "checkmate"
            self.winner = self.color_name(winner_color)
            self.end_reason = "skakmat"
        elif self.board.is_stalemate():
            self.status = "stalemate"
            self.end_reason = "remis — buntu"
        elif self.board.is_insufficient_material():
            self.status = "draw"
            self.end_reason = "remis — materi tidak cukup"
        elif self.board.is_seventyfive_moves():
            self.status = "draw"
            self.end_reason = "remis — 75 langkah"
        elif self.board.is_fivefold_repetition():
            self.status = "draw"
            self.end_reason = "remis — pengulangan lima kali"

    def legal_targets(self, frm: str) -> list[str]:
        """Kotak tujuan legal dari satu kotak — dipakai Activity untuk sorotan."""
        try:
            from_sq = chess.parse_square(frm)
        except ValueError:
            return []
        return sorted(
            chess.square_name(m.to_square)
            for m in self.board.legal_moves
            if m.from_square == from_sq
        )

    # ── serialisasi ─────────────────────────────────────────────────────────

    def payload_for(self, ws: Optional[WebSocket]) -> dict[str, Any]:
        color = self.color_of(ws) if ws is not None else None
        return {
            "type": "state",
            "instanceId": self.instance_id,
            "fen": self.board.fen(),
            "turn": self.color_name(self.board.turn),
            "check": self.board.is_check(),
            "status": self.status,
            "winner": self.winner,
            "endReason": self.end_reason,
            "history": self.history,
            "lastMove": self.history[-1] if self.history else None,
            "yourColor": self.color_name(color),
            "players": {
                "white": self._seat_payload(self.white),
                "black": self._seat_payload(self.black),
            },
        }

    def _seat_payload(self, seat: Seat) -> dict[str, Any]:
        return {
            "discordId": seat.discord_id,
            "username": seat.username,
            "connected": seat.ws is not None,
            "isBot": seat.is_bot,
        }


ROOMS: dict[str, Room] = {}


def get_room(instance_id: str) -> Room:
    room = ROOMS.get(instance_id)
    if room is None:
        room = Room(instance_id=instance_id)
        ROOMS[instance_id] = room
        log.info("room baru: %s", instance_id)
    return room


# ─────────────────────────────────────────────────────────────────────────────
# Siaran
# ─────────────────────────────────────────────────────────────────────────────


async def broadcast(room: Room) -> None:
    """Kirim state penuh ke tiap koneksi, dipersonalisasi dengan warnanya."""
    targets: list[WebSocket] = list(room.spectators)
    for seat in (room.white, room.black):
        if seat.ws is not None:
            targets.append(seat.ws)

    dead: list[WebSocket] = []
    for ws in targets:
        try:
            await ws.send_json(room.payload_for(ws))
        except Exception:  # koneksi mati — bersihkan, jangan jatuhkan room
            dead.append(ws)

    for ws in dead:
        detach(room, ws)


def detach(room: Room, ws: WebSocket) -> None:
    if ws in room.spectators:
        room.spectators.remove(ws)
    for seat in (room.white, room.black):
        if seat.ws is ws:
            seat.ws = None


async def send_error(ws: WebSocket, message: str, code: str = "illegal") -> None:
    try:
        await ws.send_json({"type": "error", "code": code, "message": message})
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Lawan simulasi — supaya satu akun bisa menguji alur giliran
# ─────────────────────────────────────────────────────────────────────────────


async def bot_maybe_move(room: Room) -> None:
    """Kalau lawan adalah bot dan gilirannya, mainkan langkah acak legal."""
    seat = room.seat_for(room.board.turn)
    if not seat.is_bot or room.status != "playing":
        return

    await asyncio.sleep(0.7)  # biar terasa seperti pemain, bukan mesin
    async with room.lock:
        if room.status != "playing":
            return
        if not room.seat_for(room.board.turn).is_bot:
            return
        moves = list(room.board.legal_moves)
        if not moves:
            return
        move = random.choice(moves)
        entry = {
            "ply": len(room.history) + 1,
            "color": room.color_name(room.board.turn),
            "from": chess.square_name(move.from_square),
            "to": chess.square_name(move.to_square),
            "uci": move.uci(),
            "san": room.board.san(move),
            "promotion": None,
            "captured": None,
        }
        room.board.push(move)
        entry["fen"] = room.board.fen()
        entry["check"] = room.board.is_check()
        room.history.append(entry)
        room._settle_outcome()
    await broadcast(room)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/sehat")
async def sehat() -> dict[str, Any]:
    return {
        "ok": True,
        "prototype": True,
        "rooms": len(ROOMS),
        "oauth_configured": bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET),
    }


@app.get("/api/rooms")
async def rooms() -> dict[str, Any]:
    """Introspeksi untuk pengujian — lihat room apa saja yang hidup."""
    return {
        "rooms": [
            {
                "instanceId": r.instance_id,
                "fen": r.board.fen(),
                "turn": r.color_name(r.board.turn),
                "status": r.status,
                "ply": len(r.history),
                "white": r.white.discord_id,
                "black": r.black.discord_id or ("BOT" if r.black.is_bot else None),
                "spectators": len(r.spectators),
            }
            for r in ROOMS.values()
        ]
    }


def _exchange_code(code: str) -> dict[str, Any]:
    """POST sinkron ke Discord — dijalankan di thread supaya tidak memblokir loop.

    Prototype memakai stdlib supaya tidak menambah dependensi yang belum ada
    di uv.lock. Produksi akan memakai klien HTTP async yang sesungguhnya.
    """
    payload = urllib.parse.urlencode(
        {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
        }
    ).encode()
    req = urllib.request.Request(
        "https://discord.com/api/oauth2/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": resp.status, "body": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read().decode()[:300]}
    except Exception as exc:
        return {"status": 0, "body": repr(exc)}


@app.post("/api/token")
async def token(body: dict[str, Any]) -> JSONResponse:
    """Tukar OAuth `code` dari Activity menjadi `access_token`.

    Ini langkah 5 alur auth resmi. `client_secret` HANYA boleh ada di sini,
    tidak pernah di Activity.
    """
    code = body.get("code")
    if not code:
        return JSONResponse({"error": "code wajib"}, status_code=400)
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        return JSONResponse(
            {"error": "DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET belum diisi di .env"},
            status_code=500,
        )

    result = await asyncio.to_thread(_exchange_code, code)

    if result["status"] != 200:
        log.warning("tukar token gagal: %s %s", result["status"], result["body"])
        return JSONResponse(
            {"error": "tukar token gagal", "status": result["status"], "detail": result["body"]},
            status_code=502,
        )

    data = result["body"]
    return JSONResponse({"access_token": data.get("access_token")})


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — inti sinkronisasi
# ─────────────────────────────────────────────────────────────────────────────


@app.websocket("/api/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    """Satu koneksi per pemain. Room dipilih lewat query `instance`.

    Query: instance (wajib), discord (id), name (tampilan), bot (1 = lawan simulasi)
    """
    await websocket.accept()

    q = websocket.query_params
    instance_id = q.get("instance") or "TANPA-INSTANCE"
    discord_id = q.get("discord") or "anonim"
    username = q.get("name") or discord_id
    want_bot = q.get("bot") == "1"

    room = get_room(instance_id)

    # Kursi: pemain yang sama yang menyambung ulang mendapat warnanya kembali.
    color: Optional[chess.Color] = None
    for seat in (room.white, room.black):
        if seat.discord_id == discord_id and seat.ws is None:
            seat.ws = websocket
            color = seat.color
            break

    if color is None:
        for seat in (room.white, room.black):
            if seat.discord_id is None:
                seat.discord_id = discord_id
                seat.username = username
                seat.ws = websocket
                color = seat.color
                break

    if color is None:
        room.spectators.append(websocket)
        log.info("%s masuk sebagai penonton di %s", username, instance_id)
    else:
        log.info("%s duduk sebagai %s di %s", username, room.color_name(color), instance_id)

    # Lawan simulasi menempati kursi yang masih kosong.
    if want_bot:
        for seat in (room.white, room.black):
            if seat.discord_id is None:
                seat.discord_id = f"bot-{instance_id[:8]}"
                seat.username = "Lawan simulasi"
                seat.is_bot = True
                break

    await broadcast(room)

    try:
        while True:
            raw = await websocket.receive_json()
            kind = raw.get("type")

            if kind == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if kind == "reset":
                async with room.lock:
                    room.board = chess.Board()
                    room.history = []
                    room.status = "playing"
                    room.winner = None
                    room.end_reason = None
                await broadcast(room)
                continue

            if kind == "legal":
                frm = raw.get("from", "")
                await websocket.send_json(
                    {"type": "legal", "from": frm, "targets": room.legal_targets(frm)}
                )
                continue

            if kind == "move":
                my_color = room.color_of(websocket)
                if my_color is None:
                    await send_error(websocket, "kamu penonton, tidak bisa melangkah", "spectator")
                    continue

                frm = raw.get("from", "")
                to = raw.get("to", "")
                try:
                    async with room.lock:
                        entry = room.apply_move(my_color, frm, to, raw.get("promotion"))
                except chess.IllegalMoveError:
                    await send_error(websocket, f"langkah ilegal: {frm}->{to}", "illegal")
                    # Kirim state supaya Activity membatalkan UI optimistisnya.
                    await websocket.send_json(room.payload_for(websocket))
                    continue
                except ValueError as exc:
                    await send_error(websocket, str(exc), "refused")
                    await websocket.send_json(room.payload_for(websocket))
                    continue

                log.info("langkah %s: %s", instance_id, entry["san"])
                await broadcast(room)
                asyncio.create_task(bot_maybe_move(room))
                continue

            await send_error(websocket, f"pesan tidak dikenal: {kind}", "unknown")

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # prototype — jangan sampai menjatuhkan proses
        log.warning("ws error di %s: %r", instance_id, exc)
    finally:
        detach(room, websocket)
        log.info("%s terputus dari %s", username, instance_id)
        await broadcast(room)

# Backend otoritatif — Platform Catur Discord
#
# ⚠️ BELUM DIPAKAI. Layanan di docker-compose.yml punya profil `container` dan
# tidak ikut `docker compose up` secara default. Cara menjalankan backend relatif
# terhadap Stockfish adalah keputusan ticket "Dev lokal & deployment di Windows"
# (#13) — lihat catatan kendala di docker-compose.yml.
#
# Saat #13 memutuskan backend di-container dengan binary Stockfish Linux
# (opsi b), unduh binary Linux ke engine/ dengan nama `stockfish` dan berkas ini
# langsung bekerja.

FROM python:3.14-slim

# `uv` untuk resolusi dependensi dari uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Salin manifes dulu supaya lapisan dependensi ter-cache.
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# --frozen: gagal kalau uv.lock tidak sinkron dengan pyproject.toml.
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Direktori state otoritatif — di-mount sebagai volume di compose.
RUN mkdir -p /app/data

# Jangan jalan sebagai root.
RUN useradd --create-home --uid 1000 chessbot && chown -R chessbot:chessbot /app
USER chessbot

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "chessbot.app:app", "--host", "0.0.0.0", "--port", "8000"]

// PROTOTYPE — kerangka Activity. Bukan kode produksi.
//
// Membuktikan tiga hal, sesuai ticket #6:
//   1. Activity terbuka dan menggambar papan dari FEN
//   2. Langkah bisa diklik/di-drag, dikirim ke backend, dan papan ter-update
//   3. Dua klien di instance yang sama saling melihat langkah (WebSocket)
//
// Yang SENGAJA tidak ada: jam catur, Chess960, lawan komputer sungguhan,
// turnamen, analisa, tema visual, tata letak mobile.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Board } from './Board';
import { IS_DISCORD, resolveIdentity, ACTIVITY_URL } from './auth';
import { useGame } from './useGame';
import type { Identity } from './types';

export function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [botEnabled, setBotEnabled] = useState(
    () => ACTIVITY_URL.searchParams.get('bot') === '1',
  );

  // Identitas: OAuth di dalam Discord, buatan sendiri di browser biasa.
  useEffect(() => {
    let alive = true;
    resolveIdentity()
      .then((id) => {
        if (alive) setIdentity(id);
      })
      .catch((err: unknown) => {
        if (alive) setAuthError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      alive = false;
    };
  }, []);

  const game = useGame(identity, botEnabled);

  const orientation = useMemo(() => {
    if (game.state?.yourColor) return game.state.yourColor;
    return 'white' as const;
  }, [game.state?.yourColor]);

  const onMove = useCallback(
    (from: string, to: string) => {
      game.sendMove(from, to);
    },
    [game],
  );

  if (authError) {
    return (
      <div className="shell">
        <div className="panel error-panel">
          <h1>Gagal menyiapkan identitas</h1>
          <pre>{authError}</pre>
          <p className="hint">
            Di browser biasa, tambahkan <code>?debug=1</code> ke URL. Di dalam Discord,
            isi <code>VITE_DISCORD_CLIENT_ID</code> di <code>activity/prototype/.env</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!identity) {
    return (
      <div className="shell">
        <div className="panel">
          <p className="hint">menyiapkan…</p>
        </div>
      </div>
    );
  }

  const state = game.state;
  const turn = state?.turn ?? 'white';
  const yourColor = state?.yourColor ?? null;
  const isMyTurn = yourColor !== null && turn === yourColor && state?.status === 'playing';

  return (
    <div className="shell">
      <header className="topbar">
        <div className="who">
          {identity.avatarUrl && <img src={identity.avatarUrl} alt="" />}
          <div>
            <strong>{identity.username}</strong>
            <span className="muted">
              {yourColor ? `kamu ${yourColor === 'white' ? 'putih' : 'hitam'}` : 'penonton'}
            </span>
          </div>
        </div>
        <div className="badges">
          <span className={`badge ${identity.debug ? 'warn' : 'ok'}`}>
            {identity.debug ? 'MODE DEBUG (browser)' : 'DI DALAM DISCORD'}
          </span>
          <span className={`badge ${game.status === 'open' ? 'ok' : 'bad'}`}>
            WS: {game.status}
          </span>
        </div>
      </header>

      <main className="layout">
        <section className="board-col">
          {game.displayFen ? (
            <Board
              fen={game.displayFen}
              orientation={orientation}
              turn={turn}
              yourColor={yourColor}
              legalTargets={game.legalTargets}
              lastMove={state?.lastMove ?? null}
              interactive={isMyTurn && game.status === 'open'}
              onRequestLegal={game.requestLegal}
              onMove={onMove}
              pending={game.pending !== null}
            />
          ) : (
            <div className="board-placeholder">menunggu state dari server…</div>
          )}

          <div className="turn-line">
            {state?.status === 'playing' && (
              <span className={isMyTurn ? 'turn-mine' : 'turn-theirs'}>
                {isMyTurn ? 'GILIRANMU' : `giliran ${turn === 'white' ? 'putih' : 'hitam'}`}
              </span>
            )}
            {state && state.status !== 'playing' && (
              <span className="turn-end">
                {state.status === 'checkmate'
                  ? `SKAKMAT — ${state.winner === 'white' ? 'putih' : 'hitam'} menang`
                  : `SELESAI — ${state.endReason ?? state.status}`}
              </span>
            )}
            {state?.check && state.status === 'playing' && <span className="check">SKAK!</span>}
          </div>
        </section>

        <aside className="side-col">
          <div className="panel">
            <h2>Pemain</h2>
            <SeatRow
              label="Putih"
              seat={state?.players.white}
              active={turn === 'white' && state?.status === 'playing'}
              you={yourColor === 'white'}
            />
            <SeatRow
              label="Hitam"
              seat={state?.players.black}
              active={turn === 'black' && state?.status === 'playing'}
              you={yourColor === 'black'}
            />
          </div>

          <div className="panel">
            <h2>Riwayat</h2>
            {state && state.history.length > 0 ? (
              <ol className="history">
                {state.history.map((m) => (
                  <li key={m.ply} className={m.color === yourColor ? 'mine' : ''}>
                    <span className="ply">{m.ply}.</span>
                    <span className="san">{m.san}</span>
                    <span className="uci muted">{m.uci}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="hint">belum ada langkah</p>
            )}
          </div>

          {game.lastError && (
            <div className="panel error-panel">
              <h2>Ditolak server</h2>
              <p>{game.lastError.message}</p>
              <p className="hint">kode: {game.lastError.code}</p>
            </div>
          )}

          <div className="panel">
            <h2>Kendali prototype</h2>
            <button className="btn" onClick={game.reset}>
              Reset papan
            </button>
            <label className="toggle">
              <input
                type="checkbox"
                checked={botEnabled}
                onChange={(e) => setBotEnabled(e.target.checked)}
              />
              Lawan simulasi (main sendiri)
            </label>
            <p className="hint">
              Ubah lawan simulasi akan menyambung ulang WebSocket supaya kursi
              hitam diisi bot.
            </p>
          </div>

          <div className="panel">
            <h2>Info</h2>
            <dl className="kv">
              <dt>instance</dt>
              <dd>{identity.instanceId}</dd>
              <dt>discord id</dt>
              <dd>{identity.discordId}</dd>
              <dt>konteks</dt>
              <dd>{IS_DISCORD ? 'iframe Discord' : 'browser biasa'}</dd>
              <dt>ply</dt>
              <dd>{state?.history.length ?? 0}</dd>
            </dl>
          </div>

          {identity.debug && (
            <div className="panel debug-panel">
              <h2>Cara menguji dua pemain</h2>
              <p className="hint">
                Buka jendela kedua dengan instance yang <strong>sama</strong>:
              </p>
              <code className="url">
                {window.location.origin}
                {window.location.pathname}?debug=1&amp;room={identity.instanceId}&amp;name=Hitam
              </code>
              <p className="hint">
                Atau nyalakan <strong>lawan simulasi</strong> di atas untuk bermain
                sendiri — kursi hitam diisi bot.
              </p>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

function SeatRow({
  label,
  seat,
  active,
  you,
}: {
  label: string;
  seat?: { username: string | null; connected: boolean; isBot: boolean };
  active: boolean;
  you: boolean;
}) {
  return (
    <div className={`seat ${active ? 'active' : ''}`}>
      <span className="seat-label">{label}</span>
      <span className="seat-name">
        {seat?.connected || seat?.isBot ? (seat.username ?? '—') : 'kosong'}
        {seat?.isBot && <em className="bot-tag">BOT</em>}
        {you && <em className="you-tag">kamu</em>}
      </span>
    </div>
  );
}

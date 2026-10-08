// PROTOTYPE — koneksi WebSocket + state. Bukan kode produksi.
//
// Backend otoritatif (ADR-0002): Activity mengirim NIAT langkah, lalu menunggu
// state baru dari server. Untuk menjaga drag-and-drop tetap mulus, langkah
// digambar lebih dulu secara optimistis dan DIBATALKAN kalau server menolak.
//
// Semua state hidup di memori. Tidak ada persistensi — prototype tidak butuh.

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiUrl, wsUrl } from './auth';
import type { ErrorReply, GameState, Identity, ServerMessage } from './types';

export type ConnectionStatus = 'connecting' | 'open' | 'closed';

/** Langkah optimistis yang sedang menunggu konfirmasi server. */
export interface PendingMove {
  from: string;
  to: string;
}

export interface UseGame {
  status: ConnectionStatus;
  state: GameState | null;
  /** FEN yang ditampilkan — sudah termasuk langkah optimistis. */
  displayFen: string | null;
  pending: PendingMove | null;
  lastError: ErrorReply | null;
  /** Langkah terakhir yang diterima server, untuk disorot. */
  legalTargets: string[];
  requestLegal: (from: string) => void;
  sendMove: (from: string, to: string, promotion?: string) => void;
  reset: () => void;
  /** Pengaturan lawan simulasi — hanya berguna saat menguji sendirian. */
  botEnabled: boolean;
  setBotEnabled: (on: boolean) => void;
}

/**
 * Terapkan satu langkah ke FEN untuk penggambaran optimistis.
 *
 * Ini BUKAN validasi — hanya memindahkan bidak supaya UI tidak terasa lag.
 * Kalau langkahnya ilegal, server menolak dan state asli menggantikannya.
 * Karena itu hasilnya boleh salah; yang penting cepat.
 */
export function applyOptimistic(fen: string, from: string, to: string, promotion?: string): string {
  const parts = fen.split(' ');
  const [placement, turn, castling, ep, halfmove, fullmove] = parts;
  const rows = placement.split('/');

  const fileOf = (sq: string) => 'abcdefgh'.indexOf(sq[0]);
  const rankOf = (sq: string) => Number(sq[1]);

  const grid: (string | null)[][] = rows.map((row) => {
    const cells: (string | null)[] = [];
    for (const ch of row) {
      if (/\d/.test(ch)) {
        for (let i = 0; i < Number(ch); i += 1) cells.push(null);
      } else {
        cells.push(ch);
      }
    }
    return cells;
  });

  // Baris 0 = peringkat 8.
  const cellOf = (sq: string) => ({ r: 8 - rankOf(sq), c: fileOf(sq) });
  const src = cellOf(from);
  const dst = cellOf(to);

  const piece = grid[src.r]?.[src.c] ?? null;
  if (piece === null) return fen;

  grid[src.r][src.c] = null;

  // Promosi: ganti bidak yang mendarat dengan ratu sesuai warna.
  let landed = piece;
  if (promotion && (to[1] === '8' || to[1] === '1')) {
    landed = piece === piece.toUpperCase() ? 'Q' : 'q';
  }
  grid[dst.r][dst.c] = landed;

  const newPlacement = grid
    .map((row) => {
      let out = '';
      let empty = 0;
      for (const cell of row) {
        if (cell === null) {
          empty += 1;
        } else {
          if (empty) {
            out += String(empty);
            empty = 0;
          }
          out += cell;
        }
      }
      if (empty) out += String(empty);
      return out;
    })
    .join('/');

  // Giliran, penghitung langkah, dan hak castling sengaja dibiarkan usang:
  // server akan segera mengirim FEN yang benar. Menebaknya di sini hanya
  // menambah kode yang tidak menjawab pertanyaan prototype ini.
  const nextTurn = turn === 'w' ? 'b' : 'w';
  const nextFull = nextTurn === 'w' ? String(Number(fullmove) + 1) : fullmove;

  return [newPlacement, nextTurn, castling, ep, halfmove, nextFull].join(' ');
}

export function useGame(identity: Identity | null, botEnabled: boolean): UseGame {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [state, setState] = useState<GameState | null>(null);
  const [pending, setPending] = useState<PendingMove | null>(null);
  const [lastError, setLastError] = useState<ErrorReply | null>(null);
  const [legalTargets, setLegalTargets] = useState<string[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const closedByUs = useRef(false);

  const connect = useCallback(() => {
    if (!identity) return;

    setStatus('connecting');
    const params: Record<string, string> = {
      instance: identity.instanceId,
      discord: identity.discordId,
      name: identity.username,
    };
    if (botEnabled) params.bot = '1';

    const ws = new WebSocket(wsUrl(params));
    wsRef.current = ws;

    ws.onopen = () => setStatus('open');

    ws.onmessage = (ev) => {
      let msg: ServerMessage;
      try {
        msg = JSON.parse(ev.data as string) as ServerMessage;
      } catch {
        return;
      }

      if (msg.type === 'state') {
        setState(msg);
        // State dari server selalu menang atas dugaan optimistis.
        setPending(null);
        setLegalTargets([]);
        return;
      }

      if (msg.type === 'legal') {
        setLegalTargets(msg.targets);
        return;
      }

      if (msg.type === 'error') {
        setLastError(msg);
        // Batal-kan langkah optimistis; state asli menyusul dari server.
        setPending(null);
        return;
      }
    };

    ws.onclose = () => {
      setStatus('closed');
      if (closedByUs.current) return;
      // Prototype: sambung ulang tanpa backoff. Produksi butuh backoff.
      reconnectRef.current = window.setTimeout(connect, 1500);
    };

    ws.onerror = () => {
      // onclose akan menyusul dan menangani penyambungan ulang.
    };
  }, [identity, botEnabled]);

  useEffect(() => {
    closedByUs.current = false;
    connect();
    return () => {
      closedByUs.current = true;
      if (reconnectRef.current !== null) window.clearTimeout(reconnectRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const requestLegal = useCallback((from: string) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'legal', from }));
    }
  }, []);

  const sendMove = useCallback(
    (from: string, to: string, promotion?: string) => {
      const ws = wsRef.current;
      if (ws?.readyState !== WebSocket.OPEN) return;
      setPending({ from, to });
      setLegalTargets([]);
      ws.send(JSON.stringify({ type: 'move', from, to, promotion }));
    },
    [],
  );

  const reset = useCallback(() => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'reset' }));
      setLastError(null);
      setPending(null);
    }
  }, []);

  const displayFen =
    state && pending
      ? applyOptimistic(state.fen, pending.from, pending.to)
      : (state?.fen ?? null);

  return {
    status,
    state,
    displayFen,
    pending,
    lastError,
    legalTargets,
    requestLegal,
    sendMove,
    reset,
    botEnabled,
    setBotEnabled: () => undefined,
  };
}

/** Introspeksi room dari server — dipakai panel debug. */
export async function fetchRooms(): Promise<
  { instanceId: string; fen: string; turn: string; status: string; ply: number }[]
> {
  const resp = await fetch(apiUrl('/rooms'));
  if (!resp.ok) return [];
  const data = (await resp.json()) as { rooms: never[] };
  return data.rooms;
}

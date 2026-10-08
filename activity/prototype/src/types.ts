// PROTOTYPE — tipe bersama. Bukan kode produksi.

export type Color = 'white' | 'black';

export interface SeatPayload {
  discordId: string | null;
  username: string | null;
  connected: boolean;
  isBot: boolean;
}

export interface MoveEntry {
  ply: number;
  color: Color;
  from: string;
  to: string;
  uci: string;
  san: string;
  fen: string;
  promotion: string | null;
  captured: string | null;
  check?: boolean;
}

export interface GameState {
  type: 'state';
  instanceId: string;
  fen: string;
  turn: Color;
  check: boolean;
  status: 'playing' | 'checkmate' | 'stalemate' | 'draw';
  winner: Color | null;
  endReason: string | null;
  history: MoveEntry[];
  lastMove: MoveEntry | null;
  yourColor: Color | null;
  players: { white: SeatPayload; black: SeatPayload };
}

export interface LegalReply {
  type: 'legal';
  from: string;
  targets: string[];
}

export interface ErrorReply {
  type: 'error';
  code: string;
  message: string;
}

export type ServerMessage = GameState | LegalReply | ErrorReply | { type: 'pong' };

/** Identitas pemain — dari Discord kalau di dalam Activity, dari debug kalau di browser. */
export interface Identity {
  discordId: string;
  username: string;
  /** true = dijalankan di browser biasa, bukan di dalam iframe Discord. */
  debug: boolean;
  /** instance_id dari Discord; di debug dipakai ID ruang buatan. */
  instanceId: string;
  avatarUrl: string | null;
}

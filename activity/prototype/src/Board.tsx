// PROTOTYPE — papan drag-and-drop. Bukan kode produksi.
//
// Ini bagian yang paling perlu dinilai manusia: apakah drag-and-drop benar-benar
// nyaman di dalam iframe Discord? Karena itu papan mendukung DUA cara melangkah
// sekaligus, supaya bisa dibandingkan langsung:
//
//   1. DRAG  — tekan bidak, seret ke kotak tujuan, lepas.
//   2. KLIK  — klik bidak (tujuan legal tersorot), lalu klik kotak tujuan.
//
// HTML5 drag-and-drop tidak bekerja baik di sentuh, jadi jalur klik wajib ada
// sebagai cadangan. Kalau ternyata drag terasa buruk di dalam iframe, jawaban
// ticket ini mungkin "pakai klik saja" — dan itu keputusan yang sah.

import { useMemo, useRef, useState } from 'react';
import { isDarkSquare, parseFen, squaresInRenderOrder } from './fen';
import type { Color } from './types';

const GLYPHS: Record<string, string> = {
  K: '♔', Q: '♕', R: '♖', B: '♗', N: '♘', P: '♙',
  k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟',
};

export interface BoardProps {
  fen: string;
  /** Warna yang dilihat pemain ini — papan diputar supaya miliknya di bawah. */
  orientation: Color;
  /** Warna yang gilirannya sekarang, menurut server. */
  turn: Color;
  /** Warna pemain ini; null kalau penonton. */
  yourColor: Color | null;
  /** Kotak tujuan legal untuk bidak yang sedang dipilih. */
  legalTargets: string[];
  /** Langkah terakhir dari server, untuk disorot. */
  lastMove: { from: string; to: string } | null;
  /** Apakah bidak boleh diangkat sekarang (giliranmu & game jalan). */
  interactive: boolean;
  /** Minta daftar tujuan legal dari server saat bidak dipilih. */
  onRequestLegal: (from: string) => void;
  /** Kirim niat langkah ke server. */
  onMove: (from: string, to: string) => void;
  /** true = ada langkah menunggu konfirmasi server. */
  pending: boolean;
}

export function Board({
  fen,
  orientation,
  turn,
  yourColor,
  legalTargets,
  lastMove,
  interactive,
  onRequestLegal,
  onMove,
  pending,
}: BoardProps) {
  const pieces = useMemo(() => parseFen(fen), [fen]);
  const [selected, setSelected] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const draggingFrom = useRef<string | null>(null);

  const order = useMemo(() => {
    const base = squaresInRenderOrder();
    return orientation === 'white' ? base : [...base].reverse();
  }, [orientation]);

  const isMyPiece = (square: string): boolean => {
    const piece = pieces[square];
    if (!piece) return false;
    return yourColor !== null && piece.color === yourColor && turn === yourColor && interactive;
  };

  /** Klik pertama memilih; klik kedua di kotak legal melangkah. */
  const handleClick = (square: string) => {
    if (selected) {
      if (square === selected) {
        setSelected(null);
        return;
      }
      if (legalTargets.includes(square)) {
        onMove(selected, square);
        setSelected(null);
        return;
      }
    }
    if (isMyPiece(square)) {
      setSelected(square);
      onRequestLegal(square);
      return;
    }
    setSelected(null);
  };

  const handleDragStart = (square: string) => (ev: React.DragEvent) => {
    if (!isMyPiece(square)) {
      ev.preventDefault();
      return;
    }
    draggingFrom.current = square;
    setSelected(square);
    onRequestLegal(square);
    ev.dataTransfer.effectAllowed = 'move';
    // Firefox menolak drag tanpa data; nilai apa pun cukup.
    ev.dataTransfer.setData('text/plain', square);
  };

  const handleDragOver = (square: string) => (ev: React.DragEvent) => {
    if (draggingFrom.current === null) return;
    ev.preventDefault();
    ev.dataTransfer.dropEffect = 'move';
    setDragOver(square);
  };

  const handleDrop = (square: string) => (ev: React.DragEvent) => {
    ev.preventDefault();
    const from = draggingFrom.current;
    draggingFrom.current = null;
    setDragOver(null);
    if (!from || from === square) {
      setSelected(null);
      return;
    }
    onMove(from, square);
    setSelected(null);
  };

  const handleDragEnd = () => {
    draggingFrom.current = null;
    setDragOver(null);
  };

  const flipped = orientation === 'black';

  return (
    <div className={`board-wrap ${flipped ? 'flipped' : ''}`}>
      <div className="board" role="grid" aria-label="Papan catur">
        {order.map((square) => {
          const piece = pieces[square];
          const dark = isDarkSquare(square);
          const isSelected = selected === square;
          const isTarget = legalTargets.includes(square);
          const isCapture = isTarget && Boolean(piece);
          const isLast = lastMove !== null && (lastMove.from === square || lastMove.to === square);
          const isHover = dragOver === square;

          const classes = [
            'square',
            dark ? 'dark' : 'light',
            isSelected ? 'selected' : '',
            isTarget ? 'target' : '',
            isCapture ? 'capture' : '',
            isLast ? 'last' : '',
            isHover ? 'hover' : '',
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <div
              key={square}
              className={classes}
              role="gridcell"
              data-square={square}
              data-piece={piece?.code ?? ''}
              onClick={() => handleClick(square)}
              onDragStart={handleDragStart(square)}
              onDragOver={handleDragOver(square)}
              onDragLeave={() => setDragOver((cur) => (cur === square ? null : cur))}
              onDrop={handleDrop(square)}
              onDragEnd={handleDragEnd}
              draggable={isMyPiece(square)}
            >
              {piece && (
                <span className={`glyph ${piece.color}`} data-type={piece.type}>
                  {GLYPHS[piece.code] ?? '?'}
                </span>
              )}
              {isTarget && !isCapture && <span className="dot" />}
            </div>
          );
        })}
      </div>
      {pending && <div className="board-pending">menunggu server…</div>}
    </div>
  );
}

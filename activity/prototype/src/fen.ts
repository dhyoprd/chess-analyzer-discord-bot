// PROTOTYPE — parsing FEN seadanya. Bukan kode produksi.
//
// Activity TIDAK menjadi state otoritatif (ADR-0002). Ini hanya untuk menggambar
// papan dari FEN yang dikirim backend. Tidak ada validasi langkah di sini —
// validasi adalah tugas backend, dan Activity sengaja tidak menebaknya.

import type { Color } from './types';

export interface Piece {
  /** 'P' bidak putih, 'p' bidak hitam, dst. */
  code: string;
  color: Color;
  type: string;
}

/** Peta kotak -> bidak. Kotak tanpa entri berarti kosong. */
export type BoardMap = Record<string, Piece>;

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

/**
 * Uraikan FEN menjadi peta kotak.
 *
 * Hanya bagian penempatan bidak yang dipakai. En-passant, hak castling, dan
 * penghitung langkah sengaja diabaikan: Activity tidak memakainya untuk apa pun,
 * dan menebaknya di sini justru bertentangan dengan ADR-0002.
 */
export function parseFen(fen: string): BoardMap {
  const map: BoardMap = {};
  const placement = fen.split(' ')[0];
  const rows = placement.split('/');

  // FEN menulis peringkat 8 lebih dulu; papan digambar dari atas ke bawah.
  rows.forEach((row, rowIndex) => {
    const rank = 8 - rowIndex;
    let fileIndex = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        fileIndex += Number(ch);
        continue;
      }
      const square = `${FILES[fileIndex]}${rank}`;
      map[square] = {
        code: ch,
        color: ch === ch.toUpperCase() ? 'white' : 'black',
        type: ch.toLowerCase(),
      };
      fileIndex += 1;
    }
  });

  return map;
}

/** Kotak-kotak dalam urutan gambar: a8..h8, a7..h7, ... a1..h1. */
export function squaresInRenderOrder(): string[] {
  const out: string[] = [];
  for (let rank = 8; rank >= 1; rank -= 1) {
    for (const file of FILES) {
      out.push(`${file}${rank}`);
    }
  }
  return out;
}

/** Warna kotak papan — a1 gelap. */
export function isDarkSquare(square: string): boolean {
  const file = FILES.indexOf(square[0]);
  const rank = Number(square[1]);
  return (file + rank) % 2 === 0;
}

/** Giliran dari FEN — dipakai sebagai cadangan kalau state belum tiba. */
export function turnFromFen(fen: string): Color {
  return fen.split(' ')[1] === 'b' ? 'black' : 'white';
}

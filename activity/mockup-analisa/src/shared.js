/* PROTOTYPE — kode buangan (ticket #7). Bukan produksi.

   Pemuat data + pemformat bersama. Semua varian memakai ini supaya perbedaan
   antar varian benar-benar soal TATA LETAK, bukan soal angka. */

const state = { games: [], index: 0, scenario: 'normal' };

/* ── Format angka (ADR-0009) ──────────────────────────────────────────────
   Koma desimal, akurasi 1 desimal, eval 2 desimal dalam pion, skakmat "#3". */

export const fmtEval = (kind, value) => {
  if (kind === 'mate') {
    return value > 0 ? `#${value}` : `#-${Math.abs(value)}`;
  }
  const pawns = value / 100;
  const s = Math.abs(pawns).toFixed(2).replace('.', ',');
  return `${pawns > 0 ? '+' : pawns < 0 ? '−' : ''}${s}`;
};

export const fmtAcc = (v) => `${v.toFixed(1).replace('.', ',')}%`;

export const fmtMoveNo = (n) => `${n}.`;

/* Klasifikasi → label Indonesia + warna. */
export const CLASS_LABEL = {
  inaccuracy: 'Ketidaktelitian',
  mistake: 'Kesalahan',
  blunder: 'Blunder',
};
export const CLASS_SHORT = {
  inaccuracy: '?!',
  mistake: '?',
  blunder: '??',
};
export const CLASS_COLOR = {
  inaccuracy: '#fbbf24',
  mistake: '#fb923c',
  blunder: '#f87171',
};

/* ── Skenario kasus khusus (item 4 ticket) ───────────────────────────────── */

export function applyScenario(games, scenario) {
  if (!games.length) return [];
  const base = JSON.parse(JSON.stringify(games));
  const g = base[0];

  if (scenario === 'abandoned') {
    g.result = '*';
    g.label = 'Kasus: game ditinggalkan (tanpa pemenang)';
    g.white = 'Budi';
    g.black = 'Sari';
    g.abandoned = true;
    return [g];
  }
  if (scenario === 'engine') {
    g.result = '1-0';
    g.label = 'Kasus: melawan komputer';
    g.white = 'Budi';
    g.black = 'Stockfish (1320)';
    g.engine = true;
    return [g];
  }
  if (scenario === 'import') {
    g.label = 'Kasus: game impor dari Lichess';
    g.imported = true;
    g.white = 'MagnusCarlsen';
    g.black = 'HikaruNakamura';
    g.result = '1-0';
    return [g];
  }
  if (scenario === 'oneply') {
    g.label = 'Kasus: game tanpa akurasi (1 ply)';
    g.accuracy = null;
    g.counts = { white: { inaccuracy: 0, mistake: 0, blunder: 0 },
                 black: { inaccuracy: 0, mistake: 0, blunder: 0 } };
    g.moves = g.moves.slice(0, 1);
    g.plies = 1;
    return [g];
  }
  return [base[0]];
}

/* ── Emisi teks untuk embed Discord (item 1 ticket) ───────────────────────
   Yang diukur adalah KARAKTER TERPAKAI, karena batas Discord dihitung dari
   title + description + field.name + field.value + footer + author. */

const MOVE_SYMBOL = { inaccuracy: '?!', mistake: '?', blunder: '??' };

/* Daftar langkah dengan penanda, gaya notasi catur.
   `only` menyaring jenis klasifikasi yang ditampilkan; null = semua. */
export function moveListText(game, { only = null, maxMoves = Infinity } = {}) {
  const out = [];
  let i = 0;
  while (i < game.moves.length && out.length < maxMoves) {
    const w = game.moves[i];
    const b = game.moves[i + 1];
    const num = w.move_no;
    const render = (m) => {
      if (!m) return '';
      const mark = m.classification && (!only || only.includes(m.classification))
        ? MOVE_SYMBOL[m.classification] : '';
      return `${m.san}${mark}`;
    };
    const wl = render(w);
    const bl = render(b);
    if (wl || bl) out.push(`${num}.${wl}${bl ? ' ' + bl : ''}`);
    i += 2;
  }
  return out.join(' ');
}

/* Ringkasan klasifikasi sebagai teks satu baris. */
export function countSummary(game, color) {
  const c = game.counts[color];
  const parts = [];
  if (c.inaccuracy) parts.push(`${c.inaccuracy} ketidaktelitian`);
  if (c.mistake) parts.push(`${c.mistake} kesalahan`);
  if (c.blunder) parts.push(`${c.blunder} blunder`);
  return parts.length ? parts.join(', ') : 'tanpa kesalahan berarti';
}

/* Baris langkah yang MEMUAT masalah saja — inilah yang menjaga embed
   tetap di bawah 6000 karakter pada game panjang. */
export function notableMoves(game) {
  return game.moves.filter((m) => m.classification);
}

/* ── Anggaran karakter (dipakai panel "Anggaran embed") ─────────────────── */

export function measureBudget(parts) {
  const used = parts.reduce((a, p) => a + p.text.length, 0);
  return { used, limit: 6000, parts };
}

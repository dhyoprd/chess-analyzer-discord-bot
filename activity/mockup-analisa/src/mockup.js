/* PROTOTYPE — kode buangan (ticket #7). Bukan produksi.

   Tiga varian tata letak untuk DUA permukaan (embed Discord, panel Activity),
   digabung jadi tiga varian yang masing-masing menjawab keduanya sekaligus —
   karena keputusan "apa yang tampil" dan "bagaimana ditata" saling mengunci.

   Varian di sini berbeda STRUKTUR, bukan warna:
     A — Ringkas:     akurasi dulu, daftar langkah hanya yang bermasalah
     B — Papan dulu:  papan + grafik eval jadi pusat, teks menyusul
     C — Analis:      daftar langkah penuh jadi pusat, papan kecil di samping   */

const D = window.ANALISA_DATA || [];
let games = D;
let scenario = 'normal';
let surface = 'embed';
let variant = 'A';
let selectedPly = null;

/* Varian, permukaan, dan skenario disimpan di URL supaya bisa dibagikan,
   bertahan saat reload, dan bisa diambil alih skrip tangkapan layar. */
function readURL() {
  const q = new URLSearchParams(location.search);
  if (['A', 'B', 'C'].includes(q.get('variant'))) variant = q.get('variant');
  if (['embed', 'activity'].includes(q.get('surface'))) surface = q.get('surface');
  if (['normal', 'engine', 'abandoned', 'import', 'oneply', 'long'].includes(q.get('scenario')))
    scenario = q.get('scenario');
}
function writeURL() {
  const q = new URLSearchParams({ variant, surface, scenario });
  history.replaceState(null, '', `${location.pathname}?${q}`);
}

/* ── util ──────────────────────────────────────────────────────────────── */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const PIECES = {
  K: '♔', Q: '♕', R: '♖', B: '♗', N: '♘', P: '♙',
  k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟',
};
const FEN_START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR';

/* Papan mini dari FEN. Cukup untuk mockup: tidak menangani castling/ep
   secara visual karena hanya posisi yang digambar. */
function boardHTML(fen, highlights = [], size = null) {
  const rows = (fen || FEN_START).split(' ')[0].split('/');
  let html = '';
  rows.forEach((row, r) => {
    let f = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) {
        for (let k = 0; k < +ch; k++) {
          html += sqHTML(r, f++, '', highlights);
        }
      } else {
        html += sqHTML(r, f++, PIECES[ch] || '', highlights);
      }
    }
  });
  return `<div class="board"${size ? ` style="width:${size}px"` : ''}>${html}</div>`;
}

function sqHTML(r, f, piece, highlights) {
  const light = (r + f) % 2 === 0;
  const name = 'abcdefgh'[f] + (8 - r);
  const hi = highlights.includes(name) ? ' hi' : '';
  const coord = f === 0 ? `<span class="coord r">${8 - r}</span>`
    : f === 7 ? `<span class="coord f">${'abcdefgh'[f]}</span>` : '';
  return `<div class="sq ${light ? 'l' : 'd'}${hi}">${coord}<span class="pc">${piece}</span></div>`;
}

/* Format eval. `mate 0` muncul saat posisi SUDAH skakmat (tidak ada langkah
   tersisa) -- ditulis "#" bukan "#0", karena "#0" tidak berarti apa-apa bagi
   pembaca catur. Nilai mate positif = kita yang skakmat. */
const fmtEval = (kind, value) => {
  if (kind === 'mate') {
    if (value === 0) return '#';
    return value > 0 ? `#${value}` : `#−${Math.abs(value)}`;
  }
  const p = value / 100;
  const s = Math.abs(p).toFixed(2).replace('.', ',');
  return `${p > 0 ? '+' : p < 0 ? '−' : ''}${s}`;
};

/* Langkah terbaik ditampilkan sebagai SAN (ADR-0009), dengan UCI sebagai
   cadangan bila konversinya gagal. */
const bestMove = (m) => m.best_san || m.best_uci || '—';
const fmtAcc = (v) => `${v.toFixed(1).replace('.', ',')}%`;
const CLASS_LABEL = { inaccuracy: 'Ketidaktelitian', mistake: 'Kesalahan', blunder: 'Blunder' };
const CLASS_SHORT = { inaccuracy: '?!', mistake: '?', blunder: '??' };
const CLASS_CLS = { inaccuracy: 'i', mistake: 'm', blunder: 'b' };

/* ── skenario ──────────────────────────────────────────────────────────── */
function current() {
  if (!games.length) return null;
  const g = JSON.parse(JSON.stringify(games[scenario === 'long' ? 1 : 0] || games[0]));
  if (scenario === 'engine') {
    g.white = 'Budi'; g.black = 'Stockfish (1320)'; g.engine = true;
    g.result = '1-0'; g.label = 'Lawan komputer — tidak mengubah rating';
  } else if (scenario === 'abandoned') {
    g.white = 'Budi'; g.black = 'Sari'; g.abandoned = true;
    g.result = '*'; g.label = 'Ditinggalkan — tidak mengubah rating';
  } else if (scenario === 'import') {
    g.white = 'MagnusCarlsen'; g.black = 'HikaruNakamura'; g.imported = true;
    g.result = '1-0'; g.label = 'Game impor dari Lichess — pemain bayangan';
  } else if (scenario === 'oneply') {
    g.moves = g.moves.slice(0, 1); g.plies = 1; g.accuracy = null;
    g.counts = { white: { inaccuracy: 0, mistake: 0, blunder: 0 },
                 black: { inaccuracy: 0, mistake: 0, blunder: 0 } };
    g.label = 'Hanya 1 ply — akurasi tidak bisa dihitung';
  }
  return g;
}

/* ── pengukuran anggaran ───────────────────────────────────────────────── */
let budgetParts = [];
const B = (label, text) => { budgetParts.push({ label, text }); return text; };

/* ── potongan yang dipakai ulang ───────────────────────────────────────── */

/* Daftar langkah gaya notasi: 1.e4 e5 2.f4?! exf4 */
function moveList(g, { only = null, maxMoves = Infinity } = {}) {
  const out = [];
  let i = 0;
  while (i < g.moves.length && out.length < maxMoves) {
    const w = g.moves[i], b = g.moves[i + 1];
    const r = (m) => {
      if (!m) return '';
      const cls = m.classification && (!only || only.includes(m.classification))
        ? m.classification : null;
      const mark = cls ? `<span class="mk ${CLASS_CLS[cls]}">${CLASS_SHORT[cls]}</span>` : '';
      return `<span class="mv ${cls ? CLASS_CLS[cls] : ''}${m.ply === selectedPly ? ' sel' : ''}" data-ply="${m.ply}">${esc(m.san)}${mark}</span>`;
    };
    out.push(`<span class="no">${w.move_no}.</span>${r(w)}${b ? ' ' + r(b) : ''}`);
    i += 2;
  }
  return out.join(' ');
}

function moveListPlain(g, { only = null } = {}) {
  const out = [];
  for (let i = 0; i < g.moves.length; i += 2) {
    const w = g.moves[i], b = g.moves[i + 1];
    const r = (m) => {
      if (!m) return '';
      const mark = m.classification && (!only || only.includes(m.classification))
        ? CLASS_SHORT[m.classification] : '';
      return m.san + mark;
    };
    out.push(`${w.move_no}.${r(w)}${b ? ' ' + r(b) : ''}`);
  }
  return out.join(' ');
}

/* Tabel momen kritis — dipakai varian C dan panel Activity. */
function momentsTable(g, limit = 8) {
  const ms = g.moves.filter((m) => m.classification)
    .sort((a, b) => (b.delta || 0) - (a.delta || 0)).slice(0, limit);
  if (!ms.length) return '<p class="tiny muted">Tidak ada kesalahan yang mencolok.</p>';
  const rows = ms.map((m) => {
    const c = m.classification;
    return `<tr data-ply="${m.ply}">
      <td class="mono">${m.move_no}${m.color === 'white' ? '.' : '…'} ${esc(m.san)}</td>
      <td>${m.color === 'white' ? 'Putih' : 'Hitam'}</td>
      <td><span class="tag ${CLASS_CLS[c]}">${CLASS_LABEL[c]}</span></td>
      <td class="mono">${fmtEval(m.eval_before_kind, m.eval_before)} → ${fmtEval(m.eval_after_kind, m.eval_after)}</td>
      <td class="mono dim">${bestMove(m)}</td>
    </tr>`;
  }).join('');
  return `<table class="moments">
    <thead><tr><th>Langkah</th><th>Oleh</th><th>Penilaian</th><th>Eval</th><th>Terbaik</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

/* Grafik eval — SVG, area dari POV putih. */
function evalGraph(g, w = 640, h = 92) {
  const ev = g.evals.slice(1);
  const n = ev.length || 1;
  const pts = ev.map((e, i) => {
    let v = e.kind === 'mate' ? (e.value > 0 ? 1 : -1) : e.value / 600;
    v = Math.max(-1, Math.min(1, v));
    return [ (i / Math.max(1, n - 1)) * w, h / 2 - v * (h / 2 - 3) ];
  });
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const area = `M0,${h / 2} ` + pts.map((p) => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
    + ` L${w},${h / 2} Z`;
  const marks = g.moves.filter((m) => m.classification).map((m) => {
    const i = m.ply - 1;
    const x = (i / Math.max(1, n - 1)) * w;
    const y = pts[i] ? pts[i][1] : h / 2;
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${
      { inaccuracy: '#fbbf24', mistake: '#fb923c', blunder: '#f87171' }[m.classification]}"/>`;
  }).join('');
  return `<svg class="evalgraph" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <line x1="0" y1="${h / 2}" x2="${w}" y2="${h / 2}" stroke="#3a3f4a" stroke-width="1" stroke-dasharray="3 4"/>
    <path d="${area}" fill="#e8eaed" opacity="0.10"/>
    <path d="${line}" fill="none" stroke="#e8eaed" stroke-width="1.6"/>
    ${marks}
  </svg>`;
}

/* Bilah eval vertikal (gaya lichess). v = win-chance -1..+1 POV putih. */
function evalBarV(v) {
  const pct = ((1 - v) / 2) * 100;
  return `<div class="evalbar-v" style="height:100%"><div class="fill" style="height:${pct.toFixed(1)}%;bottom:0"></div></div>`;
}

/* ── EMBED DISCORD ─────────────────────────────────────────────────────── */
function embedA(g) {
  budgetParts = [];
  const acc = g.accuracy;
  const resultLine = g.abandoned ? 'Ditinggalkan — tanpa pemenang'
    : g.result === '1-0' ? 'Putih menang' : g.result === '0-1' ? 'Hitam menang'
      : g.result === '1/2-1/2' ? 'Remis' : 'Tanpa pemenang';

  const desc = B('description', acc
    ? `**Putih** ${g.white} — ${fmtAcc(acc.white)}\n**Hitam** ${g.black} — ${fmtAcc(acc.black)}`
    : `**Putih** ${g.white}\n**Hitam** ${g.black}\n\n_Akurasi tidak bisa dihitung: butuh minimal 2 ply._`);

  const notable = g.moves.filter((m) => m.classification);
  const notableTxt = B('field.momen', notable.length
    ? notable.sort((a, b) => (b.delta || 0) - (a.delta || 0)).slice(0, 5)
      .map((m) => `${CLASS_SHORT[m.classification]} **${m.move_no}${m.color === 'white' ? '.' : '…'} ${m.san}** — ${CLASS_LABEL[m.classification]} (${fmtEval(m.eval_before_kind, m.eval_before)} → ${fmtEval(m.eval_after_kind, m.eval_after)})`)
      .join('\n')
    : '_Tidak ada kesalahan mencolok._');

  const fname = B('field.pembukaan', 'Pembukaan');
  const fval = B('field.pembukaan.v', 'C33 — King\'s Gambit Diterima\nBishop\'s Gambit');
  const fno = B('field.langkah', 'Langkah');
  const fnov = B('field.langkah.v', `Pertandingan abad ke-19 · ${g.plies} ply`);

  const html = `<div class="dc"><div class="dc-msg">
    <div class="dc-av">C</div>
    <div class="dc-body">
      <div class="dc-head"><span class="dc-name">Chess Analyzer</span><span class="dc-bot">APP</span><span class="dc-time">Hari ini 14:32</span></div>
      <div class="dc-text">Analisa selesai untuk <b>${esc(g.white)}</b> vs <b>${esc(g.black)}</b>.</div>
      <div class="dc-embed${g.abandoned ? ' flat' : ''}">
        <div class="emb-author"><span>♞</span> Analisa Stockfish</div>
        <div class="emb-title">${esc(g.white)} vs ${esc(g.black)}</div>
        <div class="emb-desc">${esc(desc).replace(/\*\*/g, '')}</div>
        <div class="emb-fields">
          <div class="emb-field full"><div class="fn">${esc(fname)}</div><div class="fv">${esc(fval)}</div></div>
          <div class="emb-field full"><div class="fn">Momen kritis</div><div class="fv">${esc(notableTxt).replace(/\*\*/g, '')}</div></div>
          <div class="emb-field"><div class="fn">${esc(fno)}</div><div class="fv">${esc(fnov)}</div></div>
          <div class="emb-field"><div class="fn">Hasil</div><div class="fv">${esc(resultLine)}</div></div>
        </div>
        <div class="emb-foot">Stockfish 19 · 1.000.000 node/posisi · 4 thread · Hash 128 MB</div>
      </div>
    </div></div></div>`;
  return { html, budget: budgetParts.slice() };
}

function embedB(g) {
  budgetParts = [];
  const acc = g.accuracy;
  const thumb = boardHTML(FEN_START, [], 60).replace(/class="board"/, 'class="board" style="width:60px"');
  /* PENTING: yang diukur adalah TEKS yang dikirim ke Discord, bukan HTML-nya.
     Versi pertama fungsi ini menaruh markup thumbnail ke dalam `desc` dan
     mengukur markup itu, sehingga anggaran terbaca 3.977 karakter padahal
     teks sungguhannya ~200. Ukur teks murni, render HTML terpisah. */
  const descText = acc
    ? `**Putih** ${g.white} — ${fmtAcc(acc.white)}\n**Hitam** ${g.black} — ${fmtAcc(acc.black)}\n\nAkurasi dihitung dari seluruh ${g.plies} langkah. Klik **Buka Papan** untuk melihat eval bar dan menelusuri tiap langkah.`
    : `**Putih** ${g.white}\n**Hitam** ${g.black}\n\n_Akurasi tidak bisa dihitung: butuh minimal 2 ply._`;
  const desc = B('description', descText);

  const wc = g.counts.white, bc = g.counts.black;
  const f1 = B('field.putih', 'Putih');
  const f1v = B('field.putih.v', `${wc.inaccuracy} ?!  ${wc.mistake} ?  ${wc.blunder} ??`);
  const f2 = B('field.hitam', 'Hitam');
  const f2v = B('field.hitam.v', `${bc.inaccuracy} ?!  ${bc.mistake} ?  ${bc.blunder} ??`);
  const f3 = B('field.papan', 'Papan');
  const f3v = B('field.papan.v', 'Buka Papan → telusuri tiap langkah dengan eval bar dan langkah terbaik.');

  const html = `<div class="dc"><div class="dc-msg">
    <div class="dc-av">C</div>
    <div class="dc-body">
      <div class="dc-head"><span class="dc-name">Chess Analyzer</span><span class="dc-bot">APP</span><span class="dc-time">Hari ini 14:32</span></div>
      <div class="dc-text"><b>${esc(g.white)}</b> vs <b>${esc(g.black)}</b> — analisa selesai.</div>
      <div class="dc-embed">
        <div class="emb-title">${esc(g.white)} vs ${esc(g.black)}</div>
        <div class="emb-desc">${thumb}${esc(desc).replace(/\*\*/g, '')}</div>
        <div class="emb-fields">
          <div class="emb-field"><div class="fn">${esc(f1)}</div><div class="fv">${esc(f1v)}</div></div>
          <div class="emb-field"><div class="fn">${esc(f2)}</div><div class="fv">${esc(f2v)}</div></div>
          <div class="emb-field full"><div class="fn">${esc(f3)}</div><div class="fv">${esc(f3v)}</div></div>
        </div>
        <div class="emb-foot">Stockfish 19 · 1.000.000 node/posisi</div>
      </div>
    </div></div></div>`;
  return { html, budget: budgetParts.slice() };
}

function embedC(g) {
  budgetParts = [];
  const acc = g.accuracy;
  const desc = B('description', acc
    ? `**Putih** ${g.white} — ${fmtAcc(acc.white)}\n**Hitam** ${g.black} — ${fmtAcc(acc.black)}`
    : `**Putih** ${g.white}\n**Hitam** ${g.black}\n\n_Akurasi butuh minimal 2 ply._`);

  const notable = g.moves.filter((m) => m.classification);
  const only = B('field.blunder', 'Blunder');
  const onlyV = B('field.blunder.v', notable.filter((m) => m.classification === 'blunder').length
    ? notable.filter((m) => m.classification === 'blunder')
      .map((m) => `${m.move_no}${m.color === 'white' ? '.' : '…'} ${m.san} → ${bestMove(m)}`).join('\n')
    : '—');
  const fl = B('field.urutan', 'Urutan langkah');
  const flv = B('field.urutan.v', moveListPlain(g, { only: ['blunder', 'mistake'] }) || '—');

  const html = `<div class="dc"><div class="dc-msg">
    <div class="dc-av">C</div>
    <div class="dc-body">
      <div class="dc-head"><span class="dc-name">Chess Analyzer</span><span class="dc-bot">APP</span><span class="dc-time">Hari ini 14:32</span></div>
      <div class="dc-text">Analisa selesai — <b>${g.plies} langkah</b> diperiksa.</div>
      <div class="dc-embed">
        <div class="emb-title">${esc(g.white)} vs ${esc(g.black)}</div>
        <div class="emb-desc">${esc(desc).replace(/\*\*/g, '')}</div>
        <div class="emb-fields">
          <div class="emb-field full"><div class="fn">${esc(only)}</div><div class="fv">${esc(onlyV)}</div></div>
          <div class="emb-field full"><div class="fn">${esc(fl)}</div><div class="fv">${esc(flv)}</div></div>
        </div>
        <div class="emb-foot">Hanya kesalahan yang ditampilkan · Stockfish 19</div>
      </div>
    </div></div></div>`;
  return { html, budget: budgetParts.slice() };
}

/* ── PANEL ACTIVITY ────────────────────────────────────────────────────── */
function activityA(g) {
  const acc = g.accuracy;
  const accBox = (lbl, v, cnt) => `<div class="acc-box">
      <div class="lbl">${lbl}</div>
      <div class="val">${v == null ? '—' : fmtAcc(v)}</div>
      <div class="sub">${v == null ? 'butuh minimal 2 ply' : cnt}</div>
    </div>`;
  const sum = (c) => {
    const x = g.counts[c];
    const p = [];
    if (x.inaccuracy) p.push(`${x.inaccuracy} ketidaktelitian`);
    if (x.mistake) p.push(`${x.mistake} kesalahan`);
    if (x.blunder) p.push(`${x.blunder} blunder`);
    return p.length ? p.join(', ') : 'tanpa kesalahan berarti';
  };
  const notable = g.moves.filter((m) => m.classification);

  return `<div class="act">
    <div class="act-top">
      <div><b>${esc(g.white)}</b> <span class="muted">vs</span> <b>${esc(g.black)}</b>
        ${g.engine ? '<span class="pill mut">lawan komputer</span>' : ''}
        ${g.imported ? '<span class="pill mut">impor</span>' : ''}
        ${g.abandoned ? '<span class="pill mut">ditinggalkan</span>' : ''}
      </div>
      <div class="pill ok">Analisa terbaru · Stockfish 19</div>
    </div>
    <div class="acc-row" style="margin-bottom:12px">
      ${accBox('Akurasi putih', acc ? acc.white : null, sum('white'))}
      ${accBox('Akurasi hitam', acc ? acc.black : null, sum('black'))}
    </div>
    <div class="card" style="margin:0">
      <h2>Momen kritis</h2>
      ${momentsTable(g, 6)}
    </div>
    <div class="card">
      <h2>Urutan langkah</h2>
      <div class="movelist">${moveList(g)}</div>
      <div class="legend"><span><b class="i">?!</b> Ketidaktelitian</span><span><b class="m">?</b> Kesalahan</span><span><b class="b">??</b> Blunder</span></div>
    </div>
  </div>`;
}

function activityB(g) {
  const acc = g.accuracy;
  const last = g.moves[g.moves.length - 1];
  const v = last ? (last.wc_after || 0) : 0;
  return `<div class="act">
    <div class="act-top">
      <div><b>${esc(g.white)}</b> <span class="muted">vs</span> <b>${esc(g.black)}</b>
        ${g.engine ? '<span class="pill mut">lawan komputer</span>' : ''}</div>
      <div class="pill gold">${g.plies} langkah</div>
    </div>
    <div style="display:flex;gap:12px;align-items:stretch">
      <div style="width:220px;flex:none">
        ${boardHTML(FEN_START, [])}
        <div class="tiny muted" style="margin-top:6px">Papan mini — posisi awal</div>
      </div>
      <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:10px">
        <div style="display:flex;gap:10px;height:180px">
          ${evalBarV(v)}
          <div style="flex:1;min-width:0">${evalGraph(g)}</div>
        </div>
        <div class="acc-row">
          <div class="acc-box"><div class="lbl">Putih ${esc(g.white)}</div>
            <div class="val">${acc ? fmtAcc(acc.white) : '—'}</div></div>
          <div class="acc-box"><div class="lbl">Hitam ${esc(g.black)}</div>
            <div class="val">${acc ? fmtAcc(acc.black) : '—'}</div></div>
        </div>
      </div>
    </div>
    <div class="card">
      <h2>Filmstrip langkah</h2>
      <div class="movelist" style="max-height:150px">${moveList(g)}</div>
      <div class="legend"><span><b class="i">?!</b> Ketidaktelitian</span><span><b class="m">?</b> Kesalahan</span><span><b class="b">??</b> Blunder</span></div>
    </div>
  </div>`;
}

function activityC(g) {
  const acc = g.accuracy;
  const sel = selectedPly ? g.moves[selectedPly - 1] : g.moves[g.moves.length - 1];
  const selInfo = sel ? `<div class="card" style="margin:0">
      <h2>Langkah ${sel.move_no}${sel.color === 'white' ? '.' : '…'} — ${esc(sel.san)}</h2>
      <div class="kv"><span class="k">Eval sebelum</span><span class="v">${fmtEval(sel.eval_before_kind, sel.eval_before)}</span></div>
      <div class="kv"><span class="k">Eval sesudah</span><span class="v">${fmtEval(sel.eval_after_kind, sel.eval_after)}</span></div>
      <div class="kv"><span class="k">Penilaian</span><span class="v ${sel.classification ? CLASS_CLS[sel.classification] : ''}">${sel.classification ? CLASS_LABEL[sel.classification] : 'baik'}</span></div>
      <div class="kv"><span class="k">Langkah terbaik</span><span class="v">${bestMove(sel)}</span></div>
    </div>` : '';
  return `<div class="act">
    <div class="act-top">
      <div><b>${esc(g.white)}</b> <span class="muted">vs</span> <b>${esc(g.black)}</b></div>
      <div class="pill ok">${acc ? `Putih ${fmtAcc(acc.white)} · Hitam ${fmtAcc(acc.black)}` : 'tanpa akurasi'}</div>
    </div>
    <div style="display:grid;grid-template-columns:200px 1fr;gap:12px;align-items:start">
      <div>
        ${boardHTML(FEN_START, [])}
        <div class="tiny muted" style="margin:6px 0 10px">Papan kecil — klik langkah di kanan</div>
        ${selInfo}
      </div>
      <div>
        <div class="card" style="margin:0 0 10px">
          <h2>Grafik eval</h2>
          ${evalGraph(g, 560, 80)}
        </div>
        <div class="card" style="margin:0">
          <h2>Urutan langkah — klik untuk menelusuri</h2>
          <div class="movelist" style="max-height:230px">${moveList(g)}</div>
          <div class="legend"><span><b class="i">?!</b> Ketidaktelitian</span><span><b class="m">?</b> Kesalahan</span><span><b class="b">??</b> Blunder</span></div>
        </div>
      </div>
    </div>
  </div>`;
}

/* ── render ────────────────────────────────────────────────────────────── */
const NOTES = {
  A: ['Ringkas — akurasi di depan, daftar langkah hanya yang bermasalah',
      'Embed kecil; panel Activity menaruh akurasi sebagai angka terbesar di layar, lalu tabel momen kritis, lalu urutan langkah lengkap sebagai rujukan.'],
  B: ['Papan dulu — papan & grafik eval jadi pusat',
      'Embed memakai thumbnail papan dan hanya meringkas hitungan; panel Activity menaruh papan + eval bar + grafik di baris atas, filmstrip langkah di bawah.'],
  C: ['Analis — daftar langkah jadi pusat, bisa ditelusuri',
      'Embed hanya menampilkan blunder + urutan langkah yang bermasalah; panel Activity menjadikan daftar langkah sebagai sumbu navigasi, dengan papan dan detail langkah di samping.'],
};

/* Panel anggaran SELALU mengukur embed varian A, apa pun varian yang tampil.
   Alasannya: hanya A yang menampilkan daftar momen kritis penuh, jadi ia
   adalah kasus terberat untuk dibandingkan antar skenario. Kalau panel ini
   mengikuti varian, angka akan melompat-lompat dan tidak bisa dibandingkan.
   Skrip tools/verify_embed_budget.py menghitung ulang angka yang sama secara
   independen dari data mentah -- kedua jalur harus sepakat. */
function render() {
  const g = current();
  if (!g) { $('#stage').innerHTML = '<p class="muted">Data tidak termuat.</p>'; return; }
  selectedPly = null;
  writeURL();

  const embed = { A: embedA, B: embedB, C: embedC }[variant](g);
  const activity = { A: activityA, B: activityB, C: activityC }[variant](g);
  const forBudget = variant === 'A' ? embed : embedA(g);

  $('#note').innerHTML = `<b>Varian ${variant} — ${NOTES[variant][0]}.</b> ${NOTES[variant][1]}`;
  $('#stage').innerHTML = surface === 'embed' ? embed.html : activity;
  renderBudget(forBudget.budget, variant !== 'A');
  renderDataInfo(g);

  const extras = [];
  if (surface === 'embed') extras.push(progressDemo(g));
  extras.push(caseTable(g));
  $('#extras').innerHTML = extras.join('');

  wireMoves();
  syncControls();
  $('#vlabel').innerHTML = `${variant} — ${NOTES[variant][0].split('—')[0].trim()} <span class="sub">· ${surface === 'embed' ? 'embed' : 'Activity'}</span>`;
}

/* Tombol disamakan dengan state (penting saat state datang dari URL). */
function syncControls() {
  document.querySelectorAll('#surface button').forEach((b) =>
    b.setAttribute('aria-pressed', b.dataset.s === surface));
  document.querySelectorAll('#scenario button').forEach((b) =>
    b.setAttribute('aria-pressed', b.dataset.c === scenario));
}

/* Pesan progres — item 3 ticket. Di-edit tiap ~10%, dihapus saat selesai. */
function progressDemo(g) {
  const total = g.plies;
  const done = Math.round(total * 0.3);
  return `<h3>Pesan progres <span class="tiny muted">— di-edit di tempat, dihapus saat selesai</span></h3>
  <div class="dc" style="padding:10px"><div class="dc-msg">
    <div class="dc-av" style="width:32px;height:32px;font-size:13px">C</div>
    <div class="dc-body">
      <div class="dc-head"><span class="dc-name" style="font-size:14px">Chess Analyzer</span><span class="dc-bot">APP</span></div>
      <div class="prog">
        <div class="t">Menganalisa… <b>${done}/${total} langkah</b> <span class="dim">(1 game menunggu di antrian)</span></div>
        <div class="pbar"><div class="f" style="width:${((done / total) * 100).toFixed(0)}%"></div></div>
      </div>
      <div class="tiny dim" style="margin-top:6px">Tanpa mention — pesan ini tidak memicu notifikasi, dan dihapus begitu analisa selesai.</div>
    </div></div></div>`;
}

function caseTable(g) {
  const rows = [
    ['Ditinggalkan', 'Tanpa baris pemenang; tetap dianalisa sampai langkah terakhir.', 'tanpa pemenang'],
    ['Remis', 'Sama seperti biasa, hanya tanpa baris pemenang.', 'remis'],
    ['Lawan komputer', 'Lencana “lawan komputer”; lawan disebut namanya tanpa mention.', 'tanpa mention'],
    ['Impor', 'Pemain bayangan: nama disebut, tidak bisa di-mention.', 'pemain bayangan'],
    ['1 ply', 'Akurasi tidak bisa dihitung; tetap tampil tanpa angka akurasi.', 'tanpa akurasi'],
    [`Panjang (${games[1] ? games[1].plies : '100+'} ply)`, 'Hanya kesalahan yang ditampilkan — daftar penuh dipindah ke Activity.', 'dipangkas'],
  ];
  return `<h3 style="margin-top:16px">Kasus khusus</h3>
  <table class="moments"><thead><tr><th>Kasus</th><th>Perlakuan</th><th></th></tr></thead><tbody>
  ${rows.map(([a, b, c]) => `<tr><td>${esc(a)}</td><td class="muted">${esc(b)}</td><td class="dim tiny">${esc(c)}</td></tr>`).join('')}
  </tbody></table>`;
}

function renderBudget(parts, isFallback = false) {
  const used = parts.reduce((a, p) => a + p.text.length, 0);
  const pct = (used / 6000) * 100;
  const cls = pct > 90 ? 'bad' : pct > 65 ? 'warn' : '';
  $('#budget').innerHTML = `
    ${isFallback ? '<div class="tiny dim" style="margin-bottom:6px">Diukur dari <b>varian A</b> — kasus terberat, supaya angkanya bisa dibandingkan antar skenario.</div>' : ''}
    <div class="kv"><span class="k">Terpakai</span><span class="v ${cls === 'bad' ? 'over' : cls === 'warn' ? 'near' : 'ok'}">${used.toLocaleString('id-ID')} / 6.000</span></div>
    <div class="budget-bar"><div class="f ${cls}" style="width:${Math.min(100, pct).toFixed(1)}%"></div></div>
    <div class="tiny dim">${pct.toFixed(1).replace('.', ',')}% dari anggaran · sisa ${(6000 - used).toLocaleString('id-ID')} karakter</div>
    <div style="margin-top:10px">${parts.map((p) => `
      <div class="kv"><span class="k tiny">${esc(p.label)}</span><span class="v tiny">${p.text.length.toLocaleString('id-ID')}</span></div>`).join('')}</div>`;
}

function renderDataInfo(g) {
  const notable = g.moves.filter((m) => m.classification).length;
  $('#datainfo').innerHTML = `
    <div class="kv"><span class="k">Sumber</span><span class="v tiny">Stockfish 19, 1 jt node</span></div>
    <div class="kv" style="display:block"><div class="k">Game</div>
      <div class="v tiny" style="text-align:left;line-height:1.4">${esc(g.label || '—')}</div></div>
    <div class="kv"><span class="k">Ply</span><span class="v">${g.plies}</span></div>
    <div class="kv"><span class="k">Langkah berpenilaian</span><span class="v">${notable}</span></div>
    <div class="kv"><span class="k">Akurasi</span><span class="v">${g.accuracy ? fmtAcc(g.accuracy.white) + ' / ' + fmtAcc(g.accuracy.black) : '—'}</span></div>
    <div class="kv"><span class="k">Karakter daftar penuh</span><span class="v">${moveListPlain(g).length.toLocaleString('id-ID')}</span></div>`;
}

function wireMoves() {
  document.querySelectorAll('[data-ply]').forEach((el) => {
    el.addEventListener('click', () => {
      selectedPly = +el.dataset.ply;
      if (variant === 'C' && surface === 'activity') render();
      else document.querySelectorAll('.mv.sel').forEach((x) => x.classList.remove('sel'));
    });
  });
}

/* ── kontrol ───────────────────────────────────────────────────────────── */
$('#surface').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  surface = b.dataset.s;
  render();
});
$('#scenario').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  scenario = b.dataset.c;
  render();
});
const cycle = (d) => {
  const keys = ['A', 'B', 'C'];
  variant = keys[(keys.indexOf(variant) + d + keys.length) % keys.length];
  render();
};
$('#prev').addEventListener('click', () => cycle(-1));
$('#next').addEventListener('click', () => cycle(1));
document.addEventListener('keydown', (e) => {
  const t = document.activeElement;
  if (t && /input|textarea/i.test(t.tagName)) return;
  if (e.key === 'ArrowLeft') cycle(-1);
  if (e.key === 'ArrowRight') cycle(1);
});

readURL();
render();

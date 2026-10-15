/* PROTOTYPE (ticket #7) — periksa bahwa tiap varian menghitung SEMUA bagian
   yang dihitung Discord.

   Bug ini terjadi DUA kali: sekali karena mengukur HTML alih-alih teks, sekali
   karena lupa menghitung title dan footer. Keduanya menghasilkan angka yang
   terlihat wajar tapi salah.

   Skrip ini menjalankan `src/mockup.js` yang SUNGGUHAN di Node dengan DOM
   minimal, memanggil tiap pembangun embed, lalu membaca angka yang benar-benar
   ditampilkan panel anggaran. Jadi ia menguji kode yang dipakai mockup, bukan
   salinan logikanya.

   Pakai: node tools/check_budget_consistency.mjs <data.json> */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');

const dataPath = process.argv[2] || path.join(ROOT, 'data', 'analisa-nyata.json');
const games = JSON.parse(fs.readFileSync(dataPath, 'utf8'));

/* ── DOM minimal ────────────────────────────────────────────────────────── */
const captured = {};
function fakeEl(id) {
  return {
    _id: id,
    innerHTML: '',
    dataset: {},
    setAttribute() {},
    addEventListener() {},
    classList: { add() {}, remove() {} },
    querySelector: () => null,
    querySelectorAll: () => [],
    children: [],
    get textContent() { return ''; },
  };
}
const els = {};
const getEl = (sel) => {
  if (!els[sel]) els[sel] = fakeEl(sel);
  return els[sel];
};

globalThis.window = { ANALISA_DATA: games };
globalThis.document = {
  querySelector: getEl,
  querySelectorAll: () => [],
  addEventListener: () => {},
  activeElement: null,
};
globalThis.location = { search: '', pathname: '/index.html' };
globalThis.history = { replaceState: () => {} };

/* ── muat mockup yang sesungguhnya ──────────────────────────────────────── */
const src = fs.readFileSync(path.join(ROOT, 'src', 'mockup.js'), 'utf8');
// Panel anggaran ditulis ke #budget; tangkap HTML-nya lewat setter.
let budgetHTML = '';
Object.defineProperty(getEl('#budget'), 'innerHTML', {
  get: () => budgetHTML,
  set: (v) => { budgetHTML = v; },
});

// Jalankan di scope modul dengan `window`/`document` yang sudah dipalsukan.
const run = new Function('window', 'document', 'location', 'history', src);
run(globalThis.window, globalThis.document, globalThis.location, globalThis.history);

/* ── baca angka dari panel anggaran ─────────────────────────────────────── */
function parseBudget(html) {
  const parts = {};
  // Label boleh diawali huruf kecil (title, footer, description) maupun
  // "field.xxx". Versi pertama pola ini menuntut huruf kecil di awal DAN
  // minimal satu karakter lain, sehingga title/footer tidak tertangkap dan
  // semua skenario dilaporkan GAGAL padahal sudah benar.
  const re = /<span class="k[^"]*">([a-zA-Z][a-zA-Z.]*)<\/span><span class="v[^"]*">([\d.]+)<\/span>/g;
  let m;
  while ((m = re.exec(html))) {
    parts[m[1]] = parseInt(m[2].replace(/\./g, ''), 10);
  }
  return parts;
}

const WAJIB = ['title', 'footer', 'description'];

/* Panel anggaran selalu mengukur varian B (yang dipilih). Periksa tiap
   skenario karena panjang daftar langkah berbeda-beda. */
const SCENARIOS = ['normal', 'long', 'engine', 'abandoned', 'import', 'oneply'];
let gagal = 0;

console.log('='.repeat(74));
console.log('KONSISTENSI PANEL ANGGARAN (varian B — yang dipilih)');
console.log('='.repeat(74));

for (const scenario of SCENARIOS) {
  // Picu render ulang untuk skenario ini.
  globalThis.location.search = `?variant=B&surface=embed&scenario=${scenario}`;
  const rerun = new Function('window', 'document', 'location', 'history', src);
  rerun(globalThis.window, globalThis.document, globalThis.location, globalThis.history);

  const parts = parseBudget(budgetHTML);
  const labels = Object.keys(parts);
  if (!labels.length) {
    console.log(`  [GAGAL] ${scenario}: panel anggaran tidak terbaca`);
    gagal++;
    continue;
  }
  const hilang = WAJIB.filter((w) => !(w in parts));
  const fields = labels.filter((k) => k.startsWith('field.') && !k.endsWith('.v'));
  const total = Object.values(parts).reduce((a, b) => a + b, 0);
  // CATATAN: `!hilang` SALAH di JavaScript — array kosong itu truthy, jadi
  // `![]` bernilai false dan semua skenario dilaporkan GAGAL padahal benar.
  // Harus dibandingkan panjangnya.
  const ok = hilang.length === 0;
  gagal += ok ? 0 : 1;
  console.log(`  [${ok ? 'OK   ' : 'GAGAL'}] ${scenario.padEnd(10)} total=${String(total).padStart(5)}` +
    `  ${fields.length} field  ${ok ? 'title+footer+description dihitung' : 'HILANG: ' + hilang.join(', ')}`);
}

console.log();
console.log('='.repeat(74));
console.log('BANDINGKAN DENGAN tools/verify_embed_budget.py');
console.log('='.repeat(74));
for (const scenario of ['normal', 'long']) {
  globalThis.location.search = `?variant=B&surface=embed&scenario=${scenario}`;
  const rerun = new Function('window', 'document', 'location', 'history', src);
  rerun(globalThis.window, globalThis.document, globalThis.location, globalThis.history);
  const total = Object.values(parseBudget(budgetHTML)).reduce((a, b) => a + b, 0);
  console.log(`  ${scenario.padEnd(10)} mockup melaporkan ${total}`);
}

console.log();
if (gagal) {
  console.log(`  ${gagal} masalah — panel anggaran tidak menghitung semua bagian`);
  process.exit(1);
}
console.log('  Semua varian menghitung title, footer, description, dan tiap field.');

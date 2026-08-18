/*
  KATALOG DERLEME
  ---------------
  Kullanim:
    node katalog-derle.mjs           -> gorselleri tarar ve index.html'i gunceller
    node katalog-derle.mjs --liste   -> gorsel dosya adi listesini uretir (katalog-gorsel-listesi.md)

  Gorsel eklemek icin: dosyayi v3-saha/urun-gorselleri/ icine, adi kategori
  kimligiyle ayni olacak sekilde koyun. Ornek: motors.jpg, ac-motors.webp
  Eslesmeyen dugumler otomatik olarak teknik-resim motifine duser.
*/
import { readFile, writeFile, readdir, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, extname, basename } from 'node:path';

const ROOT = import.meta.dirname;
const PAGE = join(ROOT, 'v3-saha', 'index.html');
const DATA = join(ROOT, 'v3-saha', 'katalog', 'catalog.json');
const RENDER = join(ROOT, 'v3-saha', 'katalog', 'render.js');
const IMGDIR = join(ROOT, 'v3-saha', 'urun-gorselleri');
const WEBDIR = 'urun-gorselleri';                      // index.html'e gore goreli yol
const OK_EXT = ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.svg'];

const START = '/* ==== KATALOG: BASLANGIC (uretilmis - elle duzenlemeyin) ==== */';
const END = '/* ==== KATALOG: BITIS ==== */';

const catalog = JSON.parse(await readFile(DATA, 'utf8'));

// --- her kademedeki dugumleri dolas ---
function* walk(nodes, depth = 0, trail = []) {
  for (const n of nodes) {
    yield { node: n, depth, trail };
    if (n.kids?.length) yield* walk(n.kids, depth + 1, [...trail, n.tr]);
  }
}

if (process.argv.includes('--liste')) {
  const rows = ['# Katalog gorsel dosya adlari', '',
    'Dosyayi `v3-saha/urun-gorselleri/` icine koyun; adi asagidaki kimlikle ayni olsun.',
    'Uzanti serbest: .jpg .jpeg .png .webp .avif', '',
    'Onerilen en-boy orani 4:3, en az 800x600 piksel.', ''];
  let d0 = 0, d1 = 0, d2 = 0;
  for (const { node, depth, trail } of walk(catalog)) {
    if (depth === 0) { d0++; rows.push('', `## ${node.tr}  \`${node.id}\``); }
    else if (depth === 1) { d1++; rows.push(`- \`${node.id}\` — ${node.tr}`); }
    else d2++;
  }
  rows.push('', `---`, `Toplam: ${d0} ana grup, ${d1} alt grup, ${d2} urun ailesi.`,
    `Sadece ana gruplara gorsel koymak da yeterli; digerleri motife duser.`);
  await writeFile(join(ROOT, 'katalog-gorsel-listesi.md'), rows.join('\n'), 'utf8');
  console.log(`katalog-gorsel-listesi.md yazildi (${d0} ana / ${d1} alt / ${d2} aile)`);
  process.exit(0);
}

// --- gorselleri tara ---
// Once birebir kimlik eslesmesi denenir. Tutmazsa dosya adi kelimelere ayrilip
// kategori adiyla ortusme oranina bakilir; tedarikci paketlerini elle yeniden
// adlandirmak gerekmesin diye.
if (!existsSync(IMGDIR)) await mkdir(IMGDIR, { recursive: true });
const files = (await readdir(IMGDIR)).filter((f) => OK_EXT.includes(extname(f).toLowerCase()));

const NOISE = new Set(['image', 'images', 'img', 'photo', 'picture', 'pic', 'hero', 'banner',
  'category', 'categories', 'cat', 'main', 'thumb', 'thumbnail', 'large', 'small', 'web',
  'final', 'copy', 'new', 'grainger', 'panorama', 'resim', 'gorsel', 'kategori', 'ana', 've', 'and']);

const trMap = { 'ç': 'c', 'ğ': 'g', 'ı': 'i', 'İ': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u' };
const toks = (s) => String(s).toLowerCase()
  .replace(/[çğıİöşü]/g, (c) => trMap[c] || c)
  .split(/[^a-z0-9]+/)
  .filter((t) => t.length > 2 && !NOISE.has(t) && !/^\d+$/.test(t));

const nodes = [...walk(catalog)];
// Ayni kimlik birden fazla kademede olabilir (ornek: "bearings" hem ana grup hem
// Guc Aktarma'nin alt grubu). Birebir eslesmede daima en ust kademedeki kazanir.
const byId = new Map();
for (const { node, depth } of nodes) {
  const k = node.id.toLowerCase();
  const cur = byId.get(k);
  if (!cur || depth < cur.depth) byId.set(k, { node, depth });
}
const nodeToks = new Map(nodes.map(({ node, depth }) =>
  [node, { t: new Set(toks(node.id + ' ' + node.en + ' ' + node.tr)), depth }]));

for (const { node } of nodes) delete node.img;

let matched = 0, fuzzy = 0;
const orphans = [];
const taken = new Set();

for (const f of files) {
  const stem = basename(f, extname(f));
  const hit = byId.get(stem.toLowerCase());
  const exact = hit && !hit.node.img ? hit.node : null;
  if (exact) { exact.img = `${WEBDIR}/${f}`; matched++; taken.add(exact); continue; }

  const ft = new Set(toks(stem));
  if (!ft.size) { orphans.push(f); continue; }
  let best = null, bestScore = 0;
  for (const [node, { t: nt, depth }] of nodeToks) {
    if (taken.has(node) || !nt.size) continue;
    let hit = 0;
    for (const t of ft) if (nt.has(t)) hit++;
    if (!hit) continue;
    // esit ortusmede ust kademe kazansin
    const score = (hit / ft.size) * 0.6 + (hit / nt.size) * 0.4 - depth * 0.04;
    if (score > bestScore) { bestScore = score; best = node; }
  }
  if (best && bestScore >= 0.45) {
    best.img = `${WEBDIR}/${f}`; matched++; fuzzy++; taken.add(best);
  } else orphans.push(f);
}

// --- sayfaya isle ---
const render = await readFile(RENDER, 'utf8');
let html = await readFile(PAGE, 'utf8');
const json = JSON.stringify(catalog).replace(/<\//g, '<\\/');   // </script> erken kapanmasin
const block = `${START}\nconst CATALOG = ${json};\n${render.trim()}\n${END}`;

const s = html.indexOf(START), e = html.indexOf(END);
if (s !== -1 && e !== -1) html = html.slice(0, s) + block + html.slice(e + END.length);
else {
  const tail = html.lastIndexOf('</script>');
  if (tail === -1) { console.error('HATA: </script> bulunamadi'); process.exit(1); }
  html = html.slice(0, tail) + '\n' + block + '\n' + html.slice(tail);
}
await writeFile(PAGE, html, 'utf8');

let l1 = catalog.length, l2 = 0, l3 = 0;
for (const a of catalog) for (const b of a.kids) { l2++; l3 += b.kids.length; }
const topWith = catalog.filter((n) => n.img).length;
console.log(`katalog: ${l1} ana grup / ${l2} alt grup / ${l3} urun ailesi`);
console.log(`gorsel : klasorde ${files.length} dosya -> ${matched} eslesti (${fuzzy} tanesi ad benzerligiyle)`);
console.log(`         ana kategori kapsami: ${topWith}/${l1}`);
if (orphans.length) console.log(`         eslesmeyen dosya (${orphans.length}): ${orphans.slice(0, 10).join(', ')}${orphans.length > 10 ? ' ...' : ''}`);
if (topWith < l1) {
  const missing = catalog.filter((n) => !n.img).map((n) => n.id);
  console.log(`         gorseli olmayan ana kategoriler (${missing.length}): ${missing.slice(0, 10).join(', ')}${missing.length > 10 ? ' ...' : ''}`);
}
console.log(`index.html -> ${(Buffer.byteLength(html, 'utf8') / 1024).toFixed(0)} KB`);

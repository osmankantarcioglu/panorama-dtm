/*
  OTOMATIK GORSEL CEKME
  ---------------------
  Ticari kullanima acik lisansli (CC0 / kamu malı / CC BY / CC BY-SA) gorselleri
  Openverse uzerinden arar, en uygununu secer ve v3-saha/urun-gorselleri/ altina
  kategori kimligiyle indirir. Atif kayitlarini ATIF.json + ATIF.md dosyalarina yazar.

  Kullanim:
    node gorsel-cek.mjs              -> gorseli olmayan kategorileri ceker
    node gorsel-cek.mjs --hepsi      -> mevcutlarin uzerine yazar
    node gorsel-cek.mjs motors tools -> sadece verilen kimlikleri ceker
    node gorsel-cek.mjs --kuru       -> indirmez, ne bulacagini listeler

  NOT: Grainger vb. sitelerden gorsel CEKMEZ. Sadece lisansi ticari kullanima
  acik kaynaklardan indirir. Lisans geregi ATIF.md icerigi sayfada gosterilmelidir.
*/
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, extname } from 'node:path';

const ROOT = import.meta.dirname;
const IMGDIR = join(ROOT, 'v3-saha', 'urun-gorselleri');
const DATA = join(ROOT, 'v3-saha', 'katalog', 'catalog.json');
const API = 'https://api.openverse.org/v1/images/';

// Kategori adlari tek basina zayif sonuc veriyor ("Hardware", "Safety" gibi).
// Her kategori icin somut, gorsellenebilir terimler.
const QUERIES = {
  'abrasives': ['grinding wheel', 'sandpaper abrasive', 'angle grinder disc'],
  'adhesives-sealants-tape': ['adhesive tape roll', 'sealant cartridge', 'duct tape'],
  'bearings': ['ball bearing', 'roller bearing', 'bearing steel'],
  'cleaning-janitorial': ['cleaning trolley bucket', 'janitorial supplies', 'mop bucket'],
  'compressors-generators': ['air compressor', 'diesel generator', 'compressor industrial'],
  'electrical': ['electrical switchgear', 'circuit breaker panel', 'electrical contactor'],
  'electronics-batteries': ['industrial battery', 'electronic components', 'battery cells'],
  'fasteners': ['hex bolts nuts', 'screws fasteners', 'bolt nut washer'],
  'filtration': ['industrial filter cartridge', 'oil filter', 'air filter element'],
  'fleet-vehicle-maintenance': ['truck maintenance workshop', 'vehicle repair garage', 'hydraulic jack'],
  'food-service-processing': ['commercial kitchen stainless', 'food processing machine', 'catering kitchen'],
  'furnishings-hospitality-building': ['warehouse shelving racks', 'building materials', 'steel shelving'],
  'hardware': ['hand tools hardware', 'door hinges lock', 'hardware store tools'],
  'hvac-and-refrigeration': ['hvac air conditioning unit', 'refrigeration compressor', 'ventilation duct'],
  'hydraulics': ['hydraulic cylinder', 'hydraulic hose fittings', 'hydraulic pump'],
  'lighting': ['led floodlight', 'industrial lighting fixture', 'led high bay'],
  'lubrication': ['grease gun', 'lubricant oil can', 'industrial lubricant'],
  'machining': ['milling cutter tool', 'cnc machining lathe', 'cutting insert'],
  'material-handling': ['pallet truck', 'forklift warehouse', 'hand pallet jack'],
  'motors': ['electric motor', 'induction motor industrial', 'motor gearbox'],
  'outdoor-equipment': ['lawn mower', 'chainsaw outdoor', 'garden equipment'],
  'packaging-shipping': ['cardboard boxes shipping', 'stretch wrap pallet', 'packaging carton'],
  'paints-equipment-supplies': ['paint roller brush', 'spray gun painting', 'paint cans'],
  'pipe-hose-tube-fittings': ['pipe fittings copper', 'steel pipes', 'hose fitting'],
  'plumbing': ['plumbing valve faucet', 'plumbing pipes fittings', 'water tap'],
  'pneumatics': ['pneumatic cylinder', 'pneumatic valve fitting', 'compressed air tools'],
  'power-transmission': ['drive chain sprocket', 'v belt pulley', 'gear transmission'],
  'pumps': ['centrifugal pump', 'industrial water pump', 'submersible pump'],
  'raw-materials': ['steel bars profiles', 'metal stock material', 'steel plate sheet'],
  'safety': ['safety helmet gloves', 'personal protective equipment', 'hard hat safety'],
  'security': ['padlock security', 'cctv camera security', 'access control lock'],
  'test-instruments': ['digital multimeter', 'measuring instrument caliper', 'test meter'],
  'tools': ['hand tools set', 'cordless drill', 'wrench tools'],
  'valves': ['industrial valve', 'ball valve brass', 'butterfly valve'],
  'welding': ['welding torch arc', 'welder welding metal', 'mig welding'],
};

const LICENSE_RANK = { 'pdm': 0, 'cc0': 1, 'by': 2, 'by-sa': 3 };   // dusuk = tercihli
const OK_LICENSES = Object.keys(LICENSE_RANK);
const OK_TYPES = ['jpg', 'jpeg', 'png', 'webp'];

const args = process.argv.slice(2);
const force = args.includes('--hepsi');
const dry = args.includes('--kuru');
const only = args.filter((a) => !a.startsWith('--'));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function search(q) {
  const url = `${API}?q=${encodeURIComponent(q)}&license=${OK_LICENSES.join(',')}` +
    `&page_size=20&mature=false`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Openverse ${res.status}`);
  const j = await res.json();
  return j.results || [];
}

function score(r, q) {
  if (!r.url || r.mature) return -1;
  const type = (r.filetype || extname(r.url).slice(1) || '').toLowerCase();
  if (!OK_TYPES.includes(type)) return -1;
  const w = r.width || 0, h = r.height || 0;
  if (w < 640 || h < 420) return -1;                       // kutucuk 4:3, kucuk gorsel olmaz
  let s = 0;
  s += (3 - LICENSE_RANK[r.license]) * 12;                 // acik lisans tercihli
  s += Math.min(w / 200, 12);                              // buyuk gorsel tercihli
  const ratio = w / h;
  s += ratio > 1.05 && ratio < 2.1 ? 10 : 0;               // yataya yakin olsun
  const title = (r.title || '').toLowerCase();
  const hits = q.toLowerCase().split(/\s+/).filter((t) => title.includes(t)).length;
  s += hits * 6;
  return s;
}

async function download(url, dest) {
  const res = await fetch(url, { headers: { 'User-Agent': 'PanoramaKatalog/1.0' } });
  if (!res.ok) throw new Error(`indirme ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 8000) throw new Error('dosya cok kucuk');
  await writeFile(dest, buf);
  return buf.length;
}

// --- calistir ---
if (!existsSync(IMGDIR)) await mkdir(IMGDIR, { recursive: true });
const catalog = JSON.parse(await readFile(DATA, 'utf8'));
const have = new Set((await readdir(IMGDIR))
  .filter((f) => OK_TYPES.includes(extname(f).slice(1).toLowerCase()))
  .map((f) => f.slice(0, -extname(f).length).toLowerCase()));

let credits = {};
const creditPath = join(IMGDIR, 'ATIF.json');
if (existsSync(creditPath)) credits = JSON.parse(await readFile(creditPath, 'utf8'));

const targets = catalog.filter((n) => (only.length ? only.includes(n.id) : true))
  .filter((n) => force || !have.has(n.id));

console.log(`hedef: ${targets.length} kategori${force ? ' (uzerine yazilacak)' : ''}\n`);

let ok = 0, fail = [];
for (const node of targets) {
  const queries = QUERIES[node.id] || [node.en];
  let best = null, bestQ = '';
  for (const q of queries) {
    let results = [];
    try { results = await search(q); } catch (e) { await sleep(1500); continue; }
    for (const r of results) {
      const s = score(r, q);
      if (s > 0 && (!best || s > best._s)) { best = { ...r, _s: s }; bestQ = q; }
    }
    await sleep(400);
    if (best && best._s > 45) break;                        // yeterince iyi
  }
  if (!best) { fail.push(node.id); console.log(`  X  ${node.id.padEnd(34)} uygun sonuc yok`); continue; }

  const type = (best.filetype || extname(best.url).slice(1) || 'jpg').toLowerCase();
  const file = `${node.id}.${type === 'jpeg' ? 'jpg' : type}`;
  if (dry) {
    console.log(`  .  ${node.id.padEnd(34)} ${best.license.toUpperCase().padEnd(6)} ${best.width}x${best.height}  ${(best.title || '').slice(0, 46)}`);
    ok++; continue;
  }
  try {
    const size = await download(best.url, join(IMGDIR, file));
    credits[node.id] = {
      dosya: file, kategori: node.tr,
      baslik: best.title || '', yapan: best.creator || 'bilinmiyor',
      yapan_url: best.creator_url || '', lisans: best.license, lisans_surum: best.license_version || '',
      lisans_url: best.license_url || '', kaynak: best.foreign_landing_url || best.url,
      saglayici: best.provider || '', atif: best.attribution || '',
    };
    ok++;
    console.log(`  OK ${node.id.padEnd(34)} ${best.license.toUpperCase().padEnd(6)} ${best.width}x${best.height} ${(size / 1024).toFixed(0).padStart(5)}KB  ${(best.title || '').slice(0, 38)}`);
  } catch (e) {
    fail.push(node.id);
    console.log(`  X  ${node.id.padEnd(34)} ${e.message}`);
  }
  await sleep(300);
}

if (!dry && Object.keys(credits).length) {
  await writeFile(creditPath, JSON.stringify(credits, null, 1), 'utf8');
  const md = ['# Görsel kaynakları ve telif atıfları', '',
    'Bu sayfadaki kategori görselleri Creative Commons lisanslarıyla kullanılmaktadır.',
    'Lisans gereği aşağıdaki atıfların sitede erişilebilir olması gerekir.', '',
    '| Kategori | Görsel | Yapan | Lisans | Kaynak |', '|---|---|---|---|---|'];
  for (const c of Object.values(credits)) {
    md.push(`| ${c.kategori} | ${c.baslik.slice(0, 60) || '—'} | ${c.yapan} | [${c.lisans.toUpperCase()} ${c.lisans_surum}](${c.lisans_url}) | [bağlantı](${c.kaynak}) |`);
  }
  await writeFile(join(IMGDIR, 'ATIF.md'), md.join('\n'), 'utf8');
}

console.log(`\n${ok} basarili, ${fail.length} basarisiz${fail.length ? ': ' + fail.join(', ') : ''}`);
if (!dry) console.log(`atif kayitlari: v3-saha/urun-gorselleri/ATIF.json + ATIF.md`);
console.log(`sonra: node katalog-derle.mjs`);

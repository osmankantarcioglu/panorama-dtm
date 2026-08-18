// ===== ÜRÜN KATALOĞU =====
// Üç kademe: ana grup -> alt grup -> ürün ailesi. Üçüncü kademe yaprak.
// Görseller yerine kimlikten türetilen teknik-resim motifi çiziliyor; gerçek
// fotoğraf geldiğinde düğüme "img" alanı eklemek yeterli.
(function () {
  const root = document.getElementById('cat-root');
  if (!root) return;

  const gridEl = document.getElementById('cat-grid');
  const pathEl = document.getElementById('cat-path');
  const rungEl = document.getElementById('cat-rungs');
  const backEl = document.getElementById('cat-back');
  const headEl = document.getElementById('cat-head');
  const countEl = document.getElementById('cat-count');

  const T = {
    tr: { root: 'Ürün kataloğu', sub: 'alt grup', fam: 'ürün ailesi', item: 'kalem',
          back: 'Geri', level: 'Kademe', ask: 'Teklif iste', groups: 'ana grup',
          lead: 'Ana gruptan ürün ailesine üç kademe. Her kademede şartname, kalite belgesi ve yerinde teslimat aynı.' },
    en: { root: 'Product catalogue', sub: 'sub-group', fam: 'product family', item: 'line',
          back: 'Back', level: 'Level', ask: 'Request quote', groups: 'main groups',
          lead: 'Three levels from main group to product family. Specification, certification and on-site delivery apply at every level.' },
  };

  const lang = () => (document.documentElement.lang === 'en' ? 'en' : 'tr');
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const nm = (n) => esc(lang() === 'en' ? n.en : n.tr);
  const ds = (n) => esc(lang() === 'en' ? n.d_en : n.d_tr);

  // --- deterministik teknik-resim motifi ---------------------------------
  function hash(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  let GRID = '';
  for (let x = 20; x < 400; x += 20) GRID += `<path d="M${x} 0v300"/>`;
  for (let y = 20; y < 300; y += 20) GRID += `<path d="M0 ${y}h400"/>`;

  const MOTIFS = [
    // flanş / rulman kesiti
    `<circle r="70"/><circle r="46"/><circle r="17"/>
     <circle cx="0" cy="-58" r="5"/><circle cx="50" cy="-29" r="5"/><circle cx="50" cy="29" r="5"/>
     <circle cx="0" cy="58" r="5"/><circle cx="-50" cy="29" r="5"/><circle cx="-50" cy="-29" r="5"/>`,
    // altıgen somun
    `<path d="M0-72 62-36v72L0 72-62 36v-72z"/><path d="M0-44 38-22v44L0 44-38 22v-44z"/><circle r="20"/>`,
    // dişli çark
    `<circle r="52"/><circle r="20"/>
     <path d="M0-52v-18M37-37l13-13M52 0h18M37 37l13 13M0 52v18M-37 37l-13 13M-52 0h-18M-37-37l-13-13"/>`,
    // silindir / makara
    `<path d="M-58-52h116v104h-116z"/><ellipse cx="-58" cy="0" rx="15" ry="52"/>
     <ellipse cx="58" cy="0" rx="15" ry="52"/><path d="M-20-52v104M20-52v104"/>`,
    // yay / bobin
    `<path d="M-66-34c22-26 44 26 66 0s44 26 66 0"/><path d="M-66 0c22-26 44 26 66 0s44 26 66 0"/>
     <path d="M-66 34c22-26 44 26 66 0s44 26 66 0"/>`,
    // dirsek boru
    `<path d="M-70 46h44a50 50 0 0 0 50-50v-42"/><path d="M-70 12h44a16 16 0 0 1 16 16v42"/>
     <path d="M-70 58v-24M24-46h-38M24-46h38"/>`,
    // plaka istifi
    `<path d="M-64-40h108v26h-108z"/><path d="M-52-8h108v26h-108z"/><path d="M-40 24h108v26h-108z"/>`,
    // delik paftası
    `<path d="M-64-52h128v104h-128z"/>
     <circle cx="-34" cy="-24" r="8"/><circle cx="0" cy="-24" r="8"/><circle cx="34" cy="-24" r="8"/>
     <circle cx="-34" cy="14" r="8"/><circle cx="0" cy="14" r="8"/><circle cx="34" cy="14" r="8"/>`,
    // vana gövdesi
    `<path d="M-70 0h140"/><path d="M-26-34h52v68h-52z"/><circle r="16"/>
     <path d="M0-34v-30"/><path d="M-30-64h60"/>`,
    // kesici uç / matkap
    `<path d="M-14-70h28v96l-14 44-14-44z"/><path d="M-14-40h28M-14-12h28M-14 16h28"/>`,
  ];

  // Motif once ada gore anlamli secilir; eslesme yoksa kimlikten turetilir.
  // MOTIFS sirasi: 0 flans/rulman, 1 altigen, 2 disli, 3 silindir, 4 yay,
  // 5 dirsek boru, 6 plaka istifi, 7 delik paftasi, 8 vana, 9 kesici uc.
  const KEYS = [
    [/bearing|rulman|flange|flans|pulley|kasnak|wheel|disc|disk|roller|makara/i, 0],
    [/fastener|bolt|nut|screw|civata|somun|vida|thread|dis-|anchor|dubel|rivet|percin/i, 1],
    [/gear|disli|motor|drive|transmission|aktar|reduk|sprocket|zincir|chain/i, 2],
    [/cylinder|silindir|drum|varil|tank|vessel|roll|rulo|pump|pompa|compressor|kompresor/i, 3],
    [/spring|yay|hose|hortum|cable|kablo|wire|tel|belt|kayis|coil|bobin|rope|halat/i, 4],
    [/pipe|boru|fitting|rakor|tube|elbow|dirsek|plumb|tesisat|duct|kanal|drain|gider/i, 5],
    [/sheet|sac\b|plate|levha|panel|board|insul|yalitim|packag|ambalaj|shelv|raf\b/i, 6],
    [/filter|filtre|mesh|elek|abrasive|zimpara|clean|temizlik|electr|elektr|sensor|test|olcum/i, 7],
    [/valve|vana|valf|\btap\b|musluk|regulat|pneumat|pnomatik|hydraul|hidrolik|air\b|hava|gas\b|gaz/i, 8],
    [/tool|alet|takim|drill|matkap|cut|kesic|weld|kaynak|mill|freze|blade|bicak|safety|guvenlik/i, 9],
  ];
  function semanticMotif(node) {
    const hay = node.en + ' ' + node.tr + ' ' + node.id;
    for (const [re, idx] of KEYS) if (re.test(hay)) return idx;
    return hash(node.id) % MOTIFS.length;
  }

  // Kardes kutucuklarin hepsi ayni kelimeyi tasiyabilir ("... Motorlar"), bu da
  // ayni motifi verir. Anlamli eslesme ilk kullanana kalir, sonrakiler kaydirilir.
  function assignMotifs(list) {
    const used = new Set();
    return list.map((n) => {
      const want = semanticMotif(n);
      let m = want;
      for (let k = 0; k < MOTIFS.length && used.has(m); k++) m = (want + 1 + k) % MOTIFS.length;
      used.add(m);
      return m;
    });
  }

  function plate(node, motifIdx) {
    if (node.img) {
      return `<img src="${node.img}" alt="" loading="lazy" decoding="async">`;
    }
    const h = hash(node.id);
    const motif = MOTIFS[motifIdx];
    const rot = ((h >>> 7) % 24) * 15;
    const scale = (0.82 + (((h >>> 13) % 5) * 0.09)).toFixed(2);
    const tick = 60 + ((h >>> 17) % 5) * 45;          // kot cizgisinin yeri
    return `<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="400" height="300" fill="#0D100A"/>
      <g stroke="#93A24F" stroke-opacity=".09" stroke-width="1">${GRID}</g>
      <g stroke="#93A24F" stroke-opacity=".22" stroke-width="1" fill="none">
        <path d="M${tick} 264h${400 - tick - 40}"/>
        <path d="M${tick} 258v12M${360} 258v12"/>
      </g>
      <g transform="translate(200 144) rotate(${rot}) scale(${scale})" fill="none" stroke="#93A24F"
         stroke-opacity=".62" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">${motif}</g>
      <g stroke="#93A24F" stroke-opacity=".32" stroke-width="1.5" fill="none">
        <path d="M14 14h20M14 14v20M386 286h-20M386 286v-20"/>
      </g>
    </svg>`;
  }

  // --- durum -------------------------------------------------------------
  let trail = [];                       // seçili düğümler, en fazla 2 derinlik
  const codeOf = (i, depth) => (depth === 0 ? 'KG' : depth === 1 ? 'AG' : 'UA') + '-' + String(i + 1).padStart(2, '0');

  function current() {
    return trail.length ? trail[trail.length - 1].kids : CATALOG;
  }

  function leafLabel(n) {
    const t = T[lang()];
    if (!n.kids || !n.kids.length) return t.ask + ' →';
    const depth = trail.length;                    // bu düğüm hangi kademede
    const word = depth === 0 ? t.sub : t.fam;
    return n.kids.length + ' ' + word + ' →';
  }

  function render(animate) {
    const t = T[lang()];
    const list = current();
    const depth = trail.length;

    // yol
    let crumbs = `<button type="button" class="cat-crumb tag" data-go="-1"${depth === 0 ? ' aria-current="page"' : ''}>${t.root}</button>`;
    trail.forEach((n, i) => {
      const last = i === trail.length - 1;
      crumbs += `<span class="cat-sep tag" aria-hidden="true">/</span>`;
      crumbs += `<button type="button" class="cat-crumb tag" data-go="${i}"${last ? ' aria-current="page"' : ''}>${nm(n)}</button>`;
    });
    pathEl.innerHTML = crumbs;

    // kademe göstergesi
    rungEl.innerHTML = [0, 1, 2].map((i) => `<span class="cat-rung${i <= depth ? ' on' : ''}"></span>`).join('') +
      `<span class="tag ml-2 text-mute">${t.level} 0${depth + 1}/03</span>`;

    backEl.hidden = depth === 0;
    backEl.textContent = '← ' + t.back;

    headEl.textContent = depth === 0 ? (lang() === 'en' ? 'Product groups' : 'Ürün grupları') : nm(trail[trail.length - 1]);
    countEl.textContent = list.length + ' ' + (depth === 0 ? t.groups : depth === 1 ? t.sub : t.fam);

    const leaf = depth === 2;
    const motifs = assignMotifs(list);
    gridEl.innerHTML = list.map((n, i) => {
      const tag = leaf ? 'a' : 'button';
      const attr = leaf ? 'href="#iletisim"' : 'type="button"';
      return `<${tag} ${attr} class="cat-tile" data-i="${i}">
        <span class="cat-img">
          ${plate(n, motifs[i])}
          <span class="cat-wash"></span>
          <span class="cat-shade"></span>
        </span>
        <span class="cat-body">
          <span class="tag block text-olivelo">${codeOf(i, depth)}</span>
          <span class="disp-s mt-2 block text-[.8125rem] leading-[1.35] text-chalk">${nm(n)}</span>
          <span class="tag cat-more mt-3 block">${leafLabel(n)}</span>
        </span>
        <!-- Açıklama .cat-img'in dışında: imleçli cihazda görselin üstüne binen panel,
             dokunmatikte ise kutucuğun içinde sabit metin olarak akıyor.
             Sarmalayıcı, kapalı hâldeki panelin gövdenin üstüne taşmasını kırpar. -->
        <span class="cat-deskap"><span class="cat-desc"><span class="lede text-[.8125rem] font-medium">${ds(n)}</span></span></span>
      </${tag}>`;
    }).join('');

    if (animate) {
      gridEl.classList.add('out');
      requestAnimationFrame(() => requestAnimationFrame(() => gridEl.classList.remove('out')));
    }
  }

  // --- olaylar -----------------------------------------------------------
  gridEl.addEventListener('click', (e) => {
    const tile = e.target.closest('.cat-tile');
    if (!tile || tile.tagName === 'A') return;      // yaprak: normal bağlantı
    const node = current()[Number(tile.dataset.i)];
    if (!node || !node.kids || !node.kids.length || trail.length >= 2) return;
    trail.push(node);
    render(true);
    root.scrollIntoView({ block: 'start', behavior: 'smooth' });
  });

  pathEl.addEventListener('click', (e) => {
    const b = e.target.closest('[data-go]');
    if (!b || b.hasAttribute('aria-current')) return;
    trail = trail.slice(0, Number(b.dataset.go) + 1);
    render(true);
  });

  backEl.addEventListener('click', () => { trail.pop(); render(true); });

  window.addEventListener('langchange', () => render(false));

  render(false);
})();

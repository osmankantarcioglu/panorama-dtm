# -*- coding: utf-8 -*-
"""
ALT KATEGORI GORSELLERI
-----------------------
Tedarikci alt kategori sayfalarindaki kutucuklari ayirir ve katalogun 2. / 3.
kademe dugumlerine baglar. Izgara geometrisi otomatik bulunur; elle girilen tek
sey EŞLEŞME tablosu, yani "sayfadaki kacinci kutucuk hangi dugume gider".

Kullanim:
    python gorsel-ayir-alt.py          -> tum sayfalari isler
    python gorsel-ayir-alt.py 22 23    -> sadece verilen sayfalari isler
    node katalog-derle.mjs             -> ardindan bunu calistirin

Cikti: v3-saha/urun-gorselleri/<dugum-kimligi>.webp

Bir kutucuk birden fazla dugume gidebilir (ust grup + ayni adi tasiyan alt grup).
Bos liste, o kutucugun bizim katalogda karsiligi olmadigi anlamina gelir; ilgili
dugum teknik-resim motifinde kalir.
"""
import os, sys
from PIL import Image
from gorsel_plaka import lum, urun_kutusu, kart, kontak_sayfasi

ROOT = os.path.dirname(os.path.abspath(__file__))
KAYNAK = os.path.join(ROOT, "brand_assets", "kaynak-izgaralar")
OUT = os.path.join(ROOT, "v3-saha", "urun-gorselleri")
KONTAK = os.path.join(ROOT, "temporary screenshots")

# --- eslesme tablosu ---------------------------------------------------------
# (dosya, [satir][kutucuk] -> katalog kimlikleri).  Kutucuk sirasi soldan saga.
SAYFALAR = [
    ("17-abrasives.png", [
        # Sanding / Cut-Off & Grinding / Brushes / Blasting / Deburring / Sharpening
        [[], ["cutting-grinding-wheels"], ["surface-conditioning"], ["blasting-media"],
         ["mounted-points-files"], []],
        # Buffing & Polishing / Vibratory Tumbling / Abrasive Accessories
        [["polishing-buffing"], [], ["abrasive-power-tools"]],
    ]),
    ("22-sanding-abrasives.png", [
        # Discs / Belts / Hand Pads / Sheets / Rolls / Flap Wheels
        [["abrasive-discs", "hook-loop-discs"], ["abrasive-belts", "portable-sander-belts"],
         ["sanding-sponges"], ["coated-abrasives", "sandpaper-sheets"],
         ["abrasive-rolls"], ["flap-discs", "flap-wheels"]],
        # Surface-Conditioning Wheels / Cartridge Rolls / Spiral Bands / Specialty / Cord
        [["non-woven-discs"], [], ["sanding-sleeves"], [], []],
    ]),
    ("23-cutoff-grinding.png", [
        # Cut-Off / Grinding / Combination / Cones & Plugs / Rubbing Bricks / Segments
        [["cut-off-wheels"], ["grinding-wheels"], ["chop-saw-wheels"], [],
         ["belt-cleaning-sticks"], []],
        # Dressing & Truing Tools
        [["wheel-accessories"]],
    ]),
    ("24-abrasive-brushes.png", [
        # Wire Wheel / Cup / End / Kits / Disc / Power Tube
        [["wheel-brushes"], ["cup-brushes"], ["end-brushes"], ["hand-brushes"],
         ["stripping-wheels"], []],
        # Honing Brushes
        [[]],
    ]),
    ("25-abrasive-blasting.png", [
        # Media / Cabinets / Cabinet Parts / Portable Blasters / Guns & Nozzles / Dust Collectors
        [["steel-grit-shot"], ["blast-cabinets-pots"], [], [], ["blast-nozzles-hoses"],
         ["dust-extraction-abrasive"]],
        # Blasting Hoods
        [[]],
    ]),
    ("26-deburring.png", [
        # Carbide Burs / Mounted Points & Kits / Hand Deburring Tools
        [["carbide-burrs"], ["mounted-points"], ["deburring-tools"]],
    ]),
    ("27-sharpening.png", [
        # Sharpening Stones / Abrasive Sharpening Files / Machines / Hand Tools
        [[], ["hand-files"], [], []],
    ]),
    ("18-buffing-polishing.png", [
        # Buffing Wheels / Compounds / Kits / Lapping Compounds / Diamond Pads / Felt Bobs
        [["buffing-wheels"], ["polishing-compounds"], ["polishing-accessories"],
         ["lapping-compounds"], ["foam-pads"], ["felt-bobs"]],
    ]),
    ("19-vibratory-tumbling.png", [
        # Tumbling Media / Compounds / Tumblers / Bowls & Lids / Spares / Screens
        [["aluminium-oxide-media"], [], [], [], [], []],
    ]),
    ("20-abrasive-accessories.png", [
        # Backing Pads / Mandrels & Arbors / Expanding Drums / Sanding Blocks
        [["backing-pads"], ["quick-change-discs"], ["drums-mandrels"], []],
    ]),
]


# --- izgara geometrisi -------------------------------------------------------
def yatay_cizgiler(px, W, H):
    """Tablo ayrac cizgileri: satirin yarisindan fazlasi ayni acik gri tonda."""
    ys = [y for y in range(H) if sum(1 for x in range(W) if 195 <= lum(px[x, y]) <= 247) > W * 0.5]
    kume, son = [], -9
    for y in ys:                                   # bitisik pikselleri tek cizgide topla
        if y - son > 3:
            kume.append(y)
        son = y
    return kume


def dikey_cizgiler(px, W, y0, y1):
    """Bir satir bandindaki hucre ayraclari."""
    yuk = y1 - y0
    xs = [x for x in range(W)
          if sum(1 for y in range(y0, y1) if 195 <= lum(px[x, y]) <= 247) > yuk * 0.8]
    kume, son = [], -9
    for x in xs:
        if x - son > 3:
            kume.append(x)
        son = x
    # ekran goruntusunun kendi kenari da duz gri bir sutun olabilir; hucre
    # genisliginin yarisindan dar kalan uc araliklari at
    while len(kume) > 2:
        ara = [kume[i + 1] - kume[i] for i in range(len(kume) - 1)]
        orta = sorted(ara)[len(ara) // 2]
        if ara[0] < orta * 0.5:
            kume.pop(0)
        elif ara[-1] < orta * 0.5:
            kume.pop()
        else:
            break
    return kume


def sayfa_hucreleri(im):
    """[(x0, y0, x1, y1), ...] listesini satir satir dondurur."""
    W, H = im.size
    px = im.load()
    ç = yatay_cizgiler(px, W, H)
    if len(ç) < 2:
        raise SystemExit("tablo bulunamadi")
    ust, yuk = ç[0], ç[1] - ç[0]
    satirlar = []
    k = 0
    while ust + (k + 1) * yuk <= H + 6:             # son satirin alt kenari eksik olabilir
        y0, y1 = ust + k * yuk, min(H, ust + (k + 1) * yuk)
        ayrac = dikey_cizgiler(px, W, y0 + 4, y1 - 4)
        if len(ayrac) >= 2:
            satirlar.append([(ayrac[i] + 3, y0 + 3, ayrac[i + 1] - 2, y1 - 2)
                             for i in range(len(ayrac) - 1)])
        k += 1
    return satirlar


# --- isle --------------------------------------------------------------------
istenen = set(sys.argv[1:])
os.makedirs(OUT, exist_ok=True)
toplam, uyari = 0, []

for dosya, eslesme in SAYFALAR:
    if istenen and dosya.split("-")[0] not in istenen:
        continue
    im = Image.open(os.path.join(KAYNAK, dosya)).convert("RGB")
    px = im.load()
    satirlar = sayfa_hucreleri(im)

    bulunan = [len(s) for s in satirlar]
    beklenen = [len(s) for s in eslesme]
    if bulunan != beklenen:
        uyari.append(f"{dosya}: izgara {bulunan}, tablo {beklenen} -- ATLANDI")
        continue

    kartlar = []
    for satir, hucreler in zip(eslesme, satirlar):
        for kimlikler, (x0, y0, x1, y1) in zip(satir, hucreler):
            kutu = urun_kutusu(px, x0, y0, x1, y1)
            if not kutu:
                uyari.append(f"{dosya}: bos hucre {x0},{y0}")
                continue
            if not kimlikler:
                continue
            card = kart(im, kutu, sinir=(x0, y0, x1, y1))
            for kimlik in kimlikler:
                card.save(os.path.join(OUT, kimlik + ".webp"), quality=88, method=6)
                toplam += 1
            kartlar.append(("+".join(kimlikler), card))
    kontak_sayfasi(kartlar, os.path.join(KONTAK, "kontak-" + dosya))
    print(f"{dosya:<32} {sum(bulunan):>2} kutucuk -> {len(kartlar)} eslesme")

print(f"\ntoplam {toplam} dosya yazildi")
for u in uyari:
    print("  uyari:", u)

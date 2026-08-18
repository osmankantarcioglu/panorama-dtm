# -*- coding: utf-8 -*-
"""
ANA KATEGORI GORSELLERI
-----------------------
Tedarikcinin ana kategori izgarasini (7 sutun x 5 satir tablo) hucrelere ayirir,
her urun fotografini beyaz zeminden koparir ve sitenin teknik-resim plakasina
oturtur. Plaka motoru gorsel_plaka.py icinde.

Kullanim:
    python gorsel-ayir.py [izgara.png]      (varsayilan: brand_assets/kaynak-izgaralar/00-ana-kategoriler.png)
    node katalog-derle.mjs                  (ardindan)

Cikti: v3-saha/urun-gorselleri/<kategori-kimligi>.webp
       temporary screenshots/kontak-ana-kategoriler.png  (kontrol icin)

Alt kademeler icin: gorsel-ayir-alt.py
"""
import os, sys
from PIL import Image
from gorsel_plaka import urun_kutusu, kart, kontak_sayfasi

ROOT = os.path.dirname(os.path.abspath(__file__))
VARSAYILAN = os.path.join(ROOT, "brand_assets", "kaynak-izgaralar", "00-ana-kategoriler.png")
SRC = sys.argv[1] if len(sys.argv) > 1 else VARSAYILAN
OUT = os.path.join(ROOT, "v3-saha", "urun-gorselleri")
SHEET = os.path.join(ROOT, "temporary screenshots", "kontak-ana-kategoriler.png")

# Izgara ayrac cizgileri. Baska bir izgara icin: bir satir/sutunda koyu piksel
# orani %60'i asan konumlar ayractir (bkz. gorsel-ayir-alt.py otomatik bulur).
COLS = [12, 169, 326, 483, 641, 798, 955, 1112]
ROWS = [12, 182, 353, 510, 680, 851]

# hucre sirasina gore katalog kimlikleri; None = bizde karsiligi yok
IDS = [
    "abrasives", "adhesives-sealants-tape", "cleaning-janitorial", "electrical",
    "electronics-batteries", "fasteners", "fleet-vehicle-maintenance",
    "food-service-processing", "furnishings-hospitality-building", "hvac-and-refrigeration",
    "hardware", "hydraulics", None, "lighting",                       # None = Lab Supplies
    "lubrication", "machining", "material-handling", "motors",
    None, "outdoor-equipment", "packaging-shipping",                  # None = Office Supplies
    "paints-equipment-supplies", "pipe-hose-tube-fittings", "plumbing", "pneumatics",
    "bearings", "pumps", "raw-materials",   # Grainger "Power Transmission" karesi bir rulman;
                                            # bizde ayri "Rulmanlar" grubu var, oraya gidiyor
    None, "safety", "security", "test-instruments", "tools", "welding",  # None = Retail Supplies
]

im = Image.open(SRC).convert("RGB")
px = im.load()
os.makedirs(OUT, exist_ok=True)

kartlar, yazildi, atlandi = [], [], []
for r in range(len(ROWS) - 1):
    for c in range(len(COLS) - 1):
        i = r * (len(COLS) - 1) + c
        if i >= len(IDS):
            continue
        x0, y0 = COLS[c] + 2, ROWS[r] + 2
        x1, y1 = COLS[c + 1] - 1, ROWS[r + 1] - 1
        kutu = urun_kutusu(px, x0, y0, x1, y1)
        if not kutu:
            continue                                   # bos hucre
        card = kart(im, kutu, sinir=(x0, y0, x1, y1))
        kartlar.append((IDS[i] or f"[{r+1}-{c+1}]", card))
        if IDS[i]:
            card.save(os.path.join(OUT, IDS[i] + ".webp"), quality=88, method=6)
            yazildi.append(IDS[i])
        else:
            atlandi.append(f"satir{r+1}-sutun{c+1}")

kontak_sayfasi(kartlar, SHEET)
print(f"yazildi: {len(yazildi)}")
print(f"karsiligi yok, atlandi: {atlandi}")
print(f"kontak sayfasi: {SHEET}")

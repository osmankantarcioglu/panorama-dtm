# -*- coding: utf-8 -*-
"""
GORSEL ICE ALMA
---------------
Eslesme dosyasindaki her kayit icin urun fotografini alir (yerel dosya veya URL),
beyaz zeminden koparir ve teknik-resim plakasina oturtup katalog kimligiyle
kaydeder. gorsel-ayir*.py ekran goruntusu kirpar; bu ise hazir urun fotografini
isler.

Girdi: katalog-esle.py ciktisi ya da ayni bicimde elle yazilmis JSON
    {"eslesme": [{"kimlik": "cup-brushes", "gorsel": "https://... veya C:\\yol\\a.jpg",
                  "ad": "Cup Brushes", "yol": "abrasives/..."}]}

Kullanim:
    python gorsel-ic-al.py eslesme.json
    python gorsel-ic-al.py eslesme.json --uzerine    mevcut gorseli de degistir
    node katalog-derle.mjs                           ardindan

Kaynak kaydi v3-saha/urun-gorselleri/KAYNAK.json dosyasina yazilir.
"""
import json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from PIL import Image
from gorsel_plaka import lum, kart, kontak_sayfasi

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "v3-saha" / "urun-gorselleri"
ONBELLEK = ROOT / "brand_assets" / "indirilen-gorseller"
KAYIT = OUT / "KAYNAK.json"
KONTAK = ROOT / "temporary screenshots"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SAKLA = "--sakla" in sys.argv          # indirilen aslini diskte tut


def getir(kaynak, kimlik):
    """URL ise indirir, yerel dosya ise acar. Asillari varsayilan olarak saklamaz;
    binlerce dugumde yuzlerce MB tutmasin diye."""
    if not kaynak:
        return None
    if kaynak.startswith(("http://", "https://")):
        req = urllib.request.Request(kaynak, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            veri = r.read()
        if len(veri) < 1200:
            return None
        if SAKLA:
            ONBELLEK.mkdir(parents=True, exist_ok=True)
            (ONBELLEK / (kimlik + ".jpg")).write_bytes(veri)
        return kucult(Image.open(BytesIO(veri)).convert("RGB"))
    p = Path(kaynak)
    return kucult(Image.open(p).convert("RGB")) if p.exists() else None


def kucult(im, en_uzun=560):
    """Plakada urun en fazla 540x330 yer kapliyor; daha buyugunu tasimanin
    anlami yok. Koparmadaki MaxFilter piksel sayisiyla dogru orantili
    pahalilastigi icin bu, gorsel basina maliyeti belirgin dusuruyor."""
    k = max(im.size)
    if k <= en_uzun:
        return im
    o = en_uzun / k
    return im.resize((max(1, int(im.width * o)), max(1, int(im.height * o))), Image.LANCZOS)


def urun_sinirlari(im, esik=246):
    """Beyaz kenar bosluklarini atip urunun kutusunu bulur."""
    w, h = im.size
    px = im.load()
    xs = [x for x in range(w) if any(lum(px[x, y]) < esik for y in range(h))]
    ys = [y for y in range(h) if any(lum(px[x, y]) < esik for x in range(w))]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    veri = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    kayitlar = veri["eslesme"] if isinstance(veri, dict) else veri
    uzerine = "--uzerine" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)

    kaynak_kaydi = json.loads(KAYIT.read_text(encoding="utf8")) if KAYIT.exists() else {}
    kartlar, yazildi, atlanan, hatali = [], 0, 0, []

    is_listesi = []
    for k in kayitlar:
        kimlik = k.get("kimlik")
        if not kimlik or not k.get("gorsel"):
            continue
        if (OUT / (kimlik + ".webp")).exists() and not uzerine:
            atlanan += 1
            continue
        is_listesi.append(k)

    # Indirme ve plaka uretimi birlikte is parcaciklarina dagitiliyor: plaka
    # uretimi gorsel basina yarim saniye ve PIL bu islerde GIL'i biraktigi icin
    # ana dongude seri calistirmak butun isi kilitliyordu.
    def isle(k):
        try:
            im = getir(k["gorsel"], k["kimlik"])
            if im is None:
                return k, None, "gorsel alinamadi"
            kutu = urun_sinirlari(im)
            if not kutu:
                return k, None, "bos gorsel"
            return k, kart(im, kutu, kenar=4, sinir=(0, 0, im.width, im.height)), None
        except Exception as e:
            return k, None, str(e)[:60]

    isci = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--isci=")), 12))
    with ThreadPoolExecutor(max_workers=isci) as havuz:
        for n, (k, card, hata) in enumerate(havuz.map(isle, is_listesi), 1):
            kimlik = k["kimlik"]
            if hata or card is None:
                hatali.append(f'{kimlik}: {hata or "gorsel alinamadi"}')
                continue
            card.save(OUT / (kimlik + ".webp"), quality=88, method=4)
            kaynak_kaydi[kimlik] = {"ad": k.get("ad", ""), "yol": k.get("yol", ""),
                                    "gorsel": k.get("gorsel", "")}
            if len(kartlar) < 120:
                kartlar.append((kimlik, card))
            yazildi += 1
            if n % 250 == 0:
                print(f"  {n}/{len(is_listesi)} ...", flush=True)

    KAYIT.write_text(json.dumps(kaynak_kaydi, ensure_ascii=False, indent=1), encoding="utf8")
    if kartlar:
        KONTAK.mkdir(parents=True, exist_ok=True)
        kontak_sayfasi(kartlar[:120], str(KONTAK / "kontak-ice-alinan.png"), sutun=7, kw=210, kh=158)

    print(f"yazildi {yazildi}, mevcut oldugu icin atlandi {atlanan}, hata {len(hatali)}")
    for h in hatali[:15]:
        print("  ", h)
    return 0


if __name__ == "__main__":
    sys.exit(main())

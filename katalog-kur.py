# -*- coding: utf-8 -*-
"""
KATALOG KURMA
-------------
Tedarikci agacindan (gorsel-topla tarayicisinin ciktisi) katalogu bastan kurar.
Eslestirme yok: kategoriler, adlar, aciklamalar ve gorseller kaynakta ne ise o.

Kullanim:
    python katalog-kur.py brand_assets/toplanan/grainger-agac-tam.json
    python gorsel-ic-al.py brand_assets/toplanan/gorsel-listesi.json
    node katalog-derle.mjs

Uretir:
    v3-saha/katalog/catalog.json          uc kademeli katalog
    brand_assets/toplanan/gorsel-listesi.json   indirilecek gorseller

Kimlikler yol son parcasindan turetilir; cakisirsa ust parca eklenir. Derleyici
gorsel dosyalarini kimlige gore esledigi icin kimliklerin tekil olmasi sart.

Not: tr alanlari su an ingilizce metnin aynisi. Turkce ceviri ayri bir adim.
"""
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CIKTI = ROOT / "v3-saha" / "katalog" / "catalog.json"
GORSEL = ROOT / "brand_assets" / "toplanan" / "gorsel-listesi.json"
# Plakada urun en fazla 540 piksel yer kapliyor; 700 yeterli ve Scene7'nin
# buyuk rendition uretmesi belirgin sekilde yavas.
CDN = "https://static.grainger.com/rp/s/is/image/Grainger/{}?wid=700&hei=700"


def slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def kur(veri):
    sayfa = veri["sayfalar"]
    kok = veri["kok"]

    kullanilan = set()

    def kimlik_uret(yol):
        parca = yol.split("/")
        for n in range(1, len(parca) + 1):          # once son parca, cakisirsa geriye dogru genislet
            aday = slug("-".join(parca[-n:]))
            if aday and aday not in kullanilan:
                kullanilan.add(aday)
                return aday
        aday = slug(yol)
        kullanilan.add(aday)
        return aday

    gorseller = []

    def dugum(kutu, derinlik):
        yol = kutu["yol"]
        s = sayfa.get(yol, {})
        kimlik = kimlik_uret(yol)
        ad = s.get("ad") or kutu.get("ad") or yol.rsplit("/", 1)[-1].replace("-", " ").title()
        aciklama = (s.get("aciklama") or "").strip()
        if kutu.get("g"):
            gorseller.append({"kimlik": kimlik, "ad": ad, "yol": yol,
                              "gorsel": CDN.format(kutu["g"])})
        kids = []
        if derinlik < 3:
            for alt in s.get("kutular", []):
                kids.append(dugum(alt, derinlik + 1))
        return {"id": kimlik, "tr": ad, "en": ad,
                "d_tr": aciklama, "d_en": aciklama, "kids": kids}

    return [dugum(k, 1) for k in kok], gorseller


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    veri = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    katalog, gorseller = kur(veri)

    l1 = len(katalog)
    l2 = sum(len(a["kids"]) for a in katalog)
    l3 = sum(len(b["kids"]) for a in katalog for b in a["kids"])
    aciklamali = 0
    yigin = list(katalog)
    toplam = 0
    while yigin:
        n = yigin.pop()
        toplam += 1
        if n["d_en"]:
            aciklamali += 1
        yigin.extend(n["kids"])

    CIKTI.write_text(json.dumps(katalog, ensure_ascii=False, indent=1), encoding="utf8")
    GORSEL.parent.mkdir(parents=True, exist_ok=True)
    GORSEL.write_text(json.dumps({"eslesme": gorseller}, ensure_ascii=False, indent=1), encoding="utf8")

    print(f"katalog: {l1} ana grup / {l2} alt grup / {l3} urun ailesi  (toplam {toplam})")
    print(f"aciklamasi olan dugum: {aciklamali}/{toplam}")
    print(f"gorsel listesi: {len(gorseller)} kayit -> {GORSEL.name}")
    print(f"yazildi: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

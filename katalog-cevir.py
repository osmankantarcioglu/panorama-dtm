# -*- coding: utf-8 -*-
"""
KATALOG CEVIRI
--------------
Ceviri dosyalarini catalog.json uzerine isler. Ceviri dosyasi kimlikten
Turkce karsiliga esleyen duz bir sozluk:

    { "welding-wire": { "tr": "Kaynak Teli", "d_tr": "..." }, ... }

d_tr istege bagli; verilmezse mevcut deger korunur. Boylece adlar ve
aciklamalar ayri turlarda islenebilir.

Kullanim:
    python katalog-cevir.py                     ceviri/ altindaki tum dosyalari isler
    python katalog-cevir.py ceviri/adlar-01.json
    python katalog-cevir.py --durum             ne kadari cevrildi, listeler
    python katalog-cevir.py --kalan > kalan.txt eksik dugumleri kimlik<TAB>ingilizce olarak dokur
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KATALOG = ROOT / "v3-saha" / "katalog" / "catalog.json"
CEVIRI = ROOT / "brand_assets" / "ceviri"


def gez(ns):
    for n in ns:
        yield n
        yield from gez(n.get("kids", []))


def yukle():
    return json.loads(KATALOG.read_text(encoding="utf8"))


def ingilizce_mi(n):
    """tr alani hala ingilizce metnin aynisi mi?"""
    return n["tr"].strip() == n["en"].strip()


KISALTMA = ("Inc.", "Ltd.", "No.", "Nos.", "e.g.", "i.e.", "vs.", "U.S.", "Dr.", "in.", "ft.", "oz.")


def ilk_cumle(metin, azami=240):
    """Aciklamanin tanim cumlesini dondurur.

    Kutucugun uzerine gelince acilan panel yaklasik 240 karakter aliyor; daha
    uzun metin kirpiliyor. Tedarikci aciklamalarinda ilk cumle her zaman tanim,
    gerisi ayrinti -- o yuzden ilk cumleyle yetiniyoruz.
    """
    metin = " ".join(str(metin or "").split())
    i, n = 0, len(metin)
    while i < n:
        j = metin.find(". ", i)
        if j == -1:
            break
        parca = metin[:j + 1]
        if not any(parca.endswith(k) for k in KISALTMA) and metin[j + 2:j + 3].isupper():
            return parca if len(parca) <= azami else parca[:azami].rsplit(" ", 1)[0] + "…"
        i = j + 2
    if len(metin) <= azami:
        return metin
    return metin[:azami].rsplit(" ", 1)[0] + "…"


def durum(kat):
    dugum = list(gez(kat))
    ad_kalan = [n for n in dugum if ingilizce_mi(n)]
    acik_var = [n for n in dugum if n["d_en"].strip()]
    acik_kalan = [n for n in acik_var if n["d_tr"].strip() == n["d_en"].strip()]
    return dugum, ad_kalan, acik_var, acik_kalan


def main():
    kat = yukle()
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--durum" in sys.argv:
        dugum, ad_kalan, acik_var, acik_kalan = durum(kat)
        print(f"dugum         : {len(dugum)}")
        print(f"ad cevrildi   : {len(dugum)-len(ad_kalan)}/{len(dugum)}")
        print(f"aciklamasi olan: {len(acik_var)}")
        print(f"aciklama cevrildi: {len(acik_var)-len(acik_kalan)}/{len(acik_var)}")
        return 0

    if "--kalan" in sys.argv:
        _, ad_kalan, _, acik_kalan = durum(kat)
        hedef = acik_kalan if "--aciklama" in sys.argv else ad_kalan
        alan = "d_en" if "--aciklama" in sys.argv else "en"
        kisa = "--kisa" in sys.argv
        for n in hedef:
            metin = ilk_cumle(n[alan]) if kisa else n[alan]
            print(f'{n["id"]}\t{metin}')
        return 0

    dosyalar = [Path(a) for a in argv] if argv else sorted(CEVIRI.glob("*.json"))
    if not dosyalar:
        print(f"ceviri dosyasi yok: {CEVIRI}")
        return 1

    # Ayni kimlik hem ad hem aciklama dosyasinda gecebilir; dict.update tum
    # degeri degistirdigi icin alan bazinda birlestiriyoruz.
    sozluk = {}
    for d in dosyalar:
        for kimlik, v in json.loads(d.read_text(encoding="utf8")).items():
            sozluk.setdefault(kimlik, {}).update(v)

    dizin = {n["id"]: n for n in gez(kat)}
    ad, acik, bilinmeyen = 0, 0, []
    for kimlik, v in sozluk.items():
        n = dizin.get(kimlik)
        if not n:
            bilinmeyen.append(kimlik)
            continue
        if v.get("tr"):
            n["tr"] = v["tr"].strip(); ad += 1
        if v.get("d_tr"):
            n["d_tr"] = v["d_tr"].strip(); acik += 1

    KATALOG.write_text(json.dumps(kat, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"{len(dosyalar)} dosya -> ad {ad}, aciklama {acik} guncellendi")
    if bilinmeyen:
        print(f"katalogda olmayan kimlik ({len(bilinmeyen)}): {bilinmeyen[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

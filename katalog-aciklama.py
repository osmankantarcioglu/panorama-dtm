# -*- coding: utf-8 -*-
"""
KATALOG ACIKLAMALARI
--------------------
Tedarikci sayfalarindan toplanan aciklamalari catalog.json'a isler. Aciklama
kutucukta degil, kategorinin kendi sayfasinda durdugu icin ayri bir taramayla
toplaniyor; bu betik yol -> kimlik eslesmesini kurup d_en/d_tr alanlarini
dolduruyor.

Girdi: { "welding/filler-metals": { "u": "1,495", "a": "Filler metals melt..." } }

Kullanim:
    python katalog-aciklama.py brand_assets/toplanan/grainger-aciklamalar.json
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KATALOG = ROOT / "v3-saha" / "katalog" / "catalog.json"
AGAC = ROOT / "brand_assets" / "toplanan" / "grainger-agac-tam.json"


def gez(ns):
    for n in ns:
        yield n
        yield from gez(n.get("kids", []))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    veri = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
    kat = json.loads(KATALOG.read_text(encoding="utf8"))
    agac = json.loads(AGAC.read_text(encoding="utf8"))

    # katalog-kur.py kimlikleri ayni sirayla uretiyor; yol->kimlik esini
    # agactan yeniden kurmak yerine kaynak listesinden okuyoruz
    kaynak = json.loads((ROOT / "brand_assets" / "toplanan" / "gorsel-listesi.json")
                        .read_text(encoding="utf8"))["eslesme"]
    yol2kimlik = {k["yol"]: k["kimlik"] for k in kaynak}

    dizin = {n["id"]: n for n in gez(kat)}
    yazildi, bos, eksik = 0, 0, 0
    for yol, v in veri.items():
        kimlik = yol2kimlik.get(yol)
        if not kimlik or kimlik not in dizin:
            eksik += 1
            continue
        a = (v.get("a") or "").strip()
        if not a:
            bos += 1
            continue
        n = dizin[kimlik]
        onceki_ceviri = n["d_tr"] and n["d_tr"] != n["d_en"]
        n["d_en"] = a
        if not onceki_ceviri:
            n["d_tr"] = a
        yazildi += 1

    KATALOG.write_text(json.dumps(kat, ensure_ascii=False, indent=1), encoding="utf8")
    toplam = len(dizin)
    dolu = sum(1 for n in dizin.values() if n["d_en"].strip())
    print(f"aciklama islendi: {yazildi}, kaynakta bos: {bos}, katalogda karsiligi yok: {eksik}")
    print(f"aciklamasi olan dugum: {dolu}/{toplam}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
KATALOG ESLESTIRICI
-------------------
Tedarikci kategori agacindaki adlari bizim katalog dugumlerimize baglar. 2686
dugum icin elle tablo yazmak mumkun olmadigindan eslesme ad benzerligiyle
kurulur, ama iki sinirla:

  1. Agac sinirli. Bir kaynak dugumun cocuklari yalnizca, ustunun eslestigi
     bizim dugumun cocuklariyla yarisir. "Cup Brushes" boylece Zimpara
     agacindaki tel fircalara gider, Temizlik agacindaki fircalara degil.

  2. Bilgi agirlikli. Kardeslerin hepsinde gecen kelime ("abrasive", "wheel")
     neredeyse hic puan getirmez; ayirt edici kelime cok getirir. Aksi halde
     "Abrasive Accessories" ile "Coated Abrasives" ortak "abrasive" yuzunden
     eslesiyordu.

Eslesmeye ayrica en az bir ayirt edici kelimenin tutmasi sarti var; sadece
genel kelimeyle kurulan eslesme kabul edilmez. Skoru esigin altinda kalan
dugum bos birakilir -- yanlis gorsel, motife dusmekten kotudur.

Girdi (JSON dizisi):
    [{"yol": "abrasives/sanding-abrasives", "ad": "Sanding Abrasives",
      "ust": "abrasives", "gorsel": "https://..."}, ...]

Kullanim:
    python katalog-esle.py kaynak-agac.json --rapor       okunur ozet
    python katalog-esle.py kaynak-agac.json > eslesme.json
"""
import json, math, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KATALOG = ROOT / "v3-saha" / "katalog" / "catalog.json"

GURULTU = {"and", "or", "the", "for", "with", "of", "other", "more", "all",
           "type", "general", "misc", "ve", "ile", "diger"}

# Ana kategoriler: tedarikcinin adi -> bizim kimlik. Ilk kademede tahmine
# gerek yok, liste zaten belli. Deger None ise bizde karsiligi yok.
ANA = {
    "abrasives": "abrasives",
    "adhesives sealants and tape": "adhesives-sealants-tape",
    "cleaning and janitorial": "cleaning-janitorial",
    "electrical": "electrical",
    "electronics batteries": "electronics-batteries",
    "fasteners": "fasteners",
    "fleet vehicle maintenance": "fleet-vehicle-maintenance",
    "food service food processing": "food-service-processing",
    "furnishings hospitality building materials": "furnishings-hospitality-building",
    "hvac and refrigeration": "hvac-and-refrigeration",
    "hardware": "hardware",
    "hydraulics": "hydraulics",
    "lab supplies": None,
    "lighting": "lighting",
    "lubrication": "lubrication",
    "machining": "machining",
    "material handling": "material-handling",
    "motors": "motors",
    "office supplies": None,
    "outdoor equipment": "outdoor-equipment",
    "packaging shipping": "packaging-shipping",
    "paints equipment and supplies": "paints-equipment-supplies",
    "pipe hose tube fittings": "pipe-hose-tube-fittings",
    "plumbing": "plumbing",
    "pneumatics": "pneumatics",
    "power transmission": "power-transmission",
    "pumps": "pumps",
    "raw materials": "raw-materials",
    "retail supplies store operations": None,
    "safety": "safety",
    "security": "security",
    "test instruments": "test-instruments",
    "tools": "tools",
    "welding": "welding",
}

TR = {"ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i"}


def sadelestir(s):
    s = unicodedata.normalize("NFC", str(s or "")).lower()
    return "".join(TR.get(c, c) for c in s)


def kok(k):
    """Kaba kok bulma. Dilbilimsel dogruluk degil, iki tarafin ayni sonuca
    varmasi onemli: cutting/cut-off -> cut, grinding -> grind, brushes -> brush."""
    if len(k) > 4 and k.endswith("ies"):
        k = k[:-3] + "y"
    elif len(k) > 4 and k.endswith(("ches", "shes", "sses", "xes", "zes")):
        k = k[:-2]
    elif len(k) > 3 and k.endswith("s") and not k.endswith("ss"):
        k = k[:-1]
    for son in ("ing", "ed"):
        if len(k) > len(son) + 2 and k.endswith(son):
            g = k[: -len(son)]
            if len(g) > 2 and g[-1] == g[-2] and g[-1] not in "lsz":
                g = g[:-1]                       # cutting -> cutt -> cut
            k = g
            break
    return k


def parcala(s):
    return {kok(k) for k in re.split(r"[^a-z0-9]+", sadelestir(s))
            if len(k) > 1 and k not in GURULTU}


# ---------------------------------------------------------------- katalog
def gez(nodes, ust=None):
    for n in nodes:
        yield n, ust
        yield from gez(n.get("kids", []), n)


def yukle_katalog():
    kat = json.loads(KATALOG.read_text(encoding="utf8"))
    bilgi = {}
    for n, ust in gez(kat):
        bilgi[n["id"]] = {
            "dugum": n, "ust": ust["id"] if ust else None,
            "jeton": parcala(n["en"]) | parcala(n["id"]),
            "cocuk": [k["id"] for k in n.get("kids", [])],
        }
    return kat, bilgi, [n["id"] for n in kat]


# ---------------------------------------------------------------- skor
def agirliklar(kumeler):
    """Kardes grubunda gecen her kelimeye bilgi agirligi (IDF) ve genellik damgasi."""
    N = max(1, len(kumeler))
    df = {}
    for k in kumeler:
        for t in k:
            df[t] = df.get(t, 0) + 1
    genel_esik = max(2, 0.35 * N)          # kardeslerin ucte birinde geciyorsa genel sayilir
    return ({t: math.log(1 + N / c) for t, c in df.items()},
            {t for t, c in df.items() if c > genel_esik})


VARSAYILAN_AGIRLIK = math.log(2)          # grupta hic gecmeyen kelime


def skor(a, b, w, genel, tek_ortak_yeter=True):
    """Bilgi agirlikli kosinus benzerligi + ayirt edici kelime sarti.

    Ayirt edici = kardeslerin cogunda gecmeyen kelime. "Abrasive Accessories"
    ile "Coated Abrasives" yalnizca herkeste gecen "abrasive" uzerinden
    eslesemesin diye.
    """
    g = lambda t: w.get(t, VARSAYILAN_AGIRLIK)
    ortak = a & b
    if not ortak:
        return 0.0, False
    pa = sum(g(t) ** 2 for t in a) ** 0.5
    pb = sum(g(t) ** 2 for t in b) ** 0.5
    if not pa or not pb:
        return 0.0, False
    s = sum(g(t) ** 2 for t in ortak) / (pa * pb)

    # Genis havuzda tek ortak kelimeyle kurulan eslesme, taraflardan biri tek
    # kelimelik degilse kabul edilmez: "Rubber Rods" ile "Aluminium Bar & Rod"
    # yalnizca "rod", "Welding Curtain Rolls" ile "Turning Rolls" yalnizca
    # "roll" uzerinden bulusuyordu. "Bluetooth Padlocks" -> "Padlocks" ise tek
    # kelimelik oldugu icin gecerli kalir. Dar havuzda (kardesler arasi) bu
    # kural gereksiz katilik yapiyor, orada kapali.
    yeterli = tek_ortak_yeter or len(ortak) >= 2 or min(len(a), len(b)) == 1
    return s, yeterli and any(t not in genel for t in ortak)


# 0.32: bilinen Zimpara agacinda yanlis eslesme uretmeyen en dusuk esik.
# Yukseltmek kapsami dusurur, dusurmek zorlama eslesme getirir.
ESIK = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--esik=")), 0.32))
DEBUG = "--tara" in sys.argv


def esle(kaynak, bilgi, kok, esik=ESIK):
    for k in kaynak:
        k["derinlik"] = k["yol"].count("/")
        k["jeton"] = parcala(k["ad"])

    yol2kimlik, alinan = {}, set()
    sonuc, kalan = [], []

    for d in sorted({k["derinlik"] for k in kaynak}):
        katman = [k for k in kaynak if k["derinlik"] == d]

        if d == 0:                                     # ana kademe: elle liste
            for k in katman:
                anahtar = " ".join(sorted(parcala(k["ad"])))
                kimlik, listede = None, False
                for ad, hedef in ANA.items():
                    if " ".join(sorted(parcala(ad))) == anahtar:
                        kimlik, listede = hedef, True
                        break
                if listede and kimlik is None:
                    # listede ama karsiligi yok (Lab Supplies, Office Supplies,
                    # Retail Supplies). Bulanik eslesmeye dusurulmemeli; yoksa
                    # ortak "supplies" kelimesiyle Boya'ya gidiyordu.
                    kalan.append({"yol": k["yol"], "ad": k["ad"], "derinlik": d})
                    continue
                if kimlik is None:                     # listede yoksa ada gore dene
                    w, genel = agirliklar([bilgi[i]["jeton"] for i in kok])
                    en_iyi = max(((skor(k["jeton"], bilgi[i]["jeton"], w, genel), i) for i in kok),
                                 key=lambda t: t[0][0])
                    (s, ayirt), i = en_iyi
                    kimlik = i if s >= esik and ayirt and i not in alinan else None
                if kimlik and kimlik not in alinan:
                    yol2kimlik[k["yol"]] = kimlik
                    alinan.add(kimlik)
                else:
                    kalan.append({"yol": k["yol"], "ad": k["ad"], "derinlik": d})
            continue

        # Alt kademeler: her dugum, ustunun eslestigi dugumun cocuklariyla yarisir.
        # Ust eslesmediyse dugum ulasilamaz kalmasin diye en yakin eslesmis ataya
        # cikilir ve o atanin tum alt agaci havuz olur -- dallanma sinirini
        # bozmadan kapsami acar.
        def capa(yol):
            p = yol
            while "/" in p:
                p = p.rsplit("/", 1)[0]
                if p in yol2kimlik:
                    return yol2kimlik[p], p == yol.rsplit("/", 1)[0]
            return None, False

        def alt_agac(kimlik):
            yigin, out = list(bilgi[kimlik]["cocuk"]), []
            while yigin:
                i = yigin.pop()
                out.append(i)
                yigin.extend(bilgi[i]["cocuk"])
            return out

        gruplar = {}
        for k in katman:
            capa_kimlik, dogrudan = capa(k["yol"])
            gruplar.setdefault((capa_kimlik, dogrudan), []).append(k)

        for (ust_kimlik, dogrudan), cocuklar in gruplar.items():
            if not ust_kimlik:
                havuz = []
            else:
                aday = bilgi[ust_kimlik]["cocuk"] if dogrudan else alt_agac(ust_kimlik)
                havuz = [i for i in aday if i not in alinan]
            if not havuz:
                kalan.extend({"yol": c["yol"], "ad": c["ad"], "derinlik": d} for c in cocuklar)
                continue
            # agirliklar bu kardes grubunda hesaplanir
            w, genel = agirliklar([bilgi[i]["jeton"] for i in havuz] + [c["jeton"] for c in cocuklar])
            # Dogrudan ust eslesmisse aday havuzu dar ve guvenilir; ataya cikilan
            # yedek yolda havuz genis oldugu icin cubugu yukselt.
            yerel_esik = esik if dogrudan else max(esik, 0.50)
            adaylar = []
            for c in cocuklar:
                for i in havuz:
                    s, ayirt = skor(c["jeton"], bilgi[i]["jeton"], w, genel)
                    if DEBUG and s > 0:
                        print(f'    {s:.2f}{"" if ayirt else " (genel)"}  {c["ad"][:34]:<34} ~ {i}',
                              file=sys.stderr)
                    if s >= yerel_esik and ayirt:
                        adaylar.append((s, c["yol"], i))
            adaylar.sort(key=lambda t: -t[0])
            kullanilan = set()
            for s, yol, i in adaylar:
                if yol in kullanilan or i in alinan:
                    continue
                kullanilan.add(yol); alinan.add(i); yol2kimlik[yol] = i
            for c in cocuklar:
                if c["yol"] not in kullanilan:
                    kalan.append({"yol": c["yol"], "ad": c["ad"], "derinlik": d})

        for k in katman:
            if k["yol"] in yol2kimlik:
                i = yol2kimlik[k["yol"]]
                sonuc.append({"yol": k["yol"], "ad": k["ad"], "kimlik": i,
                              "hedef": bilgi[i]["dugum"]["en"], "hedef_tr": bilgi[i]["dugum"]["tr"],
                              "gorsel": k.get("gorsel", "")})

    # ana kademe sonuclarini da ekle
    for k in kaynak:
        if k["derinlik"] == 0 and k["yol"] in yol2kimlik:
            i = yol2kimlik[k["yol"]]
            sonuc.insert(0, {"yol": k["yol"], "ad": k["ad"], "kimlik": i,
                             "hedef": bilgi[i]["dugum"]["en"], "hedef_tr": bilgi[i]["dugum"]["tr"],
                             "gorsel": k.get("gorsel", "")})
    return sonuc, kalan


CDN = "https://static.grainger.com/rp/s/is/image/Grainger/{}?wid=1000&hei=1000"


def oku_kaynak(p):
    """JSON dizisi ya da tarayicidan gelen ham 'yol<TAB>gorsel-kimligi' dokumu.

    Ham dokumde ad, yolun son parcasindan turetilir: slug ile gercek ad
    ayni kelimeleri tasidigi icin eslestirme acisindan fark etmez
    ("cut-off-grinding-abrasives" ~ "Cut-Off & Grinding Abrasives").
    """
    metin = p.read_text(encoding="utf8")
    if p.suffix.lower() == ".json" or metin.lstrip().startswith("["):
        return json.loads(metin)
    kayit = []
    for satir in metin.splitlines():
        if not satir.strip():
            continue
        yol, _, kimlik = satir.partition("\t")
        yol = yol.strip().strip("/")
        if not yol:
            continue
        kayit.append({
            "yol": yol,
            "ust": yol.rsplit("/", 1)[0] if "/" in yol else "",
            "ad": yol.rsplit("/", 1)[-1].replace("-", " ").title(),
            "gorsel": CDN.format(kimlik.strip()) if kimlik.strip() else "",
        })
    return kayit


GENIS_ESIK = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--genis=")), 0.34))

# Bizde ana grup olan ama tedarikcide ana grup olmayan dallar. Ikinci gecisin
# bunlarin alt agacini da tarayabilmesi icin karsilik gelen tedarikci dallari.
# Once bunlar islenir; yoksa "power-transmission" genel taramasi rulman
# kutucuklarini kapip bizim Rulmanlar grubunu bos birakiyor.
EK_KOK = {
    "bearings": ["power-transmission/bearings"],
    "valves": ["plumbing/plumbing-valves", "hydraulics/hydraulic-valves-flow-control",
               "pneumatics/pneumatic-valves"],
    "filtration": ["fleet-vehicle-maintenance/vehicle-equipment-filters",
                   "hvac-and-refrigeration/air-filters", "hydraulics/hydraulic-filtration",
                   "plumbing/water-filtration-purification-systems"],
    "compressors-generators": ["pneumatics/air-compressors-vacuum-pumps-blowers",
                               "outdoor-equipment/electrical-generators-power-stations"],
}


def genis_gecis(kaynak, bilgi, sonuc, esik=GENIS_ESIK):
    """Ikinci gecis: hala bos olan dugumler icin ayni ana grubun ALTINDAKI tum
    tedarikci dugumlerine, kademe farki gozetmeksizin bakar.

    Birinci gecis agac hizasina guveniyor: bizim alt grubumuz onlarin alt
    grubuyla yarisiyor. Iki taksonomi ayni derinlikte ayni seyi anlatmadigi icin
    ("Emery Cloth" bizde urun ailesi, onlarda hic yok ama "Sanding Abrasives"in
    altinda benzeri var) bircok dugum ulasilamiyordu. Havuz genis oldugundan
    esik de yuksek ve ayirt edici kelime sarti korunuyor.
    """
    ust_grup = {}                                  # dugum -> ana grup kimligi
    for kimlik in bilgi:
        p = kimlik
        while bilgi[p]["ust"]:
            p = bilgi[p]["ust"]
        ust_grup[kimlik] = p

    alinan = {s["kimlik"] for s in sonuc}
    kullanilan_yol = {s["yol"] for s in sonuc}
    # bizim ana grup -> tedarikcinin ana grup yolu
    kok_yol = {s["kimlik"]: s["yol"] for s in sonuc if "/" not in s["yol"]}

    kaynak_dizin = {k["yol"]: k for k in kaynak}
    for k in kaynak:
        k.setdefault("jeton", parcala(k["ad"]))

    # once ek koklar (dar ve isabetli), sonra dogal ana gruplar
    sira = [(b, y) for b, y in EK_KOK.items() if b in bilgi]
    sira += [(b, [y]) for b, y in kok_yol.items()]

    yeni = []
    for bizim_kok, onlarin_kokler in sira:
        havuz = [k for k in kaynak
                 if any(k["yol"].startswith(o + "/") for o in onlarin_kokler)
                 and k["yol"] not in kullanilan_yol]
        hedefler = [i for i in bilgi
                    if ust_grup[i] == bizim_kok and i not in alinan and i != bizim_kok]
        if not havuz or not hedefler:
            continue
        w, genel = agirliklar([bilgi[i]["jeton"] for i in hedefler] + [k["jeton"] for k in havuz])
        adaylar = []
        for i in hedefler:
            for k in havuz:
                s, ayirt = skor(bilgi[i]["jeton"], k["jeton"], w, genel, tek_ortak_yeter=False)
                if s >= esik and ayirt:
                    adaylar.append((s, i, k["yol"]))
        adaylar.sort(key=lambda t: -t[0])
        for s, i, yol in adaylar:
            if i in alinan or yol in kullanilan_yol:
                continue
            alinan.add(i); kullanilan_yol.add(yol)
            k = kaynak_dizin[yol]
            yeni.append({"yol": yol, "ad": k["ad"], "kimlik": i,
                         "hedef": bilgi[i]["dugum"]["en"], "hedef_tr": bilgi[i]["dugum"]["tr"],
                         "gorsel": k.get("gorsel", ""), "gecis": 2, "skor": round(s, 3)})
    return yeni


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    kaynak = oku_kaynak(Path(sys.argv[1]))
    kat, bilgi, kok = yukle_katalog()
    sonuc, kalan = esle(kaynak, bilgi, kok)
    birinci = len(sonuc)
    if "--tek-gecis" not in sys.argv:
        sonuc += genis_gecis(kaynak, bilgi, sonuc)

    # Tedarikci ayni fotografi birden cok kategoride kullaniyor. Bu yalnizca
    # KARDES kutucuklarda sorun: tek izgarada ikiz gorunuyor. Farkli dallardaki
    # tekrar zararsiz -- kullanici onlari yan yana gormuyor -- ve global
    # eleme iyi eslesmeleri de siliyordu. Agac hizali eslesme oncelikli.
    sonuc.sort(key=lambda s: (s.get("gecis", 1), -s.get("skor", 1.0)))
    gorulen, tekil = set(), []
    for s in sonuc:
        anahtar = (bilgi[s["kimlik"]]["ust"], s["gorsel"])
        if s["gorsel"] and anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        tekil.append(s)
    ikiz = len(sonuc) - len(tekil)
    sonuc = tekil
    eslesen = {s["kimlik"] for s in sonuc}
    print(f"gecis 1 (agac hizali): {birinci}   gecis 2 (ana grup icinde): "
          f"{len(sonuc) + ikiz - birinci}   ikiz gorsel elendi: {ikiz}   "
          f"toplam: {len(sonuc)}", file=sys.stderr)

    if "--rapor" in sys.argv:
        for d in (0, 1, 2):
            grup = [s for s in sonuc if s["yol"].count("/") == d]
            print(f"\n=== kademe {d+1}: {len(grup)} eslesme ===")
            for s in grup:
                print(f'  {s["ad"][:42]:<42} -> {s["kimlik"]:<26} ({s["hedef"][:34]})')
        print(f"\neslesmeyen kaynak ({len(kalan)}):")
        for k in kalan:
            print(f'  k{k["derinlik"]+1} {k["ad"]}')
        print(f"\ntoplam dugum {len(bilgi)}, gorsel alan {len(eslesen)}")
        return 0

    veri = json.dumps({"eslesme": sonuc, "eslesmeyen_kaynak": kalan},
                      ensure_ascii=False, indent=1)
    cikti = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--cikti=")), None)
    if cikti:                        # kabuk yonlendirmesi BOM ekliyor; dosyayi kendimiz yazalim
        Path(cikti).write_text(veri, encoding="utf8")
        print(f"{len(sonuc)} eslesme -> {cikti}")
    else:
        sys.stdout.write(veri)
    return 0


if __name__ == "__main__":
    sys.exit(main())

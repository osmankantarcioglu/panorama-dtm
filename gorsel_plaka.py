# -*- coding: utf-8 -*-
"""
ORTAK PLAKA MOTORU
------------------
Tedarikci kategori izgaralarindaki urun fotograflarini beyaz zeminden koparir ve
sitenin teknik-resim plakasina (4:3, 800x600) oturtur. Plaka; render.js'teki
motif kutucuklariyla ayni zemin, ayni izgara ve ayni kose isaretlerini kullanir,
boylece fotografli ve motifli kutucuklar tek bir dil konusur.

Kullananlar: gorsel-ayir.py (ana kategori izgarasi), gorsel-ayir-alt.py (alt sayfalar)
"""
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw, ImageFilter

# --- plaka paleti (render.js ile ayni) ---
BASE = (13, 16, 10)          # #0D100A
GRIDC = (29, 32, 22)         # #BCC08F @ .09 -> BASE uzerinde
TICKC = (69, 72, 53)         # #BCC08F @ .32 -> BASE uzerinde
GLOW = (36, 40, 28)          # urunun arkasindaki hafif hare

PW, PH = 800, 600
FIT_W, FIT_H = 540, 330      # urunun sigacagi kutu
CX, CY = 400, 262            # merkez; alt karartma seridi urunu yemesin diye yukarida

lum = lambda c: (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000


def icerik_bloklari(px, x0, y0, x1, y1, esik=246):
    """Hucredeki yatay icerik bloklarini (baslangic, bitis) olarak dondurur."""
    dolu = [any(lum(px[x, y]) < esik for x in range(x0, x1)) for y in range(y0, y1)]
    bloklar, i = [], 0
    while i < len(dolu):
        if dolu[i]:
            j = i
            while j < len(dolu) and dolu[j]:
                j += 1
            if j - i > 3:
                bloklar.append((y0 + i, y0 + j))
            i = j
        else:
            i += 1
    return bloklar


def urun_kutusu(px, x0, y0, x1, y1):
    """Hucrede en ustteki icerik blogu urun gorseli, altindaki etiket yazisidir."""
    bloklar = icerik_bloklari(px, x0, y0, x1, y1)
    if not bloklar:
        return None
    ty0, ty1 = bloklar[0]
    xs = [x for x in range(x0, x1) if any(lum(px[x, y]) < 246 for y in range(ty0, ty1))]
    if not xs:
        return None
    return min(xs), ty0, max(xs) + 1, ty1


def koparma(patch, zemin_esigi=232, golge_bandi=13):
    """Beyaz zemini ve yumusak golgeyi alfa kanalina cevirir.

    Once resmin kenarindan iceri dogru tasan beyaz bolge bulunur; boylece urunun
    kendi beyaz govdesi (mikrodalga, armatur, boya rulosu) korunur. Ardindan bu
    bolgeye komsu dar bantta kalan gri golge sondurulur.

    Butun adimlar numpy/scipy'nin C katmaninda. PIL'in ImageDraw.floodfill'i saf
    Python; 3000 gorselde goruntu basina yarim saniye tutuyor ve GIL'i biraktigi
    icin is parcaciklari da islemiyordu.
    """
    gri = np.asarray(patch.convert("L"), dtype=np.uint8)

    # 1) kenardan iceri tasan beyaz bolge = zemin. Urunun kendi beyaz govdesi
    #    (mikrodalga, armatur, boya rulosu) kenara bagli olmadigi icin korunur.
    aday = gri >= zemin_esigi
    tohum = np.zeros_like(aday)
    tohum[0, :] = tohum[-1, :] = True
    tohum[:, 0] = tohum[:, -1] = True
    tohum &= aday
    zemin = ndimage.binary_propagation(tohum, mask=aday)

    # 2) zemine komsu bantta kalan gri golgeyi sondur; ic bolge tam opak kalir
    yakin = ndimage.binary_dilation(zemin, iterations=golge_bandi // 2)
    rampa = np.clip((240.0 - gri) * (255.0 / 26.0), 0, 255)

    alpha = np.where(zemin, 0.0, np.where(yakin, rampa, 255.0)).astype(np.uint8)
    return Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(0.6))


def plaka():
    """Bos teknik-resim plakasi."""
    img = Image.new("RGB", (PW, PH), BASE)
    d = ImageDraw.Draw(img)
    hare = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(hare).ellipse([CX - 300, CY - 190, CX + 300, CY + 190], fill=90)
    img.paste(Image.new("RGB", (PW, PH), GLOW), (0, 0), hare.filter(ImageFilter.GaussianBlur(90)))
    for x in range(40, PW, 40):
        d.line([(x, 0), (x, PH)], fill=GRIDC, width=2)
    for y in range(40, PH, 40):
        d.line([(0, y), (PW, y)], fill=GRIDC, width=2)
    for (x, y, sx, sy) in ((28, 28, 1, 1), (772, 572, -1, -1)):
        d.line([(x, y), (x + 40 * sx, y)], fill=TICKC, width=3)
        d.line([(x, y), (x, y + 40 * sy)], fill=TICKC, width=3)
    return img


def kart(im, kutu, kenar=6, sinir=None):
    """Kaynak resimden verilen kutuyu kesip plakaya oturtulmus 800x600 kart uretir."""
    bx0, by0, bx1, by1 = kutu
    if sinir:
        sx0, sy0, sx1, sy1 = sinir
        patch = im.crop((max(sx0, bx0 - kenar), max(sy0, by0 - kenar),
                         min(sx1, bx1 + kenar), min(sy1, by1 + kenar)))
    else:
        patch = im.crop((bx0 - kenar, by0 - kenar, bx1 + kenar, by1 + kenar))
    alpha = koparma(patch)

    # kucuk kaynagi once buyut (ekran goruntusunden kirpilan kareler ~90px);
    # zaten buyuk gelen urun fotografini bosuna sisirme
    k = max(1, min(4, -(-FIT_W // max(1, patch.width))))
    big = patch.resize((patch.width * k, patch.height * k), Image.LANCZOS)
    biga = alpha.resize((patch.width * k, patch.height * k), Image.LANCZOS)
    s = min(FIT_W / big.width, FIT_H / big.height)
    nw, nh = max(1, int(big.width * s)), max(1, int(big.height * s))
    big = big.resize((nw, nh), Image.LANCZOS)
    biga = biga.resize((nw, nh), Image.LANCZOS)

    card = plaka()
    card.paste(big, (CX - nw // 2, CY - nh // 2), biga)
    return card


def kontak_sayfasi(kartlar, yol, sutun=6, kw=240, kh=180):
    """Kontrol icin kucuk onizleme tabakasi."""
    if not kartlar:
        return
    satir = (len(kartlar) + sutun - 1) // sutun
    sheet = Image.new("RGB", (sutun * kw, satir * (kh + 22)), (10, 12, 10))
    dr = ImageDraw.Draw(sheet)
    for n, (ad, card) in enumerate(kartlar):
        cx, cy = (n % sutun) * kw, (n // sutun) * (kh + 22)
        sheet.paste(card.resize((kw - 8, kh - 8), Image.LANCZOS), (cx + 4, cy + 4))
        dr.text((cx + 6, cy + kh), ad, fill=(200, 205, 170))
    sheet.save(yol)

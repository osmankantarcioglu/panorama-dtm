# Grainger kategori gorsel toplayici

## Kurulum

```bash
pip install playwright
playwright install chromium
```

## Calistirma

Once kucuk bir testle basla:

```bash
python grainger_scraper.py --start /category/abrasives --max-pages 15
```

Tum agac (yavas, saatler surebilir):

```bash
python grainger_scraper.py --start /category --max-pages 2000 --delay 2.0
```

Parametreler: `--out` (cikti klasoru), `--max-depth` (kategori derinligi),
`--delay` (sayfa basi bekleme), `--headful` (tarayiciyi goster),
`--no-report` (HTML dokumani uretme).

## Cikti

```
grainger_images/
  images/abrasives/sanding-abrasives/...jpg
  images.csv        her gorsel: dosya, url, kategori, parent, alt metin, boyut, sha1
  categories.csv    kategori agaci: path, ad, url, parent, derinlik, gorsel sayisi
  manifest.json     tam kayit (mobil uygulama / DB aktarimi icin)
  report.html       gorsellerin kategori kategori dokumani
  report.md
```

Dokumani sonradan yeniden uretmek icin: `python build_report.py grainger_images`

## Davranis notlari

- Sadece `--start` ile verilen `/category/...` alt agacinda gezer; urun sayfalarina girmez.
- `robots.txt` okunur ve izin verilmeyen yollar atlanir; koruma mekanizmasi asilmaz.
- Sayfa basi bekleme + tek sekme ile calisir, paralel istek atmaz.
- Ayni gorsel URL'i ve ayni icerik (sha1) iki kez indirilmez.
- Lazy-load gorseller icin sayfa asagi kaydirilir; `srcset` icinden en buyuk boy secilir.
- Indirilen gorsellerin telifi Grainger'a aittir. Yeniden yayin/ticari kullanim icin
  Grainger kullanim sartlarini kontrol et; bu script yalnizca teknik toplama yapar.

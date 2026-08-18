# Ürün görselleri

Buraya koyduğunuz görseller katalog kutucuklarına otomatik yerleşir.
Eklemek için proje kökünde:

    node katalog-derle.mjs

## Dosya adlandırma

**Kesin yöntem — dosya adı = kategori kimliği.** Birebir ad her zaman kazanır.

    motors.jpg          -> Motorlar
    ac-motors.jpg       -> Motorlar / AC Motorlar
    bearings.webp       -> Rulmanlar

Kimlik listesi proje kökündeki `katalog-gorsel-listesi.md` dosyasında.
Yeniden üretmek için: `node katalog-derle.mjs --liste`

**Esnek yöntem — tedarikçi paketini olduğu gibi atın.** Dosya adı kimlikle
birebir tutmuyorsa, ad kelimelere ayrılıp kategori adıyla karşılaştırılır.
Şunların hepsi Motorlar'a gider:

    Motors_Category_Hero.jpg
    WELDING EQUIPMENT main.webp     -> Kaynak
    hydraulics_cat_LARGE.png        -> Hidrolik
    zimpara ve asindiricilar.jpg    -> Zımpara ve Aşındırıcılar

Türkçe adlar ve büyük harf sorun değil. "image", "hero", "category", "01" gibi
dolgu kelimeler yok sayılır. Eşleşme zayıfsa dosya atlanır ve raporda listelenir.

Bir dosya yanlış kategoriye giderse, adını o kategorinin kimliğiyle
değiştirin — birebir ad bulanık eşleşmeyi ezer.

## Kapsam

Görsel asıl olarak **35 ana kategoride** görünür. Alt gruplar isteğe bağlı,
ürün ailesi seviyesinde gerekmez. Hepsini doldurmak zorunda değilsiniz;
görseli olmayan her kategori otomatik olarak teknik-resim motifine düşer.

`node katalog-derle.mjs` her çalıştığında ana kategori kapsamını ve hangi
kategorilerin hâlâ görselsiz olduğunu yazdırır.

## Tedarikçi ekran görüntüsünden toplu ayırma

Tedarikçi kategori tablosunun ekran görüntüsünü `brand_assets/kaynak-izgaralar/`
içine atın, sonra proje kökünde:

    python gorsel-ayir.py            # ana kategori ızgarası (7x5 tablo)
    python gorsel-ayir-alt.py        # alt kategori sayfaları
    node katalog-derle.mjs

Betikler tablo çizgilerini kendisi bulur, her kutucuktaki ürünü beyaz zeminden
koparır ve motif kutucuklarıyla aynı teknik-resim plakasına oturtur. Hangi
kutucuğun hangi düğüme gideceği `gorsel-ayir-alt.py` içindeki `SAYFALAR`
tablosunda; yeni sayfa eklerken oraya bir satır yazmak yeterli. Boş liste
bıraktığınız kutucuk atlanır, düğüm motifte kalır.

Kontrol için her sayfanın küçük önizleme tabakası
`temporary screenshots/kontak-*.png` olarak yazılır.

## Tedarikçi sitesinden toplu toplama

Tedarikçi (Grainger) otomatik tarayıcıyı engelliyor: headless Chromium, görünür
Chromium ve gerçek Chrome'un üçü de 403 alıyor. Zoro, MSC, Fastenal, RS Online
da aynı şekilde kapalı. Koruma aşılmıyor — yol, **Claude in Chrome eklentisi**
ile kullanıcının kendi oturumunda gezinmek.

Akış:

1. Eklenti bağlıyken `grainger.com/category` açılır.
2. Sayfa içinde çalışan tarayıcı, kategori sayfalarını `fetch` ile okur ve her
   kutucuktan `yol` + görsel kimliğini çıkarır. Sayfa başına ekran görüntüsü
   almak yerine bu yöntem kullanılır; üç kademe için ~490 sayfa var.
3. Toplanan liste sayfa içinde bir Blob'a yazılıp `<a download>` ile indirilir;
   `grainger-agac.tsv` olarak Downloads klasörüne düşer (`yol<TAB>görsel-kimliği`).
   Veriyi localhost'a POST etmek işe yaramıyor — Chrome, https bir sayfadan yerel
   ağa yapılan isteği engelliyor.
4. Dosya `brand_assets/toplanan/` altına alınır, sonra:

       python katalog-esle.py brand_assets/toplanan/grainger-agac.tsv --cikti=brand_assets/toplanan/eslesme.json
       python gorsel-ic-al.py brand_assets/toplanan/eslesme.json
       python gorsel-ic-al.py brand_assets/toplanan/elle-eslesme.json --uzerine
       node katalog-derle.mjs

   `elle-eslesme.json` ad benzerliğinin bulamadığı bağları taşır; yeni bir elle
   düzeltme gerektiğinde oraya satır eklemek yeterli.

Görseller `static.grainger.com` (Adobe Scene7) üzerinden iniyor; bu ana koruma
altında değil, `?wid=1000&hei=1000` ile tam boy alınabiliyor.

### Eşleştirme neden hepsini doldurmuyor

Tedarikçinin ağacı bizimkiyle birebir değil. `katalog-esle.py` ad benzerliğiyle
eşleştirir, ama iki sınırla: eşleşme ağaç içinde kalır (bir düğümün çocukları
yalnızca bizim karşılık düğümün çocuklarıyla yarışır) ve genel kelimeler
("abrasive", "wheel") bilgi ağırlığıyla bastırılır.

Üstü eşleşmeyen düğüm ulaşılamaz kalmasın diye en yakın eşleşmiş ataya çıkılır,
ama o yedek yolda havuz genişlediği için eşik 0,32'den 0,50'ye yükselir. Bu
olmadan "Wire Cloth Lab Sieves" Tel Fırçalar'a bağlanıyordu.

Ölçülen sonuç: 491 tedarikçi sayfası, 3391 kutucuk, 637 düğüme görsel.
Ana grup %100, alt grup %45, ürün ailesi %19. "Rubbing Bricks ≈ Bant Temizleme
Çubukları" gibi alan bilgisi gerektiren bağları kelime benzerliği bulamıyor;
eşleşmeyen düğüm teknik-resim motifinde kalır — yanlış görsel koymaktan iyidir.

Eşiği `--esik=0.28` gibi düşürmek kapsamı artırır, zorlama eşleşme riskini de.

## Biçim

Kabul edilen uzantılar: .jpg .jpeg .png .webp .avif .svg
Önerilen: 4:3 en-boy oranı, en az 800x600 piksel.
Görseller lazy-load edilir; kutucukta haki renk katmanı ve alt karartma uygulanır.

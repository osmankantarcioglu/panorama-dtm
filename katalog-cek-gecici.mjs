import puppeteer from 'puppeteer';
import { join } from 'node:path';
const OUT = join(process.cwd(), 'temporary screenshots');
const bekle = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-color-profile=srgb'] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  await page.goto('http://localhost:4300/v3-saha/', { waitUntil: 'networkidle0', timeout: 90000 });
  await page.waitForFunction(() => [...document.querySelectorAll('style')].some((s) => s.textContent.includes('.mx-auto')), { timeout: 20000 }).catch(() => {});
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
    const p = (ms) => new Promise((r) => setTimeout(r, ms));
    for (let y = 0; y < document.documentElement.scrollHeight; y += Math.round(innerHeight * 0.7)) { scrollTo(0, y); await p(140); }
    document.getElementById('urunler').scrollIntoView({ block: 'start' });
    await p(1200);
  });
  // uzun aciklamali bir kutucugun uzerine gel
  const kutu = await page.evaluate(() => {
    const t = [...document.querySelectorAll('#cat-grid .cat-tile')];
    const hedef = t.find((x) => (x.querySelector('.cat-desc')?.textContent || '').length > 200) || t[0];
    const r = hedef.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + 40, uzunluk: (hedef.querySelector('.cat-desc')?.textContent || '').length,
             ad: hedef.querySelector('.disp-s')?.textContent };
  });
  console.log('hover:', kutu.ad, 'aciklama uzunlugu', kutu.uzunluk);
  await page.mouse.move(kutu.x, kutu.y);
  await bekle(1200);
  await page.screenshot({ path: join(OUT, 'hover-testi.png') });
  const tasma = await page.evaluate(() => {
    const d = [...document.querySelectorAll('#cat-grid .cat-desc')];
    return d.filter((x) => x.scrollHeight > x.clientHeight + 2).length + '/' + d.length;
  });
  console.log('tasan panel:', tasma);
} finally { await browser.close(); }

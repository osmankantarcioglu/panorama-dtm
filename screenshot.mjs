import puppeteer from 'puppeteer';
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const OUT_DIR = join(process.cwd(), 'temporary screenshots');

const url = process.argv[2] || 'http://localhost:3000';
const label = process.argv[3] || '';
// full-page by default; pass `viewport` as the 4th arg for above-the-fold only
const mode = process.argv[4] || 'full';

async function nextIndex() {
  await mkdir(OUT_DIR, { recursive: true });
  const files = await readdir(OUT_DIR);
  let max = 0;
  for (const f of files) {
    const m = /^screenshot-(\d+)/.exec(f);
    if (m) max = Math.max(max, Number(m[1]));
  }
  return max + 1;
}

const n = await nextIndex();
const name = label ? `screenshot-${n}-${label}.png` : `screenshot-${n}.png`;
const path = join(OUT_DIR, name);

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-color-profile=srgb'],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });

  // The Tailwind CDN generates its stylesheet at runtime; networkidle0 can
  // land before that finishes and capture an unstyled page.
  try {
    await page.waitForFunction(
      () => [...document.querySelectorAll('style')].some((s) => s.textContent.includes('.mx-auto')),
      { timeout: 15000 },
    );
  } catch {
    console.warn('warn: Tailwind stylesheet not detected — continuing');
  }

  // Let fonts settle, then walk the page slowly so IntersectionObserver
  // reveals actually fire — fast rAF scrolling makes IO skip elements.
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready;
    const pause = (ms) => new Promise((r) => setTimeout(r, ms));
    const step = Math.round(window.innerHeight * 0.75);
    for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await pause(220);
    }
    window.scrollTo(0, document.documentElement.scrollHeight);
    await pause(400);
    window.scrollTo(0, 0);
    await pause(500);
  });
  await new Promise((r) => setTimeout(r, 900));

  await page.screenshot({ path, fullPage: mode === 'full' });
  console.log(`Saved ${path}`);
} finally {
  await browser.close();
}

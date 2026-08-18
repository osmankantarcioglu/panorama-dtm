"""
Grainger kategori gorseli toplayici.

/category agacinda gezinir, her kategori sayfasindaki gorselleri indirir ve
her gorsel icin kategori adi / parent / alt kategori bilgisini kaydeder.

Kullanim:
    python grainger_scraper.py --start /category/abrasives --max-pages 40
    python grainger_scraper.py --start /category --max-pages 500 --delay 2.0

Cikti (varsayilan ./grainger_images):
    images/<kategori/yolu>/<dosya>.jpg   indirilen gorseller
    images.csv                           her gorsel + kategori metadatasi
    categories.csv                       kategori agaci
    manifest.json                        makine okunur tam kayit
    report.html                          gorsellerin dokumani (build_report.py)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
import urllib.robotparser as robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.async_api import async_playwright

BASE = "https://www.grainger.com"
DOMAIN = "www.grainger.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Kategori kartlarinda kullanilmayan kucuk ikon/logo gorsellerini eleme esigi
MIN_PIXELS = 90
SKIP_URL_PATTERNS = re.compile(
    r"(sprite|icon|logo|placeholder|1x1|pixel|spacer|loading|\.svg($|\?))", re.I
)


# ---------------------------------------------------------------- yardimcilar


def slugify(text: str, limit: int = 80) -> str:
    text = re.sub(r"[^\w\-]+", "-", (text or "").strip().lower())
    return text.strip("-_")[:limit] or "unknown"


def normalize_page_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", "", ""))


def category_parts(url: str) -> list[str]:
    """/category/abrasives/sanding -> ['abrasives', 'sanding']"""
    path = urlparse(url).path.strip("/")
    if path.startswith("category"):
        path = path[len("category") :].strip("/")
    return [slugify(p) for p in path.split("/") if p]


def category_path(url: str) -> str:
    parts = category_parts(url)
    return "/".join(parts) if parts else "_root"


def parent_url(url: str) -> str:
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) <= 2:  # ['category'] veya ['category', 'abrasives']
        return f"{BASE}/category" if len(parts) == 2 else ""
    return f"{BASE}/" + "/".join(parts[:-1])


def upgrade_image_url(url: str) -> str:
    """Grainger CDN'inde kucuk boy varyantlarini buyuk boya cevirmeye calisir."""
    out = re.sub(r"(_|-)(sm|smThumb|thumb|small|xs|60|90|120|150)(?=\.(jpg|jpeg|png|webp))",
                 "_lg", url, flags=re.I)
    out = re.sub(r"\$[a-z0-9_\-]*(thumb|small|sm)[a-z0-9_\-]*\$", "$lgimg$", out, flags=re.I)
    return out


def guess_ext(url: str, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    for key, ext in (("jpeg", ".jpg"), ("png", ".png"), ("webp", ".webp"),
                     ("avif", ".avif"), ("gif", ".gif"), ("svg", ".svg")):
        if key in ct:
            return ext
    m = re.search(r"\.(jpe?g|png|webp|avif|gif|svg)(?:$|\?)", url, re.I)
    return "." + m.group(1).lower().replace("jpeg", "jpg") if m else ".jpg"


def robots_checker(user_agent: str = "*") -> robotparser.RobotFileParser:
    rp = robotparser.RobotFileParser()
    rp.set_url(f"{BASE}/robots.txt")
    try:
        rp.read()
    except Exception as exc:  # robots okunamazsa yine de kurallara uyar gibi davran
        print(f"! robots.txt okunamadi ({exc}); sadece /category yollari taranacak")
    return rp


# ---------------------------------------------------------------- sayfa isleri

PAGE_SCRIPT = """
() => {
  const pick = (srcset) => {
    if (!srcset) return null;
    const best = srcset.split(',')
      .map(s => s.trim().split(/\\s+/))
      .map(([u, d]) => ({ u, w: parseInt(d || '0', 10) || 0 }))
      .sort((a, b) => b.w - a.w)[0];
    return best ? best.u : null;
  };
  const out = [];
  document.querySelectorAll('img').forEach((img) => {
    const src = pick(img.getAttribute('srcset')) || img.currentSrc || img.src ||
                img.getAttribute('data-src') || img.getAttribute('data-lazy-src');
    if (!src || src.startsWith('data:')) return;
    out.push({
      src,
      alt: (img.alt || '').trim(),
      title: (img.getAttribute('title') || '').trim(),
      width: img.naturalWidth || img.width || 0,
      height: img.naturalHeight || img.height || 0,
      label: (img.closest('a')?.innerText || img.closest('li,article,div')?.innerText || '')
              .trim().split('\\n')[0].slice(0, 120),
      link: img.closest('a')?.href || '',
    });
  });
  const links = [...document.querySelectorAll('a[href]')].map(a => a.href);
  const heading = (document.querySelector('h1')?.innerText || document.title || '').trim();
  return { images: out, links, heading };
}
"""


async def autoscroll(page, rounds: int = 12, step_wait: float = 0.45) -> None:
    """Lazy-load edilen gorselleri tetiklemek icin sayfayi asagi kaydirir."""
    last = 0
    for _ in range(rounds):
        height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
        await page.wait_for_timeout(int(step_wait * 1000))
        if height == last:
            break
        last = height
    await page.evaluate("window.scrollTo(0, 0)")


async def download(request_ctx, url: str, referer: str) -> tuple[bytes, str] | None:
    try:
        resp = await request_ctx.get(url, headers={"Referer": referer}, timeout=30000)
        if not resp.ok:
            return None
        body = await resp.body()
        if len(body) < 1200:  # 1x1 / bos gorsel
            return None
        return body, resp.headers.get("content-type", "")
    except Exception:
        return None


# ---------------------------------------------------------------- ana akis


async def crawl(args) -> dict:
    start_url = normalize_page_url(urljoin(BASE, args.start))
    start_path = urlparse(start_url).path.rstrip("/")
    out_dir = Path(args.out)
    img_root = out_dir / "images"
    img_root.mkdir(parents=True, exist_ok=True)

    rp = robots_checker()

    def allowed(url: str) -> bool:
        p = urlparse(url)
        if p.netloc != DOMAIN:
            return False
        path = p.path.rstrip("/")
        in_scope = path == start_path or path.startswith(start_path + "/")
        if not in_scope:
            return False
        try:
            return rp.can_fetch(UA, url)
        except Exception:
            return True

    queue: list[tuple[str, int]] = [(start_url, 0)]
    seen_pages: set[str] = {start_url}
    seen_img_urls: set[str] = set()
    seen_hashes: dict[str, str] = {}
    categories: dict[str, dict] = {}
    records: list[dict] = []
    pages_done = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headful)
        context = await browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 1000})
        page = await context.new_page()
        # Gereksiz trafigi kes (font/medya), gorseller lazim oldugu icin acik kalir
        await page.route("**/*", lambda r: asyncio.ensure_future(
            r.abort() if r.request.resource_type in ("media", "font") else r.continue_()
        ))

        while queue and pages_done < args.max_pages:
            url, depth = queue.pop(0)
            if depth > args.max_depth:
                continue
            pages_done += 1
            print(f"[{pages_done}/{args.max_pages}] d{depth} {url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(int(args.delay * 1000))
                await autoscroll(page)
                data = await page.evaluate(PAGE_SCRIPT)
            except Exception as exc:
                print(f"  ! sayfa alinamadi: {exc}")
                continue

            cpath = category_path(url)
            cat_name = data.get("heading") or cpath.split("/")[-1].replace("-", " ").title()
            parent = normalize_page_url(parent_url(url)) if parent_url(url) else ""
            categories.setdefault(cpath, {
                "category_path": cpath,
                "category_name": cat_name,
                "category_url": url,
                "parent_path": category_path(parent) if parent else "",
                "parent_url": parent,
                "depth": depth,
                "image_count": 0,
                "subcategory_count": 0,
            })

            # alt kategorileri kuyruga al
            children = 0
            for link in data["links"]:
                nurl = normalize_page_url(link)
                if not allowed(nurl) or nurl in seen_pages:
                    continue
                if len(category_parts(nurl)) > len(category_parts(url)):
                    children += 1
                seen_pages.add(nurl)
                queue.append((nurl, depth + 1))
            categories[cpath]["subcategory_count"] += children

            # gorseller
            target_dir = img_root.joinpath(*cpath.split("/"))
            target_dir.mkdir(parents=True, exist_ok=True)

            for idx, img in enumerate(data["images"]):
                src = urljoin(url, img["src"])
                if SKIP_URL_PATTERNS.search(src):
                    continue
                if img["width"] and img["height"] and (
                    img["width"] < MIN_PIXELS or img["height"] < MIN_PIXELS
                ):
                    continue
                if src in seen_img_urls:
                    continue
                seen_img_urls.add(src)

                got = await download(context.request, upgrade_image_url(src), url)
                used = upgrade_image_url(src)
                if got is None:
                    got = await download(context.request, src, url)
                    used = src
                if got is None:
                    continue
                body, ctype = got

                sha1 = hashlib.sha1(body).hexdigest()
                if sha1 in seen_hashes:
                    continue

                label = slugify(img["label"] or img["alt"] or cat_name, 60)
                fname = f"{label}--{sha1[:8]}{guess_ext(used, ctype)}"
                fpath = target_dir / fname
                fpath.write_bytes(body)
                seen_hashes[sha1] = str(fpath)

                records.append({
                    "file": str(fpath.relative_to(out_dir)).replace("\\", "/"),
                    "image_url": used,
                    "original_src": src,
                    "category_name": cat_name,
                    "category_path": cpath,
                    "category_url": url,
                    "parent_path": categories[cpath]["parent_path"],
                    "parent_url": parent,
                    "depth": depth,
                    "alt_text": img["alt"] or img["title"],
                    "item_label": img["label"],
                    "item_link": img["link"],
                    "width": img["width"],
                    "height": img["height"],
                    "bytes": len(body),
                    "sha1": sha1,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                })
                categories[cpath]["image_count"] += 1

            print(f"  -> {categories[cpath]['image_count']} gorsel, {children} alt kategori")

        await browser.close()

    return {
        "start_url": start_url,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pages_visited": pages_done,
        "categories": list(categories.values()),
        "images": records,
    }


def write_outputs(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if result["images"]:
        with (out_dir / "images.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(result["images"][0].keys()))
            w.writeheader()
            w.writerows(result["images"])

    if result["categories"]:
        with (out_dir / "categories.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(result["categories"][0].keys()))
            w.writeheader()
            w.writerows(result["categories"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Grainger kategori gorsel toplayici")
    ap.add_argument("--start", default="/category", help="baslangic yolu, orn. /category/abrasives")
    ap.add_argument("--out", default="grainger_images", help="cikti klasoru")
    ap.add_argument("--max-pages", type=int, default=50, help="taranacak azami sayfa")
    ap.add_argument("--max-depth", type=int, default=4, help="azami kategori derinligi")
    ap.add_argument("--delay", type=float, default=1.5, help="sayfa basi bekleme (sn)")
    ap.add_argument("--headful", action="store_true", help="tarayiciyi gorunur ac")
    ap.add_argument("--no-report", action="store_true", help="report.html uretme")
    args = ap.parse_args()

    result = asyncio.run(crawl(args))
    out_dir = Path(args.out)
    write_outputs(result, out_dir)

    print(f"\n{len(result['images'])} gorsel / {len(result['categories'])} kategori -> {out_dir}")

    if not args.no_report:
        from build_report import build_report  # ayni klasorde
        build_report(out_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())

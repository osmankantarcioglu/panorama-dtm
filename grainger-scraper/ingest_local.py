"""
Kendi tarayicinda actigin sayfalardan gorsel + kategori metadatasi cikarir.

Grainger otomatik tarayicilari (Akamai) engelledigi icin sayfalari sen kaydedersin,
bu script kaydedilenleri isler. Koruma atlatmaz; sadece diskteki dosyalari okur.

Sayfayi kaydetme:
  Chrome/Edge'de kategori sayfasini ac -> Ctrl+S
    "Web Page, Complete"    -> sayfa.html + sayfa_files/  (gorseller zaten diske iner)
    "Web Page, Single File" -> sayfa.mhtml                (gorseller dosyanin icinde)
  Alternatif: DevTools > Network > sag tik > "Save all as HAR with content"

Kullanim:
  python ingest_local.py --input "C:\\Users\\me\\Desktop\\grainger" --out grainger_images
  python build_report.py grainger_images        # dokumani yeniden uret
"""

from __future__ import annotations

import argparse
import csv
import email
import hashlib
import json
import mimetypes
import re
import shutil
import sys
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

try:
    import requests
except ImportError:  # uzaktan indirme opsiyonel
    requests = None

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SKIP = re.compile(r"(sprite|icon|logo|placeholder|1x1|pixel|spacer|loading)", re.I)
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}


def slugify(text: str, limit: int = 80) -> str:
    text = re.sub(r"[^\w\-]+", "-", unquote(text or "").strip().lower())
    return text.strip("-_")[:limit] or "unknown"


def category_from(url: str, fallback: str) -> tuple[str, str]:
    """(category_path, parent_path) -- URL yoksa dosya adina duser."""
    path = urlparse(url).path.strip("/") if url else ""
    if path.startswith("category"):
        path = path[len("category"):].strip("/")
    parts = [slugify(p) for p in path.split("/") if p] or [slugify(fallback)]
    return "/".join(parts), "/".join(parts[:-1])


def best_src(img) -> str:
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        cands = []
        for item in srcset.split(","):
            bits = item.strip().split()
            if bits:
                w = int(re.sub(r"\D", "", bits[1])) if len(bits) > 1 else 0
                cands.append((w, bits[0]))
        if cands:
            return max(cands)[1]
    for attr in ("src", "data-src", "data-lazy-src", "data-original"):
        if img.get(attr):
            return img[attr]
    return ""


def label_for(img) -> str:
    for node in (img.find_parent("a"), img.find_parent(["li", "article", "div"])):
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text[:120]
    return (img.get("alt") or "").strip()[:120]


# ------------------------------------------------------------------ kaynaklar


def load_html_file(path: Path) -> tuple[str, str, dict[str, bytes]]:
    """(html, page_url, {local_ref: bytes}) - 'Web Page, Complete' kaydi."""
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    url = ""
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canon and canon.get("href"):
        url = canon["href"]
    if not url:
        og = soup.find("meta", property="og:url")
        url = og["content"] if og and og.get("content") else ""
    assets: dict[str, bytes] = {}
    folder = path.with_suffix("")  # sayfa_files klasoru genelde "sayfa_files"
    for cand in (Path(str(folder) + "_files"), folder):
        if cand.is_dir():
            for f in cand.rglob("*"):
                if f.is_file() and f.suffix.lower() in IMG_EXT:
                    assets[f.name] = f.read_bytes()
    return html, url, assets


def load_mhtml_file(path: Path) -> tuple[str, str, dict[str, bytes]]:
    msg = email.message_from_bytes(path.read_bytes())
    html, url, assets = "", msg.get("Snapshot-Content-Location", ""), {}
    for part in msg.walk():
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        loc = part.get("Content-Location", "")
        if ctype == "text/html" and not html:
            html = payload.decode("utf-8", errors="ignore")
            url = url or loc
        elif ctype.startswith("image/"):
            assets[loc] = payload
    return html, url, assets


def load_har(path: Path) -> list[dict]:
    """HAR icindeki gorselleri (varsa govdesiyle) dondurur."""
    har = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    out = []
    for entry in har.get("log", {}).get("entries", []):
        resp = entry.get("response", {})
        mime = (resp.get("content", {}).get("mimeType") or "").lower()
        if not mime.startswith("image/"):
            continue
        url = entry.get("request", {}).get("url", "")
        text = resp.get("content", {}).get("text")
        body = None
        if text:
            try:
                body = b64decode(text) if resp["content"].get("encoding") == "base64" \
                    else text.encode("utf-8", "ignore")
            except Exception:
                body = None
        page_url = entry.get("pageref", "") or ""
        out.append({"url": url, "body": body, "page": page_url, "mime": mime})
    return out


# ------------------------------------------------------------------ ana akis


def ingest(args) -> dict:
    src_dir = Path(args.input)
    out_dir = Path(args.out)
    img_root = out_dir / "images"
    img_root.mkdir(parents=True, exist_ok=True)

    session = None
    if requests and not args.no_fetch:
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Referer": "https://www.grainger.com/"})

    files = [p for p in src_dir.rglob("*")
             if p.is_file() and p.suffix.lower() in (".html", ".htm", ".mhtml", ".har")]
    if not files:
        print(f"! {src_dir} altinda .html/.mhtml/.har bulunamadi")

    records, categories, seen_hash = [], {}, {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def store(cpath: str, name: str, body: bytes, url: str, meta: dict) -> None:
        sha1 = hashlib.sha1(body).hexdigest()
        if sha1 in seen_hash or len(body) < 1200:
            return
        ext = mimetypes.guess_extension(meta.get("mime", "")) or Path(urlparse(url).path).suffix
        ext = ".jpg" if ext in ("", ".jpe", ".jpeg") else ext
        target = img_root.joinpath(*cpath.split("/"))
        target.mkdir(parents=True, exist_ok=True)
        fname = f"{slugify(meta.get('label') or name, 60)}--{sha1[:8]}{ext}"
        (target / fname).write_bytes(body)
        seen_hash[sha1] = fname
        records.append({
            "file": f"images/{cpath}/{fname}",
            "image_url": url,
            "original_src": meta.get("original_src", url),
            "category_name": categories[cpath]["category_name"],
            "category_path": cpath,
            "category_url": categories[cpath]["category_url"],
            "parent_path": categories[cpath]["parent_path"],
            "parent_url": categories[cpath]["parent_url"],
            "depth": cpath.count("/"),
            "alt_text": meta.get("alt", ""),
            "item_label": meta.get("label", ""),
            "item_link": meta.get("link", ""),
            "width": meta.get("width", 0),
            "height": meta.get("height", 0),
            "bytes": len(body),
            "sha1": sha1,
            "source": meta.get("source", "local"),
            "downloaded_at": now,
        })
        categories[cpath]["image_count"] += 1

    def ensure_cat(cpath: str, parent: str, name: str, url: str) -> None:
        categories.setdefault(cpath, {
            "category_path": cpath,
            "category_name": name,
            "category_url": url,
            "parent_path": parent,
            "parent_url": (url.rsplit("/", 1)[0] if url and parent else ""),
            "depth": cpath.count("/"),
            "image_count": 0,
            "subcategory_count": 0,
        })

    for path in files:
        print(f"- {path.name}")
        if path.suffix.lower() == ".har":
            entries = load_har(path)
            cpath, parent = category_from("", path.stem)
            ensure_cat(cpath, parent, path.stem.replace("-", " ").title(), "")
            for e in entries:
                if SKIP.search(e["url"]):
                    continue
                body = e["body"]
                if body is None and session:
                    try:
                        r = session.get(e["url"], timeout=30)
                        body = r.content if r.ok else None
                    except Exception:
                        body = None
                if body:
                    store(cpath, Path(urlparse(e["url"]).path).stem, body, e["url"],
                          {"mime": e["mime"], "source": "har"})
            print(f"  -> {categories[cpath]['image_count']} gorsel")
            continue

        html, page_url, assets = (load_mhtml_file(path) if path.suffix.lower() == ".mhtml"
                                  else load_html_file(path))
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        name = (heading.get_text(strip=True) if heading else "") or path.stem.replace("-", " ").title()
        cpath, parent = category_from(page_url, path.stem)
        ensure_cat(cpath, parent, name, page_url)

        for img in soup.find_all("img"):
            src = best_src(img)
            if not src or src.startswith("data:") or SKIP.search(src):
                continue
            meta = {
                "alt": (img.get("alt") or "").strip(),
                "label": label_for(img),
                "link": (img.find_parent("a") or {}).get("href", "") if img.find_parent("a") else "",
                "width": int(re.sub(r"\D", "", str(img.get("width") or "0")) or 0),
                "height": int(re.sub(r"\D", "", str(img.get("height") or "0")) or 0),
                "original_src": src,
                "mime": mimetypes.guess_type(src)[0] or "",
            }
            body = None
            # 1) sayfa kaydinin yanindaki yerel dosya
            key = Path(urlparse(src).path).name
            if src in assets:
                body, meta["source"] = assets[src], "mhtml"
            elif key in assets:
                body, meta["source"] = assets[key], "saved-page"
            # 2) yoksa CDN'den dogrudan indirmeyi dene
            elif session and src.startswith(("http://", "https://")):
                try:
                    r = session.get(src, timeout=30)
                    if r.ok and r.headers.get("content-type", "").startswith("image/"):
                        body = r.content
                        meta["mime"] = r.headers["content-type"].split(";")[0]
                        meta["source"] = "cdn"
                except Exception:
                    body = None
            if body:
                abs_url = urljoin(page_url or "", src)
                store(cpath, key or meta["label"], body, abs_url, meta)

        # alt kategori sayimi (ayni agacta baska sayfalara link)
        subs = {a["href"] for a in soup.find_all("a", href=True) if "/category/" in a["href"]}
        categories[cpath]["subcategory_count"] = len(subs)
        print(f"  -> {categories[cpath]['image_count']} gorsel, {len(subs)} kategori linki")

    return {
        "start_url": str(src_dir),
        "generated_at": now,
        "pages_visited": len(files),
        "categories": list(categories.values()),
        "images": records,
    }


def write_outputs(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for key, fname in (("images", "images.csv"), ("categories", "categories.csv")):
        rows = result[key]
        if not rows:
            continue
        with (out_dir / fname).open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Kaydedilmis sayfalardan gorsel + kategori cikar")
    ap.add_argument("--input", required=True, help="kaydedilmis .html/.mhtml/.har dosyalarinin klasoru")
    ap.add_argument("--out", default="grainger_images", help="cikti klasoru")
    ap.add_argument("--no-fetch", action="store_true", help="eksik gorselleri CDN'den cekme")
    ap.add_argument("--no-report", action="store_true", help="report.html uretme")
    args = ap.parse_args()

    result = ingest(args)
    out_dir = Path(args.out)
    write_outputs(result, out_dir)
    print(f"\n{len(result['images'])} gorsel / {len(result['categories'])} kategori -> {out_dir}")

    if not args.no_report and result["images"]:
        from build_report import build_report
        build_report(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
manifest.json -> report.html + report.md

Indirilen gorselleri kategori agacina gore listeleyen dokumani uretir.
Tek basina da calisir:

    python build_report.py grainger_images
"""

from __future__ import annotations

import html
import json
import sys
from collections import defaultdict
from pathlib import Path

CSS = """
:root{
  --ink:#0e1116; --panel:#161b22; --line:#262d38; --text:#e6e9ee;
  --muted:#8b94a3; --accent:#ff4d2e; --accent-soft:rgba(255,77,46,.14);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--text);
  font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
code,.mono{font-family:ui-monospace,"SF Mono",Consolas,monospace}
header{padding:48px 32px 28px;border-bottom:1px solid var(--line)}
h1{margin:0 0 6px;font-size:clamp(28px,4vw,44px);letter-spacing:-.03em;font-weight:650}
.sub{color:var(--muted);font-size:14px}
.stats{display:flex;flex-wrap:wrap;gap:28px;margin-top:22px}
.stat b{display:block;font-size:26px;letter-spacing:-.02em}
.stat span{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.12em}
.tools{position:sticky;top:0;z-index:5;display:flex;gap:12px;padding:14px 32px;
  background:rgba(14,17,22,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
input[type=search]{flex:1;max-width:420px;padding:9px 12px;border-radius:8px;
  border:1px solid var(--line);background:var(--panel);color:var(--text)}
input[type=search]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
main{padding:24px 32px 80px}
section{margin:0 0 44px;scroll-margin-top:70px}
.cat{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
  padding-bottom:10px;border-bottom:1px solid var(--line)}
.cat h2{margin:0;font-size:19px;letter-spacing:-.01em}
.crumb{color:var(--muted);font-size:12px}
.count{margin-left:auto;font-size:12px;color:var(--accent);
  background:var(--accent-soft);padding:3px 9px;border-radius:99px}
.grid{display:grid;gap:14px;margin-top:16px;
  grid-template-columns:repeat(auto-fill,minmax(190px,1fr))}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;
  overflow:hidden;transition:transform .18s cubic-bezier(.2,.8,.3,1),border-color .18s}
figure:hover{transform:translateY(-2px);border-color:#3a4352}
figure img{display:block;width:100%;aspect-ratio:1;object-fit:contain;background:#fff}
figcaption{padding:9px 10px;font-size:12px;line-height:1.45}
figcaption .name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
figcaption a{color:var(--muted);font-size:11px;text-decoration:none}
figcaption a:hover,figcaption a:focus-visible{color:var(--accent);text-decoration:underline}
.empty{color:var(--muted);font-size:13px;margin-top:12px}
@media (prefers-reduced-motion:reduce){figure{transition:none}}
"""

JS = """
const q=document.getElementById('q');
q.addEventListener('input',()=>{
  const t=q.value.toLowerCase();
  document.querySelectorAll('section').forEach(s=>{
    let shown=0;
    s.querySelectorAll('figure').forEach(f=>{
      const ok=!t||f.dataset.k.includes(t);
      f.hidden=!ok; if(ok)shown++;
    });
    s.hidden=shown===0;
  });
});
"""


def build_report(out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    images = manifest["images"]
    cats = {c["category_path"]: c for c in manifest["categories"]}

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for rec in images:
        by_cat[rec["category_path"]].append(rec)

    total_bytes = sum(r["bytes"] for r in images)
    parts = [
        "<!doctype html><html lang='tr'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Grainger gorsel dokumani</title>",
        f"<style>{CSS}</style></head><body>",
        "<header><h1>Grainger kategori gorselleri</h1>",
        f"<div class='sub mono'>{html.escape(manifest['start_url'])} &middot; "
        f"{manifest['generated_at']}</div>",
        "<div class='stats'>"
        f"<div class='stat'><b>{len(images)}</b><span>gorsel</span></div>"
        f"<div class='stat'><b>{len(by_cat)}</b><span>kategori</span></div>"
        f"<div class='stat'><b>{manifest['pages_visited']}</b><span>sayfa</span></div>"
        f"<div class='stat'><b>{total_bytes/1_048_576:.1f} MB</b><span>toplam</span></div>"
        "</div></header>",
        "<div class='tools'><input id='q' type='search' "
        "placeholder='Kategori, dosya veya alt metin ara'></div><main>",
    ]

    for cpath in sorted(by_cat):
        meta = cats.get(cpath, {})
        name = meta.get("category_name") or cpath.split("/")[-1]
        recs = by_cat[cpath]
        parts.append("<section>")
        parts.append(
            f"<div class='cat'><h2>{html.escape(name)}</h2>"
            f"<span class='crumb mono'>{html.escape(cpath.replace('/', ' / '))}</span>"
            f"<span class='count'>{len(recs)}</span></div><div class='grid'>"
        )
        for r in recs:
            key = " ".join(
                str(r.get(k, "")) for k in ("item_label", "alt_text", "category_path", "file")
            ).lower()
            caption = r["item_label"] or r["alt_text"] or Path(r["file"]).stem
            parts.append(
                f"<figure data-k=\"{html.escape(key, quote=True)}\">"
                f"<img loading='lazy' src='{html.escape(r['file'])}' "
                f"alt='{html.escape(r['alt_text'] or caption)}'>"
                f"<figcaption><span class='name'>{html.escape(caption)}</span>"
                f"<a href='{html.escape(r['category_url'])}' target='_blank' rel='noopener'>"
                "kaynak sayfa</a></figcaption></figure>"
            )
        parts.append("</div></section>")

    if not images:
        parts.append("<p class='empty'>Kayitli gorsel yok.</p>")

    parts.append(f"</main><script>{JS}</script></body></html>")
    report = out_dir / "report.html"
    report.write_text("".join(parts), encoding="utf-8")

    # Markdown ozeti
    md = [f"# Grainger gorsel dokumani\n",
          f"- Kaynak: {manifest['start_url']}",
          f"- Tarih: {manifest['generated_at']}",
          f"- Gorsel: {len(images)} / Kategori: {len(by_cat)} / Sayfa: {manifest['pages_visited']}\n"]
    for cpath in sorted(by_cat):
        meta = cats.get(cpath, {})
        md.append(f"\n## {meta.get('category_name', cpath)}  \n`{cpath}` — {len(by_cat[cpath])} gorsel")
        md.append(f"Kaynak: {meta.get('category_url', '')}\n")
        for r in by_cat[cpath]:
            md.append(f"- ![{r['alt_text'] or ''}]({r['file']}) — {r['item_label'] or '-'}")
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"Dokuman hazir: {report}")
    return report


if __name__ == "__main__":
    build_report(sys.argv[1] if len(sys.argv) > 1 else "grainger_images")

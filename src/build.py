
#!/usr/bin/env python3
import os, csv, json, re, urllib.request, io
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "src"
DATA = BASE / "data"
SITE = BASE / "site"

def read_config():
    return json.loads((SRC / "config.json").read_text(encoding="utf-8"))

def fetch_csv(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        return list(csv.DictReader(io.StringIO(content)))
    except Exception as e:
        print("Fetch failed for", url, "→", e)
        return []

def read_local_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def to_float(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except:
        return 0.0

def slugify(text):
    text = str(text or "").lower()
    text = re.sub(r'[^a-z0-9\-]+', '-', text.replace(' ', '-'))
    text = re.sub(r'-+', '-', text).strip('-')
    return text or "product"

def normalize_rows(rows):
    norm = []
    for r in rows:
        item = {
            "category": r.get("category","").strip() or "",
            "product_slug": r.get("product_slug","").strip() or slugify((r.get("brand","")+" "+r.get("model","")).strip() or r.get("product_name","")),
            "product_name": r.get("product_name","").strip() or (r.get("brand","")+" "+r.get("model","")).strip(),
            "brand": r.get("brand","").strip(),
            "model": r.get("model","").strip(),
            "gtin": r.get("gtin","").strip(),
            "mpn": r.get("mpn","").strip(),
            "specs_json": r.get("specs_json","").strip(),
            "merchant": r.get("merchant","").strip(),
            "price": to_float(r.get("price","0")),
            "currency": (r.get("currency","") or "RUB").strip(),
            "shipping": to_float(r.get("shipping","0")),
            "url": r.get("url","").strip(),
            "availability": r.get("availability","").strip(),
            "updated_at": r.get("updated_at","").strip() or datetime.utcnow().isoformat()+"Z",
        }
        if item["product_slug"] and item["merchant"] and item["price"]>0 and item["url"]:
            norm.append(item)
    return norm

def group_by_product(rows):
    products = {}
    offers = defaultdict(list)
    for r in rows:
        slug = r["product_slug"]
        if slug not in products:
            try:
                specs = json.loads(r.get("specs_json") or "{}")
            except:
                specs = {}
            products[slug] = {
                "slug": slug,
                "category": r["category"],
                "name": r["product_name"],
                "brand": r["brand"],
                "model": r["model"],
                "gtin": r["gtin"],
                "mpn": r["mpn"],
                "specs": specs,
            }
        total = r["price"] + r["shipping"]
        offers[slug].append({
            "merchant": r["merchant"],
            "availability": r["availability"],
            "price": r["price"],
            "shipping": r["shipping"],
            "currency": r["currency"],
            "url": r["url"],
            "total": total,
            "updated_at": r["updated_at"],
        })
    return products, offers

def render_index(site_title, products, offers):
    tpl = (SRC / "index_tpl.html").read_text(encoding="utf-8")
    rows_html = []
    for slug, p in sorted(products.items(), key=lambda kv: (kv[1]["category"], kv[1]["name"])):
        offs = offers[slug]
        min_offer = min(offs, key=lambda o:o["total"])
        row = (
            "<tr>"
            "<td>{cat}</td>"
            "<td><a href=\"products/{slug}.html\">{name}</a><br><small>{brand} {model}</small></td>"
            "<td>{count}</td>"
            "<td>{price:.2f} {cur}</td>"
            "</tr>"
        ).format(cat=(p["category"] or "—"), slug=slug, name=p["name"], brand=p["brand"], model=p["model"], count=len(offs), price=min_offer["total"], cur=min_offer["currency"])
        rows_html.append(row)
    html = tpl.format(site_title=site_title, rows="\n".join(rows_html), year=datetime.utcnow().year)
    (SITE / "index.html").write_text(html, encoding="utf-8")

def render_product(slug, product, offs):
    tpl = (SRC / "product_tpl.html").read_text(encoding="utf-8")
    offs_sorted = sorted(offs, key=lambda o:o["total"])
    spec_lines = "".join(["<li><b>{}</b>: {}</li>".format(k, v) for k,v in (product.get("specs") or {}).items()]) or "<li>—</li>"
    offer_rows = []
    for o in offs_sorted:
        row = (
          "<tr>"
          "<td>{merchant}</td>"
          "<td>{avail}</td>"
          "<td>{price:.2f} + {ship:.2f}</td>"
          "<td><b>{total:.2f} {cur}</b></td>"
          "<td><a class='btn' href='{url}' rel='nofollow sponsored' target='_blank'>В магазин</a></td>"
          "</tr>"
        ).format(merchant=o["merchant"], avail=(o["availability"] or "—"), price=o["price"], ship=o["shipping"], total=o["total"], cur=o["currency"], url=o["url"])
        offer_rows.append(row)

    ld = {
      "@context":"https://schema.org",
      "@type":"Product",
      "name": product["name"],
      "brand":{"@type":"Brand","name": product["brand"]},
      "mpn": product["mpn"] or None,
      "gtin13": product["gtin"] or None,
      "offers":{
        "@type":"AggregateOffer",
        "priceCurrency": offs_sorted[0]["currency"],
        "lowPrice": "{:.2f}".format(offs_sorted[0]["total"]),
        "highPrice": "{:.2f}".format(max(o["total"] for o in offs_sorted)),
        "offerCount": str(len(offs_sorted))
      }
    }
    html = tpl.format(
        name=product["name"],
        brand=product["brand"],
        model=product["model"],
        spec_lines=spec_lines,
        offer_rows="\n".join(offer_rows),
        json_ld=json.dumps(ld, ensure_ascii=False)
    )
    (SITE / "products").mkdir(exist_ok=True, parents=True)
    (SITE / "products" / f"{slug}.html").write_text(html, encoding="utf-8")

def build():
    cfg = read_config()
    # For preview we just use local sample; in GitHub Actions remote feeds will be used if added
    rows = read_local_csv(BASE / cfg["fallback_local_csv"])
    norm = normalize_rows(rows)
    products, offers = group_by_product(norm)
    render_index(cfg["site"]["title"], products, offers)
    for slug, p in products.items():
        render_product(slug, p, offers[slug])
    urls = [cfg["site"]["base_url"] + "index.html"] + [cfg["site"]["base_url"] + "products/" + slug + ".html" for slug in products.keys()]
    (SITE / "sitemap.txt").write_text("\n".join(urls), encoding="utf-8")
    print("Build complete")

if __name__ == "__main__":
    build()

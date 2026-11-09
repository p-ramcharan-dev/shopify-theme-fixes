"""Light-touch storefront audit: 3-4 public page requests per store, no logins, no forms.

Usage: python audit/audit.py domain1 domain2 ...
Writes JSON results to stdout.
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, r.geturl(), body, round(time.time() - t0, 2), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, url, b"", round(time.time() - t0, 2), {}
    except Exception as e:  # noqa: BLE001
        return None, url, str(e).encode(), round(time.time() - t0, 2), {}


def page_stats(html):
    imgs = re.findall(r"<img\b[^>]*>", html, flags=re.I)
    no_alt = [i for i in imgs if not re.search(r'\balt\s*=\s*["\'][^"\']+["\']', i, flags=re.I)]
    lazy = [i for i in imgs if re.search(r'loading\s*=\s*["\']lazy', i, flags=re.I)]
    no_dims = [i for i in imgs if not re.search(r"\bwidth\s*=", i, flags=re.I)]
    scripts = re.findall(r"<script\b[^>]*>", html, flags=re.I)
    ext_scripts = [s for s in scripts if "src=" in s.lower()]
    blocking = [s for s in ext_scripts if not re.search(r"\b(async|defer)\b|type=[\"']module", s, flags=re.I)]
    hosts = sorted({m for m in re.findall(r'src=["\'](?:https?:)?//([^/"\']+)', " ".join(ext_scripts))})
    title = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, flags=re.I | re.S)
    h1 = re.findall(r"<h1\b", html, flags=re.I)
    ld_types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
    return {
        "html_kb": round(len(html) / 1024),
        "title": title.group(1).strip()[:140] if title else None,
        "meta_description": (desc.group(1).strip()[:200] if desc else None),
        "h1_count": len(h1),
        "img_count": len(imgs),
        "img_missing_alt": len(no_alt),
        "img_lazy": len(lazy),
        "img_no_width_attr": len(no_dims),
        "script_tags": len(scripts),
        "external_scripts": len(ext_scripts),
        "render_blocking_scripts": len(blocking),
        "third_party_script_hosts": [h for h in hosts if "shopify" not in h][:25],
        "jsonld_types": sorted(set(ld_types))[:15],
        "has_og_image": bool(re.search(r'property=["\']og:image', html, flags=re.I)),
        "has_viewport": bool(re.search(r'name=["\']viewport', html, flags=re.I)),
        "has_skip_link": bool(re.search(r"skip[- ]to[- ](main|content)", html, flags=re.I)),
        "review_app": [a for a in ["judge.me", "judgeme", "loox", "yotpo", "stamped", "okendo", "shopify-product-reviews", "spr-", "trustpilot", "reviews.io", "junip", "rivyo", "ali-reviews", "vitals"] if a in html.lower()],
        "emails": sorted(set(e for e in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", html) if not re.search(r"\.(png|jpg|jpeg|gif|webp|svg|js|css)$|sentry|example|shopify|wixpress", e, flags=re.I)))[:5],
    }


def audit(domain):
    out = {"domain": domain}
    status, final, body, secs, headers = get(f"https://{domain}/")
    out["status"], out["final_url"], out["home_secs"] = status, final, secs
    if status != 200:
        out["error"] = body[:200].decode("utf-8", "replace")
        return out
    html = body.decode("utf-8", "replace")
    out["is_shopify"] = "cdn.shopify.com" in html or "Shopify.theme" in html
    m = re.search(r'Shopify\.theme\s*=\s*(\{.*?\});', html, flags=re.S)
    if m:
        try:
            t = json.loads(m.group(1))
            out["theme"] = {k: t.get(k) for k in ("name", "schema_name", "schema_version", "theme_store_id")}
        except Exception:  # noqa: BLE001
            out["theme"] = m.group(1)[:200]
    cur = re.search(r'Shopify\.currency\s*=\s*\{"active":"(\w+)"', html)
    out["currency"] = cur.group(1) if cur else None
    out["home"] = page_stats(html)

    # product catalogue (public endpoint on most Shopify stores)
    time.sleep(1)
    s, _, pbody, _, _ = get(f"https://{domain}/products.json?limit=250")
    handle = None
    if s == 200:
        try:
            prods = json.loads(pbody).get("products", [])
            out["products_in_first_page"] = len(prods)
            if prods:
                no_desc = sum(1 for p in prods if len(re.sub(r"<[^>]+>", "", p.get("body_html") or "").strip()) < 80)
                no_img_alt = sum(1 for p in prods for i in p.get("images", [])[:1] if not i.get("alt"))
                one_img = sum(1 for p in prods if len(p.get("images", [])) <= 1)
                big = [i.get("width", 0) for p in prods for i in p.get("images", [])[:1]]
                out["catalog"] = {
                    "thin_descriptions_under_80_chars": no_desc,
                    "single_or_no_image": one_img,
                    "lead_image_no_alt": no_img_alt,
                    "newest_product_published": max(p.get("published_at") or "" for p in prods)[:10],
                    "oldest_product_published": min(p.get("published_at") or "9" for p in prods)[:10],
                    "median_lead_image_width": sorted(big)[len(big) // 2] if big else None,
                    "sample_titles": [p["title"] for p in prods[:6]],
                }
                handle = prods[0]["handle"]
        except Exception as e:  # noqa: BLE001
            out["products_json_error"] = str(e)[:100]
    else:
        out["products_json_status"] = s

    if handle:
        time.sleep(1)
        s, _, b, secs, _ = get(f"https://{domain}/products/{handle}")
        if s == 200:
            ph = b.decode("utf-8", "replace")
            ps = page_stats(ph)
            ps["secs"] = secs
            ps["has_product_schema"] = "Product" in ps["jsonld_types"]
            ps["has_aggregate_rating"] = "AggregateRating" in ps["jsonld_types"]
            ps["sticky_atc_hint"] = bool(re.search(r"sticky[-_ ]?(atc|add|cart|buy)", ph, flags=re.I))
            ps["shipping_or_returns_mentioned"] = bool(re.search(r"free shipping|returns?|ships? (in|within)|delivery", re.sub(r"<script.*?</script>", "", ph, flags=re.S | re.I), flags=re.I))
            out["product_page"] = ps
            out["product_url"] = f"https://{domain}/products/{handle}"

    time.sleep(1)
    for path in ("/pages/contact", "/pages/contact-us"):
        s, _, b, _, _ = get(f"https://{domain}{path}")
        if s == 200:
            ch = b.decode("utf-8", "replace")
            out["contact_page"] = path
            out["contact_emails"] = sorted(set(e for e in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", ch) if not re.search(r"\.(png|jpg|jpeg|gif|webp|svg|js|css)$|sentry|example|shopify", e, flags=re.I)))[:5]
            break
    return out


if __name__ == "__main__":
    results = []
    for d in sys.argv[1:]:
        try:
            results.append(audit(d))
        except Exception as e:  # noqa: BLE001
            results.append({"domain": d, "error": str(e)[:200]})
        time.sleep(1)
    print(json.dumps(results, indent=1))

"""Second-pass verification for shortlisted stores: confirm each claim before it goes in an email.

Usage: python audit/verify.py domain [domain ...]
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from audit import get  # noqa: E402


def text(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def psi(url):
    api = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + urllib.parse.urlencode(
        [("url", url), ("strategy", "mobile"), ("category", "performance"), ("category", "accessibility"), ("category", "seo"), ("category", "best-practices")]
    )
    try:
        with urllib.request.urlopen(api, timeout=120) as r:
            d = json.loads(r.read())
        lh = d["lighthouseResult"]
        cats = {k: round(v["score"] * 100) if v.get("score") is not None else None for k, v in lh["categories"].items()}
        a = lh["audits"]
        metrics = {k: a[k]["displayValue"] for k in ("largest-contentful-paint", "total-blocking-time", "cumulative-layout-shift", "speed-index") if k in a}
        failed = sorted(
            [(v.get("score"), k, v.get("title"), v.get("displayValue", "")) for k, v in a.items() if v.get("score") is not None and v["score"] < 0.5 and v.get("scoreDisplayMode") in ("binary", "numeric", "metricSavings")],
            key=lambda x: x[0],
        )
        return {"scores": cats, "metrics": metrics, "failed_audits": [f"{k}: {t} {dv}".strip() for _, k, t, dv in failed][:25]}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


def verify(domain):
    out = {"domain": domain}
    s, final, body, _, _ = get(f"https://{domain}/")
    html = body.decode("utf-8", "replace")
    out["final_url"] = final
    out["h1_texts"] = [text(h)[:80] for h in re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, flags=re.S | re.I)]
    out["uses_lazysizes"] = "lazyload" in html
    out["replacement_chars_in_home"] = html.count("�")
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.S | re.I)
    out["title_raw"] = m.group(1).strip() if m else None
    out["jquery"] = re.findall(r"jquery[-./]?(\d+\.\d+\.\d+)", html, flags=re.I)[:3]
    out["announcement_text"] = [text(x)[:120] for x in re.findall(r'<[^>]+class="[^"]*announcement[^"]*"[^>]*>(.*?)</(?:div|a|p)>', html, flags=re.S | re.I)][:2]
    out["footer_copyright"] = re.findall(r"(?:&copy;|©)\s*(\d{4})", html)[:2]
    out["imgs_without_alt_attr_or_empty"] = [re.search(r'(?:data-)?src=["\']([^"\']+)', i).group(1)[-60:] for i in re.findall(r"<img\b[^>]*>", html, flags=re.I) if not re.search(r'\balt\s*=\s*["\'][^"\']+["\']', i, flags=re.I) and re.search(r'(?:data-)?src=["\']([^"\']+)', i)][:6]
    out["newsletter_form"] = bool(re.search(r'contact\[tags\]"?\s*value="newsletter|/contact#contact_form|newsletter', html, flags=re.I))
    out["search_present"] = 'action="/search"' in html
    time.sleep(1)
    s, _, pb, _, _ = get(f"https://{domain}/products.json?limit=5")
    try:
        prods = json.loads(pb)["products"]
    except Exception:  # noqa: BLE001
        prods = []
    if prods:
        p = prods[0]
        out["sample_product"] = {"title": p["title"], "price": p["variants"][0]["price"], "images": len(p["images"]), "body_chars": len(text(p.get("body_html") or ""))}
        time.sleep(1)
        s, _, b, _, _ = get(f"https://{domain}/products/{p['handle']}")
        ph = b.decode("utf-8", "replace")
        out["pdp_url"] = f"https://{domain}/products/{p['handle']}"
        out["pdp_jsonld_product"] = bool(re.search(r'"@type"\s*:\s*"Product"', ph))
        out["pdp_microdata_product"] = bool(re.search(r'itemtype=["\']https?://schema.org/Product', ph, flags=re.I))
        out["pdp_review_widget"] = [a for a in ["jdgm-widget", "spr-container", "shopify-product-reviews", "loox-reviews", "yotpo-main-widget", "stamped-main-widget", "okendo-reviews-widget"] if a in ph]
        out["pdp_dynamic_checkout_button"] = "shopify-payment-button" in ph
        out["pdp_img_alt_samples"] = re.findall(r'<img\b[^>]*\balt\s*=\s*["\']([^"\']*)["\']', ph, flags=re.I)[:5]
        out["pdp_replacement_chars"] = ph.count("�")
    time.sleep(1)
    for path in ("/policies/shipping-policy", "/policies/refund-policy"):
        s, _, _, _, _ = get(f"https://{domain}{path}")
        out[path] = s
        time.sleep(0.5)
    out["psi_mobile_home"] = psi(final)
    return out


if __name__ == "__main__":
    print(json.dumps([verify(d) for d in sys.argv[1:]], indent=1, ensure_ascii=True))

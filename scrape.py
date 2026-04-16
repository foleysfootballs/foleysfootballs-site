#!/usr/bin/env python3
"""
Foley's Footballs — eBay Scraper & Site Builder
Runs daily via GitHub Actions.
Fetches each eBay listing, extracts photos + status, rebuilds index.html
"""

import json, re, time, os, urllib.request, urllib.error
from datetime import datetime

LISTINGS_FILE = "listings.json"
SOLD_FILE     = "sold.json"
OUTPUT_FILE   = "index.html"
EBAY_BASE     = "https://www.ebay.com/itm/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_listing(item_id):
    url = f"{EBAY_BASE}{item_id}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Error fetching {item_id}: {e}")
        return None

def parse_listing(html, item_id, fallback_title, fallback_price):
    if html is None:
        return None

    # Check if sold/ended
    sold = bool(re.search(r'(This listing has ended|SOLD|sold-status|item-ended)', html, re.I))

    # Extract title
    title_match = re.search(r'<h1[^>]*class="[^"]*x-item-title__mainTitle[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>', html, re.S)
    if not title_match:
        title_match = re.search(r'"og:title"\s+content="([^"]+)"', html)
    title = title_match.group(1).strip() if title_match else fallback_title
    title = re.sub(r'<[^>]+>', '', title).strip()

    # Extract price
    price_match = re.search(r'\$\s*([\d,]+\.?\d*)', html)
    price = fallback_price
    if price_match:
        try:
            price = float(price_match.group(1).replace(',', ''))
        except:
            pass

    # Extract images — full size from eBay CDN
    imgs = re.findall(r'https://i\.ebayimg\.com/images/g/[A-Za-z0-9]+/s-l(?:1600|500)\.(?:jpg|webp)', html)
    # Deduplicate while preserving order
    seen = set()
    unique_imgs = []
    for img in imgs:
        # Normalize to jpg
        img = re.sub(r'\.webp$', '.jpg', img)
        key = re.search(r'/g/([A-Za-z0-9]+)/', img)
        if key and key.group(1) not in seen:
            seen.add(key.group(1))
            unique_imgs.append(img)

    # Fallback: try s-l500
    if not unique_imgs:
        imgs500 = re.findall(r'https://i\.ebayimg\.com/images/g/[A-Za-z0-9]+/s-l(?:300|140)\.(?:jpg|webp)', html)
        for img in imgs500:
            img = re.sub(r's-l(?:300|140)', 's-l1600', img)
            img = re.sub(r'\.webp$', '.jpg', img)
            key = re.search(r'/g/([A-Za-z0-9]+)/', img)
            if key and key.group(1) not in seen:
                seen.add(key.group(1))
                unique_imgs.append(img)

    return {
        "id":     item_id,
        "title":  title,
        "price":  price,
        "images": unique_imgs[:8],  # cap at 8 photos
        "sold":   sold,
        "url":    f"{EBAY_BASE}{item_id}",
    }

def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def tag_for_title(title):
    """Return a display tag based on listing title keywords."""
    t = title.upper()
    if "JETS" in t and "TEAM ISSUED" in t: return ("Team Issued", "special")
    if "100 YR" in t or "100YR" in t:      return ("100th Season", "special")
    if "2X RAMS" in t:                      return ("Double Rams", "special")
    if "RAMS" in t or "LA RAMS" in t:       return ("Rams Logo", "logo")
    if "JETS" in t:                          return ("Jets", "logo")
    return ("Game-Ready Duke", "standard")

def build_html(active, sold_list):
    tag_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── TILE HTML helpers ──────────────────────────────────────
    def thumb_strip(imgs):
        if len(imgs) <= 1:
            return ""
        html = '<div class="tile-thumbs">'
        for i, img in enumerate(imgs[:5]):
            active_cls = " active" if i == 0 else ""
            html += f'<img class="tile-thumb{active_cls}" src="{img}" alt="photo {i+1}" onclick="swapImg(this,\'{img}\')" loading="lazy"/>'
        html += '</div>'
        return html

    def active_tile(item):
        tag_label, tag_type = tag_for_title(item["title"])
        badge_cls = "b-special" if tag_type in ("special","logo") else "b-site"
        first_img = item["images"][0] if item["images"] else ""
item_id = item['id']
        img_html = f'<img class="tile-main-img" src="{first_img}" alt="ball photo" loading="lazy" onclick="openLightbox(\'{item_id}\',0)"/>' if first_img else '<div class="tile-img-placeholder">&#x1F3C8;</div>'
        discount_url = f"/contact.html?topic=site&item={item['id']}"
        ebay_url     = item["url"]
        return f"""
        <div class="tile tile-active" id="tile-{item['id']}">
          <div class="tile-type">
            <span style="color:var(--muted)">Wilson The Duke</span>
            <span class="tile-badge {badge_cls}">{tag_label}</span>
          </div>
          <div class="tile-img-wrap">
            {img_html}
          </div>
          {thumb_strip(item["images"])}
          <div class="tile-body">
            <div class="tile-price">${item['price']:.0f}</div>
            <div class="tile-sub">Hand-conditioned &#xB7; NFL-sourced &#xB7; PSA verified</div>
          </div>
          <div class="tile-footer">
            <a class="tile-btn-ebay" href="{ebay_url}" target="_blank">Buy on eBay &#x2197;</a>
            <a class="tile-btn-discount" href="{discount_url}">Buy Direct &#x2193;</a>
          </div>
        </div>"""

    def sold_tile(item):
        first_img = item["images"][0] if item["images"] else ""
        img_html = f'<img class="tile-main-img sold-img" src="{first_img}" alt="sold" loading="lazy"/>' if first_img else '<div class="tile-img-placeholder">&#x1F3C8;</div>'
        tag_label, tag_type = tag_for_title(item["title"])
        return f"""
        <div class="tile tile-sold" id="tile-{item['id']}">
          <div class="tile-type">
            <span style="color:var(--muted)">Wilson The Duke</span>
            <span class="tile-badge b-sold">Sold</span>
          </div>
          <div class="tile-img-wrap sold-wrap">
            {img_html}
            <div class="sold-overlay">SOLD</div>
          </div>
          <div class="tile-body">
            <div class="tile-price" style="color:var(--muted)">${item['price']:.0f}</div>
            <div class="tile-sub">{tag_label} &#xB7; No longer available</div>
          </div>
        </div>"""

    active_tiles_html = "\n".join(active_tile(i) for i in active)   if active   else '<p style="color:var(--muted);font-size:0.9rem">No active listings right now &#x2014; check back soon or <a href="/contact.html" style="color:var(--gold)">message us</a>.</p>'
    sold_tiles_html   = "\n".join(sold_tile(i)   for i in sold_list) if sold_list else ""
    sold_section = f"""
      <div class="section-label" style="margin-top:40px;margin-bottom:12px">
        Recently Sold
        <span style="font-size:0.65rem;color:var(--muted)">{len(sold_list)} ball{'s' if len(sold_list)!=1 else ''}</span>
      </div>
      <div class="tile-grid sold-grid">{sold_tiles_html}</div>
    """ if sold_list else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Foley's Footballs &#x2014; Game-Ready NFL Footballs</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow+Condensed:ital,wght@0,400;0,600;0,700;1,400&family=Barlow:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0F0A05;--surface:#1A100A;--surface2:#231408;--border:rgba(212,168,71,0.12);--border2:rgba(212,168,71,0.25);--gold:#D4A847;--gold2:#B8882E;--leather:#7B4A1E;--cream:#F5EFE6;--text:rgba(245,239,230,0.9);--muted:rgba(245,239,230,0.45);--faint:rgba(245,239,230,0.18);--sidebar:200px}}
html{{scroll-behavior:smooth}}
body{{font-family:'Barlow',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;overflow-x:hidden}}
.sidebar{{width:var(--sidebar);min-width:var(--sidebar);height:100vh;position:sticky;top:0;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}}
.sidebar-logo{{padding:22px 20px 18px;border-bottom:1px solid var(--border)}}
.logo-mark{{font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:0.06em;color:var(--gold);line-height:1}}
.logo-mark span{{color:var(--cream)}}
.logo-sub{{font-family:'Barlow Condensed',sans-serif;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--muted);margin-top:4px}}
.nav{{flex:1;padding:14px 0;overflow-y:auto}}
.nav-group{{font-family:'Barlow Condensed',sans-serif;font-size:9px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:var(--faint);padding:14px 20px 5px}}
.nav-link{{display:flex;align-items:center;gap:10px;padding:9px 20px;font-family:'Barlow Condensed',sans-serif;font-size:0.8rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:var(--muted);text-decoration:none;cursor:pointer;border-left:2px solid transparent;transition:all 0.15s}}
.nav-link:hover{{color:var(--cream);background:rgba(255,255,255,0.03)}}
.nav-link.active{{color:var(--gold);border-left-color:var(--gold);background:rgba(212,168,71,0.07)}}
.nav-icon{{font-size:13px;width:16px;text-align:center;flex-shrink:0}}
.sidebar-bottom{{padding:16px 20px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:8px}}
.ebay-btn{{display:block;text-align:center;text-decoration:none;font-family:'Barlow Condensed',sans-serif;font-size:0.7rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:var(--gold);border:1px solid var(--border2);padding:9px 12px;transition:all 0.15s}}
.ebay-btn:hover{{background:rgba(212,168,71,0.1)}}
.trust-pill{{font-family:'Barlow Condensed',sans-serif;font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);text-align:center}}
.trust-dot{{color:var(--gold);margin-right:4px}}
.main{{flex:1;min-width:0;display:flex;flex-direction:column}}
.topbar{{position:sticky;top:0;z-index:50;background:rgba(15,10,5,0.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 28px;height:52px;display:flex;align-items:center;justify-content:space-between}}
.topbar-left{{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:600;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted);display:flex;align-items:center;gap:16px}}
.topbar-sep{{color:var(--faint)}}
.topbar-right{{display:flex;align-items:center;gap:10px}}
.btn-sm{{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;text-decoration:none;padding:7px 16px;cursor:pointer;border:none;transition:all 0.15s}}
.btn-outline{{background:transparent;color:var(--muted);border:1px solid var(--faint)}}
.btn-outline:hover{{color:var(--cream);border-color:var(--border2)}}
.btn-gold{{background:var(--gold);color:#0F0A05}}
.btn-gold:hover{{background:var(--gold2)}}
.content{{flex:1;padding:24px 28px 48px;overflow-y:auto}}
.page{{display:none}}.page.active{{display:block}}
/* HERO */
.hero-strip{{background:var(--surface);border:1px solid var(--border);padding:28px 32px;margin-bottom:20px;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:center;position:relative;overflow:hidden}}
.hero-strip::before{{content:'&#x1F3C8;';position:absolute;right:140px;top:50%;transform:translateY(-50%);font-size:5rem;opacity:0.06;pointer-events:none}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:var(--gold);margin-bottom:8px;display:flex;align-items:center;gap:10px}}
.hero-eyebrow::before{{content:'';width:20px;height:1px;background:var(--gold)}}
.hero-h1{{font-family:'Bebas Neue',sans-serif;font-size:clamp(2rem,4vw,3.2rem);line-height:0.95;letter-spacing:0.02em;color:var(--cream);margin-bottom:10px}}
.hero-h1 em{{font-style:normal;color:var(--gold)}}
.hero-sub{{font-size:0.88rem;line-height:1.65;color:var(--muted);max-width:500px}}
.hero-stats{{display:flex;gap:24px;flex-shrink:0;padding-left:24px;border-left:1px solid var(--border)}}
.hstat{{text-align:center}}
.hstat-val{{font-family:'Bebas Neue',sans-serif;font-size:1.8rem;color:var(--gold);line-height:1}}
.hstat-label{{font-family:'Barlow Condensed',sans-serif;font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:var(--muted);margin-top:2px}}
/* SECTION LABEL */
.section-label{{font-family:'Barlow Condensed',sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;justify-content:space-between}}
/* MARQUEE */
.marquee-wrap{{background:var(--leather);padding:9px 0;overflow:hidden;white-space:nowrap;margin-bottom:20px}}
.marquee-inner{{display:inline-flex;animation:marquee 28s linear infinite}}
@keyframes marquee{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.marquee-item{{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:var(--cream);padding:0 24px;opacity:0.85}}
.marquee-sep{{color:var(--gold);opacity:1}}
/* TILE GRID */
.tile-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;margin-bottom:28px}}
.tile{{background:var(--surface);border:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;transition:border-color 0.18s,transform 0.18s}}
.tile-active:hover{{border-color:var(--border2);transform:translateY(-2px)}}
.tile-type{{font-family:'Barlow Condensed',sans-serif;font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;padding:12px 14px 0;display:flex;align-items:center;justify-content:space-between}}
.tile-badge{{font-family:'Barlow Condensed',sans-serif;font-size:9px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;padding:3px 8px}}
.b-site{{background:rgba(212,168,71,0.12);color:#D4A847}}
.b-special{{background:rgba(123,74,30,0.3);color:#F5EFE6}}
.b-logo{{background:rgba(29,78,216,0.15);color:#93C5FD}}
.b-sold{{background:rgba(6,95,70,0.2);color:#6EE7B7}}
/* TILE IMAGE */
.tile-img-wrap{{position:relative;width:100%;aspect-ratio:4/3;overflow:hidden;background:var(--surface2)}}
.tile-main-img{{width:100%;height:100%;object-fit:cover;transition:opacity 0.2s;cursor:zoom-in}}
.tile-main-img:hover{{opacity:0.9}}
.sold-img{{filter:brightness(0.5)}}
.sold-wrap{{position:relative}}
.sold-overlay{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:'Bebas Neue',sans-serif;font-size:2rem;letter-spacing:0.12em;color:rgba(245,239,230,0.9);pointer-events:none}}
.tile-img-placeholder{{width:100%;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;font-size:3rem;background:var(--surface2);opacity:0.3}}
/* THUMBNAILS */
.tile-thumbs{{display:flex;gap:4px;padding:8px 14px 0;flex-wrap:wrap}}
.tile-thumb{{width:44px;height:44px;object-fit:cover;cursor:pointer;opacity:0.5;border:1px solid transparent;transition:opacity 0.15s}}
.tile-thumb:hover,.tile-thumb.active{{opacity:1;border-color:var(--gold)}}
/* TILE BODY */
.tile-body{{padding:12px 14px 8px}}
.tile-price{{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;color:var(--gold);line-height:1;margin-bottom:4px}}
.tile-sub{{font-size:0.75rem;color:var(--muted);line-height:1.4}}
/* TILE FOOTER — two buttons */
.tile-footer{{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--border);margin-top:auto}}
.tile-btn-ebay,.tile-btn-discount{{font-family:'Barlow Condensed',sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;text-align:center;padding:10px 6px;text-decoration:none;transition:all 0.15s}}
.tile-btn-ebay{{color:#93C5FD;border-right:1px solid var(--border)}}
.tile-btn-ebay:hover{{background:rgba(147,197,253,0.08)}}
.tile-btn-discount{{color:var(--gold)}}
.tile-btn-discount:hover{{background:rgba(212,168,71,0.08)}}
/* SOLD GRID */
.sold-grid{{opacity:0.7}}
/* LIGHTBOX */
.lightbox{{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,0.93);align-items:center;justify-content:center}}
.lightbox.open{{display:flex}}
.lightbox-img{{max-width:90vw;max-height:85vh;object-fit:contain}}
.lightbox-close{{position:absolute;top:20px;right:24px;font-size:1.8rem;color:var(--cream);cursor:pointer;background:none;border:none;opacity:0.7;line-height:1}}
.lightbox-close:hover{{opacity:1}}
.lightbox-prev,.lightbox-next{{position:absolute;top:50%;transform:translateY(-50%);font-size:2.5rem;color:var(--cream);cursor:pointer;background:none;border:none;opacity:0.55;padding:16px;line-height:1}}
.lightbox-prev{{left:8px}}.lightbox-next{{right:8px}}
.lightbox-prev:hover,.lightbox-next:hover{{opacity:1}}
.lightbox-counter{{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);font-family:'Barlow Condensed',sans-serif;font-size:0.75rem;letter-spacing:0.14em;text-transform:uppercase;color:var(--muted)}}
/* PROCESS / STORY / REVIEWS — same as before */
.process-intro{{font-size:0.9rem;line-height:1.7;color:var(--muted);max-width:580px;margin-bottom:24px}}
.process-steps{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:24px}}
.process-step{{background:var(--surface);border:1px solid var(--border);border-top:2px solid var(--leather);padding:20px 18px}}
.step-num{{font-family:'Bebas Neue',sans-serif;font-size:2.5rem;color:rgba(212,168,71,0.12);line-height:1;margin-bottom:10px}}
.step-title{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--cream);margin-bottom:8px}}
.step-body{{font-size:0.82rem;line-height:1.6;color:var(--muted)}}
.psa-notice{{background:var(--surface);border:1px solid var(--border2);border-left:3px solid var(--gold);padding:18px 22px;max-width:600px}}
.psa-notice-label{{font-family:'Barlow Condensed',sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:var(--gold);margin-bottom:8px}}
.psa-notice p{{font-size:0.82rem;line-height:1.7;color:var(--muted)}}
.psa-notice p+p{{margin-top:8px}}
.story-body{{max-width:560px}}
.story-h{{font-family:'Bebas Neue',sans-serif;font-size:2.4rem;line-height:0.95;letter-spacing:0.02em;color:var(--cream);margin-bottom:18px}}
.story-body p{{font-size:0.9rem;line-height:1.75;color:var(--muted);margin-bottom:14px}}
.story-body strong{{color:var(--cream);font-weight:500}}
.btn-shop{{font-family:'Barlow Condensed',sans-serif;font-size:0.78rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;background:var(--gold);color:#0F0A05;border:none;padding:12px 24px;cursor:pointer;transition:all 0.15s;display:inline-block;text-decoration:none}}
.btn-shop:hover{{background:var(--gold2)}}
.ratings-card{{background:var(--surface);border:1px solid var(--border);padding:20px 24px;margin-bottom:20px;display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:center}}
.ratings-score{{text-align:center;padding-right:24px;border-right:1px solid var(--border)}}
.ratings-big{{font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:var(--gold);line-height:1}}
.ratings-stars{{color:var(--gold);font-size:14px;letter-spacing:3px;margin:4px 0}}
.ratings-count{{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted)}}
.ratings-bars{{display:flex;flex-direction:column;gap:10px}}
.rating-row{{display:flex;align-items:center;gap:12px}}
.rating-label{{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:var(--muted);width:160px;flex-shrink:0}}
.rating-bar-wrap{{flex:1;height:4px;background:rgba(245,239,230,0.08)}}
.rating-bar{{height:100%;background:var(--gold)}}
.rating-val{{font-family:'Bebas Neue',sans-serif;font-size:1rem;color:var(--gold);width:28px;text-align:right;flex-shrink:0}}
.reviews-featured{{background:var(--surface);border:1px solid var(--border2);border-left:3px solid var(--gold);padding:20px 24px;margin-bottom:20px}}
.reviews-featured-label{{font-family:'Barlow Condensed',sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:var(--gold);margin-bottom:14px}}
.reviews-featured-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.review-card{{background:var(--surface);border:1px solid var(--border);padding:20px}}
.review-stars{{color:var(--gold);font-size:11px;letter-spacing:2px;margin-bottom:10px}}
.review-text{{font-size:0.85rem;line-height:1.65;color:var(--muted);font-style:italic;margin-bottom:14px}}
.review-author{{font-family:'Barlow Condensed',sans-serif;font-size:0.72rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--leather)}}
.review-source{{font-size:0.68rem;color:var(--faint);margin-top:2px}}
.reviews-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
.auto-update-badge{{font-family:'Barlow Condensed',sans-serif;font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);text-align:right;padding:6px 0 0}}
@media(max-width:780px){{.sidebar{{display:none}}.hero-strip{{grid-template-columns:1fr}}.hero-stats{{border-left:none;border-top:1px solid var(--border);padding-left:0;padding-top:16px}}.ratings-card{{grid-template-columns:1fr}}.ratings-score{{border-right:none;border-bottom:1px solid var(--border);padding-right:0;padding-bottom:16px}}.reviews-featured-grid{{grid-template-columns:1fr}}.content{{padding:16px}}}}
</style>
</head>
<body>

<!-- LIGHTBOX -->
<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <button class="lightbox-close" onclick="closeLightboxBtn()">&#x2715;</button>
  <button class="lightbox-prev" onclick="lightboxNav(-1)">&#8249;</button>
  <img class="lightbox-img" id="lightbox-img" src="" alt="Ball photo"/>
  <button class="lightbox-next" onclick="lightboxNav(1)">&#8250;</button>
  <div class="lightbox-counter" id="lightbox-counter"></div>
</div>

<!-- SIDEBAR -->
<aside class="sidebar">
  <div class="sidebar-logo">
    <div class="logo-mark">Foley&#x2019;s <span>Footballs</span></div>
    <div class="logo-sub">foleysfootballs.com</div>
  </div>
  <nav class="nav">
    <div class="nav-group">Store</div>
    <div class="nav-link active" onclick="nav('home',this)"><span class="nav-icon">&#x2B21;</span>Home</div>
    <div class="nav-link" onclick="nav('process',this)"><span class="nav-icon">&#x25CE;</span>The Process</div>
    <div class="nav-link" onclick="nav('reviews',this)"><span class="nav-icon">&#x2605;</span>Reviews</div>
    <div class="nav-link" onclick="nav('story',this)"><span class="nav-icon">&#x25F7;</span>Our Story</div>
    <div class="nav-group">More</div>
    <a class="nav-link" href="/contact.html"><span class="nav-icon">&#x2709;</span>Contact</a>
  </nav>
  <div class="sidebar-bottom">
    <a class="ebay-btn" href="https://www.ebay.com/usr/foleysfootballs" target="_blank">&#x2197; View eBay Store</a>
    <div class="trust-pill"><span class="trust-dot">&#x25CF;</span>Registered in Pennsylvania</div>
  </div>
</aside>

<!-- MAIN -->
<div class="main">
  <header class="topbar">
    <div class="topbar-left">
      <span>Authentic NFL Footballs</span><span class="topbar-sep">&#xB7;</span>
      <span>Hand-Conditioned</span><span class="topbar-sep">&#xB7;</span>
      <span>Game-Ready</span>
    </div>
    <div class="topbar-right">
      <button class="btn-sm btn-outline" onclick="nav('process',document.querySelectorAll('.nav-link')[1])">The Process</button>
      <a class="btn-sm btn-gold" href="/contact.html">Buy Direct</a>
    </div>
  </header>

  <div class="content">

    <!-- HOME -->
    <div id="page-home" class="page active">
      <div class="hero-strip">
        <div>
          <div class="hero-eyebrow">NFL-Sourced &#xB7; PSA Authenticated &#xB7; PA Registered Business</div>
          <h1 class="hero-h1">Game-Ready<br><em>From Day One.</em></h1>
          <p class="hero-sub">Every Wilson &#x201C;The Duke&#x201D; we sell is hand-conditioned through a professional multi-step process. No break-in time. No guesswork. The real NFL experience, right out of the box.</p>
        </div>
        <div class="hero-stats">
          <div class="hstat"><div class="hstat-val">128</div><div class="hstat-label">Sold</div></div>
          <div class="hstat"><div class="hstat-val">197</div><div class="hstat-label">Feedback</div></div>
          <div class="hstat"><div class="hstat-val">100%</div><div class="hstat-label">Positive</div></div>
        </div>
      </div>

      <div class="marquee-wrap"><div class="marquee-inner">
        <span class="marquee-item">Authentic Wilson &#x201C;The Duke&#x201D;</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">NFL-Sourced Inventory</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">PSA Authenticated</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">Hand-Conditioned</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">197 Five-Star Reviews</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">128 Sold</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">Registered PA Business</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">Authentic Wilson &#x201C;The Duke&#x201D;</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">NFL-Sourced Inventory</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">PSA Authenticated</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">Hand-Conditioned</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">197 Five-Star Reviews</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">128 Sold</span><span class="marquee-item marquee-sep">&#x2726;</span>
        <span class="marquee-item">Registered PA Business</span><span class="marquee-item marquee-sep">&#x2726;</span>
      </div></div>

      <div class="section-label">
        Available Now &#x2014; {len(active)} Ball{'s' if len(active)!=1 else ''}
        <span class="auto-update-badge">Auto-updated &#xB7; {tag_time}</span>
      </div>
      <div class="tile-grid">
        {active_tiles_html}
      </div>

      {sold_section}
    </div>

    <!-- PROCESS -->
    <div id="page-process" class="page">
      <div class="section-label" style="margin-bottom:16px">The Conditioning Process</div>
      <p class="process-intro">A brand new NFL football right out of the bag is stiff, slippery, and nothing like what you see on Sundays. Every ball we sell goes through the same multi-step process used by NFL equipment managers.</p>
      <div class="process-steps">
        <div class="process-step"><div class="step-num">01</div><div class="step-title">Selection</div><div class="step-body">Hand-picked authentic Wilson &#x201C;The Duke&#x201D; NFL footballs &#x2014; the same model used in every NFL game. Sourced directly from the NFL.</div></div>
        <div class="process-step"><div class="step-num">02</div><div class="step-title">Conditioning</div><div class="step-body">Leather panels brushed and treated with conditioner to open the pores, naturally softening and darkening the leather.</div></div>
        <div class="process-step"><div class="step-num">03</div><div class="step-title">Grip &amp; Tack</div><div class="step-body">Tack agents and grip compounds worked in by hand. Laces treated separately for maximum feel on the spiral.</div></div>
        <div class="process-step"><div class="step-num">04</div><div class="step-title">Inspection</div><div class="step-body">Each ball inflated to regulation pressure and inspected by hand. If it doesn&#x2019;t pass our feel test, it doesn&#x2019;t ship.</div></div>
      </div>
      <div class="psa-notice">
        <div class="psa-notice-label">About the PSA Authentication Sticker</div>
        <p>Many of our balls were originally sourced from the NFL with PSA-authenticated player signatures. The autograph has faded through conditioning &#x2014; you are purchasing a conditioned, game-ready football, not a signed collectible.</p>
        <p>The PSA sticker stays on as our inventory tracking system &#x2014; it&#x2019;s how we guarantee the ball in the photos is the exact ball that ships to you.</p>
      </div>
    </div>

    <!-- REVIEWS -->
    <div id="page-reviews" class="page">
      <div class="ratings-card">
        <div class="ratings-score">
          <div class="ratings-big">5.0</div>
          <div class="ratings-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div>
          <div class="ratings-count">197 Feedback &#xB7; 100% Positive</div>
        </div>
        <div class="ratings-bars">
          <div class="rating-row"><span class="rating-label">Accurate Description</span><div class="rating-bar-wrap"><div class="rating-bar" style="width:100%"></div></div><span class="rating-val">5.0</span></div>
          <div class="rating-row"><span class="rating-label">Shipping Speed</span><div class="rating-bar-wrap"><div class="rating-bar" style="width:100%"></div></div><span class="rating-val">5.0</span></div>
          <div class="rating-row"><span class="rating-label">Communication</span><div class="rating-bar-wrap"><div class="rating-bar" style="width:100%"></div></div><span class="rating-val">5.0</span></div>
          <div class="rating-row"><span class="rating-label">Shipping Cost</span><div class="rating-bar-wrap"><div class="rating-bar" style="width:96%"></div></div><span class="rating-val">4.8</span></div>
        </div>
      </div>
      <div class="reviews-featured">
        <div class="reviews-featured-label">Verified eBay Reviews</div>
        <div class="reviews-featured-grid">
          <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Super easy to work with&#x2026;shipped immediately quick shipping well packaged&#x2026;I think it took 2 days&#x2026;awesome ebayer&#x2026;item as described perfectly!! Love my football&#x201D;</div><div class="review-author">y***s</div><div class="review-source">eBay Verified Purchase &#xB7; Past 6 months</div></div>
          <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;High quality item. Came exactly as seller described. Quick shipping. Good packaging.&#x201D;</div><div class="review-author">d***n</div><div class="review-source">eBay Verified Purchase &#xB7; Colts Team Issued Ball</div></div>
          <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Football came just as the picture shown. Beautiful piece to add to the collection. Great seller and would buy from them again.&#x201D;</div><div class="review-author">f***e</div><div class="review-source">eBay Verified Purchase &#xB7; Super Bowl LVII Ball</div></div>
        </div>
      </div>
      <div class="section-label" style="margin-bottom:12px">More Reviews</div>
      <div class="reviews-grid">
        <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Threw it the second it arrived. Feels incredible &#x2014; soft, tacky, and spirals beautifully.&#x201D;</div><div class="review-author">Mike T.</div><div class="review-source">eBay Verified Purchase</div></div>
        <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Bought this for my son&#x2019;s birthday. He couldn&#x2019;t believe it was a real NFL ball. Perfect gift.&#x201D;</div><div class="review-author">Sarah K.</div><div class="review-source">eBay Verified Purchase</div></div>
        <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;I&#x2019;ve tried breaking in leather footballs myself. This arrived better than anything I&#x2019;ve done on my own.&#x201D;</div><div class="review-author">James R.</div><div class="review-source">eBay Verified Purchase</div></div>
        <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Fast shipping, great communication, ball looks and feels exactly as described. Will buy again.&#x201D;</div><div class="review-author">Dave M.</div><div class="review-source">eBay Verified Purchase</div></div>
        <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Legitimately game-ready out of the box. The leather is soft and tackiness is perfect.&#x201D;</div><div class="review-author">Chris B.</div><div class="review-source">eBay Verified Purchase</div></div>
        <div class="review-card"><div class="review-stars">&#x2605;&#x2605;&#x2605;&#x2605;&#x2605;</div><div class="review-text">&#x201C;Bought two and gave one as a gift. Both went over extremely well.&#x201D;</div><div class="review-author">Tyler W.</div><div class="review-source">eBay Verified Purchase</div></div>
      </div>
    </div>

    <!-- STORY -->
    <div id="page-story" class="page">
      <div class="story-body">
        <div class="story-h">Born Out<br>of Frustration.</div>
        <p>Every football fan knows the feeling. You finally get your hands on a real Wilson &#x201C;The Duke&#x201D; and it feels nothing like what the pros throw. Stiff leather. Slippery surface. No grip.</p>
        <p><strong>Foley&#x2019;s Footballs started with one simple question: what if you could skip straight to the good part?</strong></p>
        <p>We&#x2019;re a small, registered Pennsylvania business built around one thing &#x2014; taking authentic NFL footballs and professionally conditioning them so you get a game-ready ball from day one.</p>
        <p>128 sold. 197 feedback. 100% positive. Every ball handled personally and shipped with care.</p>
        <a class="btn-shop" href="/contact.html" style="margin-top:8px">Buy Direct &#x2014; No eBay Fees</a>
      </div>
    </div>

  </div>
</div>

<script>
// Lightbox
var lbImgs={{}};var lbIdx=0;var lbId='';
function openLightbox(id,idx){{lbId=id;lbIdx=idx;var imgs=lbImgs[id]||[];if(!imgs.length)return;document.getElementById('lightbox-img').src=imgs[lbIdx];document.getElementById('lightbox-counter').textContent=(lbIdx+1)+' / '+imgs.length;document.getElementById('lightbox').classList.add('open');document.body.style.overflow='hidden'}}
function closeLightboxBtn(){{document.getElementById('lightbox').classList.remove('open');document.body.style.overflow=''}}
function closeLightbox(e){{if(e.target===document.getElementById('lightbox'))closeLightboxBtn()}}
function lightboxNav(dir){{var imgs=lbImgs[lbId]||[];lbIdx=(lbIdx+dir+imgs.length)%imgs.length;document.getElementById('lightbox-img').src=imgs[lbIdx];document.getElementById('lightbox-counter').textContent=(lbIdx+1)+' / '+imgs.length}}
document.addEventListener('keydown',function(e){{var lb=document.getElementById('lightbox');if(!lb.classList.contains('open'))return;if(e.key==='ArrowRight')lightboxNav(1);if(e.key==='ArrowLeft')lightboxNav(-1);if(e.key==='Escape')closeLightboxBtn()}});
function swapImg(el,src){{var wrap=el.closest('.tile');wrap.querySelector('.tile-main-img').src=src;wrap.querySelectorAll('.tile-thumb').forEach(function(t){{t.classList.remove('active')}});el.classList.add('active')}}
function nav(pageId,navEl){{document.querySelectorAll('.page').forEach(function(p){{p.classList.remove('active')}});document.querySelectorAll('.nav-link').forEach(function(n){{n.classList.remove('active')}});var p=document.getElementById('page-'+pageId);if(p)p.classList.add('active');if(navEl)navEl.classList.add('active');document.querySelector('.content').scrollTop=0}}
// Image registry for lightbox
var imgData = {json.dumps({item['id']: item['images'] for item in active})};
Object.assign(lbImgs, imgData);
</script>
</body>
</html>"""

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    print(f"=== Foley's Footballs Scraper — {datetime.utcnow().isoformat()} ===")

    listings_data = load_json(LISTINGS_FILE, {"listings": []})
    sold_data     = load_json(SOLD_FILE,     {"sold": []})

    active_ids = {item["id"] for item in listings_data["listings"]}
    sold_ids   = {item["id"] for item in sold_data["sold"]}

    active_results = []
    newly_sold     = []

    for item in listings_data["listings"]:
        print(f"Fetching {item['id']}...")
        html = fetch_listing(item["id"])
        result = parse_listing(html, item["id"], item["title"], item["price"])

        if result is None:
            print(f"  Could not fetch — keeping as active")
            active_results.append({"id": item["id"], "title": item["title"],
                                   "price": item["price"], "images": [], "sold": False,
                                   "url": f"{EBAY_BASE}{item['id']}"})
            continue

        if result["sold"]:
            print(f"  SOLD — moving to sold section")
            newly_sold.append(result)
        else:
            print(f"  Active — ${result['price']} — {len(result['images'])} images")
            active_results.append(result)

        time.sleep(1.5)  # polite delay

    # Update sold.json — add newly sold, keep last 20
    existing_sold = sold_data["sold"]
    newly_sold_ids = {i["id"] for i in newly_sold}
    combined_sold = newly_sold + [i for i in existing_sold if i["id"] not in newly_sold_ids]
    combined_sold = combined_sold[:20]  # keep last 20 sold
    save_json(SOLD_FILE, {"sold": combined_sold})

    # Remove sold items from listings.json
    remaining = [i for i in listings_data["listings"] if i["id"] not in newly_sold_ids]
    save_json(LISTINGS_FILE, {"listings": remaining})

    # Build site
    html = build_html(active_results, combined_sold)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDone. Active: {len(active_results)} | Sold: {len(combined_sold)}")
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
One-time script: Creates all Stripe products + payment links
Saves payment links back to listings.json
Run via GitHub Actions with STRIPE_SECRET_KEY set
"""

import json, os, urllib.request, urllib.parse, urllib.error

STRIPE_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
if not STRIPE_KEY:
    raise SystemExit("ERROR: STRIPE_SECRET_KEY not set")

def stripe_post(endpoint, data):
    url = f"https://api.stripe.com/v1/{endpoint}"
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Authorization', f'Bearer {STRIPE_KEY}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Stripe error {e.code}: {body[:200]}")
        return None

def stripe_get(endpoint):
    url = f"https://api.stripe.com/v1/{endpoint}"
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {STRIPE_KEY}')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  GET error: {e}")
        return None

# Ball definitions
BALLS = [
    {"id": "236712073331", "title": "Game-Ready Duke",     "price": 175, "tag": "Standard",    "notes": "Hand-conditioned Wilson The Duke NFL game ball. NFL-sourced, PSA verified provenance. Game-ready from day one."},
    {"id": "236712078029", "title": "Game-Ready Duke",     "price": 175, "tag": "Standard",    "notes": "Hand-conditioned Wilson The Duke NFL game ball. NFL-sourced, PSA verified provenance. Game-ready from day one."},
    {"id": "236712089570", "title": "Game-Ready Duke",     "price": 175, "tag": "Standard",    "notes": "Hand-conditioned Wilson The Duke NFL game ball. NFL-sourced, PSA verified provenance. Game-ready from day one."},
    {"id": "236712095546", "title": "Game-Ready Duke",     "price": 175, "tag": "Standard",    "notes": "Hand-conditioned Wilson The Duke NFL game ball. NFL-sourced, PSA verified provenance. Game-ready from day one."},
    {"id": "236608126994", "title": "Game-Ready Duke",     "price": 189, "tag": "Standard",    "notes": "Hand-conditioned Wilson The Duke NFL game ball. NFL-sourced, PSA verified provenance. Game-ready from day one."},
    {"id": "236568479439", "title": "Rams Logo Duke",      "price": 196, "tag": "Rams Logo",   "notes": "Wilson The Duke with Rams logo stamp. Hand-conditioned, NFL-sourced, PSA verified."},
    {"id": "236568493852", "title": "LA Rams Duke",        "price": 181, "tag": "Rams Logo",   "notes": "Wilson The Duke with LA Rams logo stamp. Hand-conditioned, NFL-sourced, PSA verified."},
    {"id": "236568496267", "title": "Rams Logo Duke",      "price": 181, "tag": "Rams Logo",   "notes": "Wilson The Duke with Rams logo stamp. Hand-conditioned, NFL-sourced, PSA verified."},
    {"id": "236513442391", "title": "Jets Team Issued",    "price": 225, "tag": "Team Issued", "notes": "New York Jets team issued Wilson The Duke NFL game ball. Authenticated, hand-conditioned."},
    {"id": "236513742095", "title": "100th Season Duke",   "price": 225, "tag": "100th Season","notes": "NFL 100th season Wilson The Duke game ball. Hand-conditioned, NFL-sourced, PSA verified."},
    {"id": "236513750225", "title": "2x Rams Duke",        "price": 389, "tag": "Double Rams", "notes": "Double Rams logo stamped Wilson The Duke. Rare dual-stamp. Hand-conditioned, NFL-sourced."},
]

# Check for existing products to avoid duplicates
print("Checking existing Stripe products...")
existing = stripe_get("products?limit=100&active=true")
existing_by_meta = {}
if existing and 'data' in existing:
    for p in existing['data']:
        meta = p.get('metadata', {})
        if 'ebay_id' in meta:
            existing_by_meta[meta['ebay_id']] = p['id']
    print(f"  Found {len(existing_by_meta)} existing products with ebay_id metadata")

results = []

for ball in BALLS:
    ebay_id = ball['id']
    print(f"\nProcessing {ebay_id} — {ball['title']} (${ball['price']})...")

    # Reuse existing product if already created
    if ebay_id in existing_by_meta:
        product_id = existing_by_meta[ebay_id]
        print(f"  Product already exists: {product_id}")
    else:
        # Create product
        product = stripe_post("products", {
            "name":                    f"Foley's Footballs — {ball['title']} ({ebay_id})",
            "description":             ball['notes'],
            "metadata[ebay_id]":       ebay_id,
            "metadata[tag]":           ball['tag'],
            "shippable":               "true",
        })
        if not product:
            print(f"  FAILED to create product for {ebay_id}")
            results.append({"id": ebay_id, "error": "product creation failed"})
            continue
        product_id = product['id']
        print(f"  Created product: {product_id}")

    # Create price
    price = stripe_post("prices", {
        "product":      product_id,
        "unit_amount":  str(ball['price'] * 100),  # cents
        "currency":     "usd",
    })
    if not price:
        print(f"  FAILED to create price for {ebay_id}")
        results.append({"id": ebay_id, "error": "price creation failed"})
        continue
    price_id = price['id']
    print(f"  Created price: {price_id}")

    # Create payment link
    payment_link = stripe_post("payment_links", {
        "line_items[0][price]":    price_id,
        "line_items[0][quantity]": "1",
        "after_completion[type]":  "redirect",
        "after_completion[redirect][url]": "https://foleysfootballs.com?purchased=true",
        "shipping_address_collection[allowed_countries][0]": "US",
        "metadata[ebay_id]": ebay_id,
    })
    if not payment_link:
        print(f"  FAILED to create payment link for {ebay_id}")
        results.append({"id": ebay_id, "error": "payment link creation failed"})
        continue

    link_url = payment_link['url']
    print(f"  Payment link: {link_url}")

    results.append({
        "id":           ebay_id,
        "product_id":   product_id,
        "price_id":     price_id,
        "payment_link": link_url,
        "price":        ball['price'],
        "title":        ball['title'],
        "tag":          ball['tag'],
    })

# Save results
with open("stripe_products.json", "w") as f:
    json.dump({"products": results}, f, indent=2)

print(f"\n{'='*50}")
print(f"Done. {len([r for r in results if 'payment_link' in r])}/{len(BALLS)} products created.")
print("Results saved to stripe_products.json")

# Show summary
for r in results:
    if 'payment_link' in r:
        print(f"  {r['id']} — ${r['price']} — {r['payment_link']}")
    else:
        print(f"  {r['id']} — ERROR: {r.get('error', 'unknown')}")

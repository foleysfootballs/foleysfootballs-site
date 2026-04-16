# Foley's Footballs — Site Automation

## How it works
- `scrape.py` runs daily via GitHub Actions
- It fetches each eBay listing, pulls photos + status
- Rebuilds `index.html` automatically
- Deploys to Netlify within minutes

## Adding a new ball
1. Post your ball on eBay as usual
2. Open `listings.json`
3. Add one line to the `"listings"` array:
   ```json
   { "id": "YOUR_EBAY_ITEM_ID", "price": 175, "title": "NFL The Duke Wilson Football - Game Ball - Prepped & Conditioned" }
   ```
4. Commit and push — the site updates on the next scheduled run (or trigger manually)

## When a ball sells on eBay
Nothing to do. The next daily run detects it's sold, moves it to the SOLD section automatically, and removes it from `listings.json`.

## Triggering a manual update
Go to GitHub → Actions → "Update Site from eBay" → "Run workflow" → Run.
Site updates within ~3 minutes.

## Files
- `listings.json` — active eBay item IDs (only file you edit)
- `sold.json`     — auto-managed sold listings (don't edit)
- `index.html`    — auto-generated, don't edit manually
- `contact.html`  — edit this manually for contact form changes
- `scrape.py`     — the scraper, only touch if something breaks
- `.github/workflows/update-site.yml` — the schedule, runs daily at 8am UTC

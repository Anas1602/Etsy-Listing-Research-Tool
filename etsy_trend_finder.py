"""
Etsy Trend Finder
==================

Finds listings for a given search term that are BOTH:
  1. Newly listed (within N days)
  2. Already showing sales traction (review_count >= min_reviews)

...and ranks them by "review velocity" (reviews per day since listing),
which is a mathematically sound proxy for sales momentum:

    velocity = review_count / days_active

Why review_count and not a guessed "sales estimate"?
Etsy only allows a review after a verified purchase, so review_count is a
real, provable FLOOR on sales (actual sales >= review_count). We're not
estimating — we're ranking by a real lower-bound signal, normalized by time.

Requirements:
    pip install requests --break-system-packages

You need a free Etsy API key (keystring):
    1. Go to https://www.etsy.com/developers/register
    2. Create an app, copy the "Keystring" -- that's your API key.
    3. Public read-only endpoints (active listing search, reviews) work
       with just the API key in the x-api-key header, no OAuth needed.

Usage:
    python etsy_trend_finder.py "prop firm risk calculator" \
        --api-key YOUR_KEY \
        --days 30 \
        --min-reviews 1 \
        --max-pages 10 \
        --out results.csv
"""

import argparse
import csv
import sys
import time
from datetime import datetime, timezone

import requests

API_BASE = "https://openapi.etsy.com/v3/application"
LISTINGS_PER_PAGE = 100  # Etsy API max per page

# Real limits from the Etsy Developer dashboard for this key: 5 QPS, 5,000 QPD.
# 0.22s between calls keeps us under 5/sec with a safety margin.
REQUEST_DELAY_SEC = 0.22
DAILY_QUOTA = 5000


def api_get(path, api_key, params=None):
    """Call the Etsy Open API with basic retry/backoff on rate limiting."""
    headers = {"x-api-key": api_key}
    url = f"{API_BASE}{path}"
    for attempt in range(5):
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 429:
            wait = 2 ** attempt
            print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Failed after retries: {url}")


def fetch_listings(search_term, api_key, max_pages):
    """Fetch active listings for a search term, newest first, up to max_pages."""
    all_listings = []
    for page in range(max_pages):
        offset = page * LISTINGS_PER_PAGE
        params = {
            "keywords": search_term,
            "sort_on": "created",
            "sort_order": "desc",
            "limit": LISTINGS_PER_PAGE,
            "offset": offset,
        }
        data = api_get("/listings/active", api_key, params)
        results = data.get("results", [])
        if not results:
            break
        all_listings.extend(results)
        print(f"  Fetched page {page + 1} ({len(results)} listings)")
        time.sleep(REQUEST_DELAY_SEC)
        if len(results) < LISTINGS_PER_PAGE:
            break  # last page
    return all_listings


def fetch_review_count(listing_id, api_key):
    """Get the true review count for a listing (limit=1, we only need the count)."""
    params = {"limit": 1, "offset": 0}
    data = api_get(f"/listings/{listing_id}/reviews", api_key, params)
    time.sleep(REQUEST_DELAY_SEC)
    return data.get("count", 0)


def days_since(creation_timestamp):
    created = datetime.fromtimestamp(creation_timestamp, tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    delta = now - created
    return max(delta.total_seconds() / 86400, 0.01)  # floor to avoid div-by-zero


def analyze(search_term, api_key, days_threshold, min_reviews, max_pages, dry_run=False):
    print(f"Searching Etsy for: '{search_term}' (up to {max_pages} pages)...")

    if dry_run:
        # Dry-run only estimates cost: it fetches listing metadata (which we need
        # anyway to know ages) but skips the per-listing review-count calls,
        # since those are the bulk of quota usage.
        listings = fetch_listings(search_term, api_key, max_pages)
        eligible = [
            l for l in listings
            if (l.get("original_creation_timestamp") or l.get("creation_timestamp"))
            and days_since(l.get("original_creation_timestamp") or l.get("creation_timestamp")) <= days_threshold
        ]
        search_calls = -(-len(listings) // LISTINGS_PER_PAGE) or 1  # ceil division, min 1
        review_calls = len(eligible)
        total_calls = search_calls + review_calls
        print(f"\nDRY RUN ESTIMATE for '{search_term}':")
        print(f"  Listings scanned:         {len(listings)}")
        print(f"  Newly-listed candidates:  {len(eligible)} (would cost 1 review-count call each)")
        print(f"  Estimated API calls:      {total_calls} "
              f"(search: {search_calls}, reviews: {review_calls})")
        print(f"  Daily quota:              {DAILY_QUOTA}")
        print(f"  Estimated % of daily quota used: {total_calls / DAILY_QUOTA * 100:.1f}%")
        return []

    listings = fetch_listings(search_term, api_key, max_pages)
    print(f"Total listings fetched: {len(listings)}")

    candidates = []
    for i, listing in enumerate(listings, 1):
        listing_id = listing["listing_id"]
        created_tsz = listing.get("original_creation_timestamp") or listing.get("creation_timestamp")
        if not created_tsz:
            continue

        age_days = days_since(created_tsz)
        if age_days > days_threshold:
            continue  # not "newly listed" — skip before spending an API call on it

        review_count = fetch_review_count(listing_id, api_key)
        if review_count < min_reviews:
            continue

        velocity = review_count / age_days
        favorites = listing.get("num_favorers", 0)

        candidates.append({
            "listing_id": listing_id,
            "title": listing.get("title", "")[:80],
            "url": listing.get("url", ""),
            "price": listing.get("price", {}).get("amount", 0) / 100
                     if isinstance(listing.get("price"), dict) else listing.get("price"),
            "age_days": round(age_days, 1),
            "review_count": review_count,
            "favorites": favorites,
            "review_velocity": round(velocity, 3),
        })

        if i % 20 == 0:
            print(f"  Processed {i}/{len(listings)} listings, "
                  f"{len(candidates)} candidates so far...")

    candidates.sort(key=lambda c: c["review_velocity"], reverse=True)
    return candidates



def write_csv(candidates, out_path):
    if not candidates:
        print("No candidates found — nothing to write.")
        return
    fieldnames = ["listing_id", "title", "url", "price", "age_days",
                  "review_count", "favorites", "review_velocity"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)
    print(f"\nWrote {len(candidates)} candidates to {out_path}")


def write_html(candidates, out_path, search_term):
    """Generate a standalone, self-contained HTML report (no server needed)."""
    import json

    if candidates:
        velocities = [c["review_velocity"] for c in candidates]
        best_v = max(velocities)
        avg_v = sum(velocities) / len(velocities)
    else:
        best_v = avg_v = 0.0

    data_json = json.dumps(candidates)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Etsy Trend Finder — {search_term}</title>
<style>
  :root {{
    --bg: #14171C;
    --panel: #1C2027;
    --border: #2A2F38;
    --text: #E8E6E0;
    --text-dim: #8B9099;
    --accent: #5EC8B8;
    --price: #D9A34A;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", Inter, sans-serif;
    padding: 40px 24px 80px;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  h1 {{
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 4px;
  }}
  .subterm {{
    color: var(--text-dim);
    font-size: 14px;
    margin: 0 0 28px;
  }}
  .stats {{
    display: flex;
    gap: 16px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }}
  .stat {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    min-width: 140px;
  }}
  .stat .num {{
    font-family: "SF Mono", "JetBrains Mono", ui-monospace, monospace;
    font-size: 22px;
    color: var(--accent);
  }}
  .stat .label {{
    font-size: 12px;
    color: var(--text-dim);
    margin-top: 2px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }}
  thead th {{
    text-align: left;
    padding: 10px 12px;
    font-size: 12px;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }}
  thead th:hover {{ color: var(--text); }}
  thead th.sorted::after {{ content: " ↓"; color: var(--accent); }}
  tbody td {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    vertical-align: middle;
  }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: rgba(94, 200, 184, 0.06); }}
  .mono {{ font-family: "SF Mono", "JetBrains Mono", ui-monospace, monospace; }}
  .price {{ color: var(--price); }}
  .title-cell a {{ color: var(--text); text-decoration: none; }}
  .title-cell a:hover {{ color: var(--accent); text-decoration: underline; }}
  .velocity-cell {{ position: relative; min-width: 110px; }}
  .velocity-bar {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: rgba(94, 200, 184, 0.18);
    z-index: 0;
  }}
  .velocity-val {{ position: relative; z-index: 1; }}
  .empty {{
    color: var(--text-dim);
    padding: 40px;
    text-align: center;
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Etsy Trend Finder</h1>
  <p class="subterm">Search term: "{search_term}" — {len(candidates)} candidate{"s" if len(candidates) != 1 else ""} found</p>

  <div class="stats">
    <div class="stat"><div class="num mono">{len(candidates)}</div><div class="label">Candidates</div></div>
    <div class="stat"><div class="num mono">{best_v:.3f}</div><div class="label">Best velocity (rev/day)</div></div>
    <div class="stat"><div class="num mono">{avg_v:.3f}</div><div class="label">Avg velocity</div></div>
  </div>

  <table id="results">
    <thead>
      <tr>
        <th data-key="title">Title</th>
        <th data-key="price" class="mono">Price</th>
        <th data-key="age_days" class="mono">Age (d)</th>
        <th data-key="review_count" class="mono">Reviews</th>
        <th data-key="favorites" class="mono">Favorites</th>
        <th data-key="review_velocity" class="mono sorted">Velocity</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div id="emptyState" class="empty" style="display:none;">No candidates matched your filters for this search term.</div>
</div>

<script>
  const data = {data_json};
  const maxVelocity = Math.max(1e-6, ...data.map(d => d.review_velocity));
  let sortKey = "review_velocity";
  let sortDir = -1;

  function render() {{
    const tbody = document.getElementById("tbody");
    const rows = [...data].sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : -1) * sortDir);
    tbody.innerHTML = rows.map(r => {{
      const barWidth = (r.review_velocity / maxVelocity * 100).toFixed(1);
      return `
        <tr>
          <td class="title-cell"><a href="${{r.url}}" target="_blank" rel="noopener">${{r.title}}</a></td>
          <td class="mono price">$${{Number(r.price).toFixed(2)}}</td>
          <td class="mono">${{r.age_days}}</td>
          <td class="mono">${{r.review_count}}</td>
          <td class="mono">${{r.favorites}}</td>
          <td class="mono velocity-cell">
            <div class="velocity-bar" style="width:${{barWidth}}%"></div>
            <span class="velocity-val">${{r.review_velocity.toFixed(3)}}</span>
          </td>
        </tr>`;
    }}).join("");
    document.getElementById("emptyState").style.display = data.length ? "none" : "block";
  }}

  document.querySelectorAll("th[data-key]").forEach(th => {{
    th.addEventListener("click", () => {{
      const key = th.dataset.key;
      if (sortKey === key) {{
        sortDir *= -1;
      }} else {{
        sortKey = key;
        sortDir = -1;
      }}
      document.querySelectorAll("th").forEach(h => h.classList.remove("sorted"));
      th.classList.add("sorted");
      render();
    }});
  }});

  render();
</script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote HTML report to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Find newly-listed, already-selling Etsy listings.")
    parser.add_argument("search_term", help="Etsy search keywords")
    parser.add_argument("--api-key", required=True, help="Etsy API keystring")
    parser.add_argument("--days", type=int, default=30,
                         help="Max listing age in days to count as 'newly listed' (default: 30)")
    parser.add_argument("--min-reviews", type=int, default=1,
                         help="Minimum review count to count as 'already selling' (default: 1)")
    parser.add_argument("--max-pages", type=int, default=10,
                         help="Max pages of 100 listings to scan (default: 10)")
    parser.add_argument("--out", default="etsy_trend_results.csv", help="Output CSV path")
    parser.add_argument("--html-out", default="etsy_trend_report.html",
                         help="Output HTML report path (default: etsy_trend_report.html)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Estimate API call cost against the daily quota without spending review-count calls")
    args = parser.parse_args()

    candidates = analyze(
        search_term=args.search_term,
        api_key=args.api_key,
        days_threshold=args.days,
        min_reviews=args.min_reviews,
        max_pages=args.max_pages,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    print("\nTop candidates by review velocity:")
    for c in candidates[:15]:
        print(f"  [{c['review_velocity']:.3f}/day] {c['title']} "
              f"(age {c['age_days']}d, {c['review_count']} reviews, {c['favorites']} favs)")

    write_csv(candidates, args.out)
    write_html(candidates, args.html_out, args.search_term)


if __name__ == "__main__":
    main()
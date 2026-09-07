# .github\workflows\daily_scan.yml

```yml
name: Daily Etsy POD Hunter

on:
  schedule:
    # Runs every day at 06:00 AM UTC
    - cron: '0 6 * * *'
  # Allows you to trigger the scan manually from the GitHub Actions tab anytime
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scan:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run POD Scanner
        env:
          ETSY_API_KEY: ${{ secrets.ETSY_API_KEY }}
          ETSY_API_SECRET: ${{ secrets.ETSY_API_SECRET }}
        run: |
          python scanner.py

      - name: Commit and push updated winners
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add pod_winners.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "Auto-update POD winners [skip ci]" && git push)

```

# .gitignore

```
venv/
.env
__pycache__/
*.sqlite
```

# app.py

```py
import json
import os
import streamlit as st
import pandas as pd
from collections import Counter
import subprocess

st.set_page_config(
    page_title="Etsy POD Trend Vault",
    page_icon="🏛️",
    layout="wide"
)

DATA_FILE = "pod_winners.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []

listings = load_data()

# --- Header & Top Controls ---
st.title("🏛️ Etsy POD Trend Vault")
st.caption("Your permanent archive of winning Print-on-Demand listings over time.")

col_top1, col_top2 = st.columns([3, 1])
with col_top2:
    if st.button("🔄 Run Live Scan Now", use_container_width=True):
        with st.spinner("Scanning Etsy and updating your Vault..."):
            subprocess.run(["python", "scanner.py"])
            st.rerun()

if not listings:
    st.warning("Vault is empty. Click 'Run Live Scan Now' above to start finding winners.")
    st.stop()

# --- Sidebar Filters & Sorting ---
st.sidebar.header("🔍 Filters & Sorting")

sort_by = st.sidebar.selectbox(
    "Sort Items By",
    ["Highest Momentum Score", "Most Favorites", "Recently Discovered", "Newest Listing Age"]
)

# 1. Keyword Filter
all_keywords = sorted(list(set(item.get("search_keyword", "Other") for item in listings)))
selected_keywords = st.sidebar.multiselect("Filter by Seed Keyword", all_keywords, default=all_keywords)

# 2. Discovery Timeframe Filter
discovery_filter = st.sidebar.radio(
    "Vault Timeframe",
    ["All-Time Archive", "Discovered in Last 7 Days", "Discovered Today"]
)

# 3. Minimum Favorites Slider
min_favs = st.sidebar.slider(
    "Minimum Total Favorites", 
    min_value=0, 
    max_value=int(max((item.get("num_favorers", 10) for item in listings), default=100)), 
    value=5
)

# 4. Listing Age Slider (Now up to 365 days so archive items never get hidden!)
max_age = st.sidebar.slider(
    "Max Listing Age (Days)", 
    min_value=1, 
    max_value=365, 
    value=365
)

only_customizable = st.sidebar.checkbox("Only Customizable / Personalized Items", value=False)

# --- Apply Filtering Logic ---
from datetime import datetime, timezone, timedelta
today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
seven_days_ago_str = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

filtered_listings = []
for item in listings:
    # Keyword check
    if item.get("search_keyword") not in selected_keywords:
        continue
    # Favorites check
    if item.get("num_favorers", 0) < min_favs:
        continue
    # Age check
    if item.get("age_days", 0) > max_age:
        continue
    # Customization check
    if only_customizable and not item.get("is_personalizable", False):
        continue
    # Timeframe check
    disc_date = item.get("first_discovered", "")
    if discovery_filter == "Discovered Today" and disc_date != today_str:
        continue
    elif discovery_filter == "Discovered in Last 7 Days" and disc_date < seven_days_ago_str:
        continue

    filtered_listings.append(item)

# --- Apply Sorting ---
if sort_by == "Highest Momentum Score":
    filtered_listings.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)
elif sort_by == "Most Favorites":
    filtered_listings.sort(key=lambda x: x.get("num_favorers", 0), reverse=True)
elif sort_by == "Recently Discovered":
    filtered_listings.sort(key=lambda x: x.get("first_discovered", ""), reverse=True)
elif sort_by == "Newest Listing Age":
    filtered_listings.sort(key=lambda x: x.get("age_days", 999))

# --- Top Stats Banner ---
st.write("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("🏛️ Total Vault Products", len(listings))
m2.metric("🎯 Matching Filters", len(filtered_listings))
if filtered_listings:
    top_score = max(item.get("momentum_score", 0) for item in filtered_listings)
    avg_favs = round(sum(item.get("num_favorers", 0) for item in filtered_listings) / len(filtered_listings), 1)
    m3.metric("🔥 Top Momentum Score", top_score)
    m4.metric("❤️ Avg. Favorites", avg_favs)
st.write("---")

# --- Product Display Grid ---
st.subheader(f"📦 Product Vault ({len(filtered_listings)} listings)")

if not filtered_listings:
    st.info("No listings match the selected filters.")
else:
    cols_per_row = 3
    for i in range(0, len(filtered_listings), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(filtered_listings):
                item = filtered_listings[i + j]
                with cols[j]:
                    with st.container(border=True):
                        # Mockup Image
                        if item.get("image_url"):
                            st.image(item["image_url"], use_container_width=True)
                        else:
                            st.write("*(No Image Available)*")
                        
                        # Title & Link
                        st.markdown(f"**[{item['title'][:55]}...]({item['url']})**")
                        
                        # Metrics Row
                        c1, c2, c3 = st.columns(3)
                        c1.caption(f"💰 **{item['price']}**")
                        c2.caption(f"📅 **{item['age_days']}d old**")
                        c3.caption(f"❤️ **{item['num_favorers']} favs**")
                        
                        # Momentum Badge
                        score = item.get("momentum_score", 0)
                        if score >= 5.0:
                            st.success(f"🚀 Breakout Score: **{score}**")
                        elif score >= 2.0:
                            st.info(f"⚡ High Traction: **{score}**")
                        else:
                            st.warning(f"📈 Momentum Score: **{score}**")
                        
                        # Discovery stamp
                        st.caption(f"🗓️ *Discovered: {item.get('first_discovered', 'N/A')}*")

                        # Tags Accordion
                        if item.get("tags"):
                            with st.expander("🏷️ View 13 SEO Tags"):
                                st.write(", ".join([f"`{t}`" for t in item["tags"]]))

# --- SEO Tag Analysis Section ---
st.write("---")
st.subheader("🏷️ Top Recurring Tags in Vault")

all_tags = []
for item in filtered_listings:
    all_tags.extend(item.get("tags", []))

if all_tags:
    tag_counts = Counter(all_tags).most_common(15)
    df_tags = pd.DataFrame(tag_counts, columns=["Tag", "Occurrences"])
    
    col_chart, col_list = st.columns([2, 1])
    with col_chart:
        st.bar_chart(df_tags.set_index("Tag"))
    with col_list:
        st.dataframe(df_tags, use_container_width=True, hide_index=True)
```

# etsy_client.py

```py
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

class EtsyClient:
    BASE_URL = "https://openapi.etsy.com/v3/application"

    def __init__(self):
        self.api_key = os.getenv("ETSY_API_KEY")
        self.api_secret = os.getenv("ETSY_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Both ETSY_API_KEY and ETSY_API_SECRET must be set in .env")
        
        # Etsy v3 requires combining keystring and shared secret: "keystring:shared_secret"
        self.headers = {
            "x-api-key": f"{self.api_key}:{self.api_secret}"
        }
        
        # Safe delay: 0.35 seconds = ~2.8 requests/second (safe under 5 QPS limit)
        self.min_delay = 0.35
        self.last_request_time = 0

    def _rate_limit(self):
        """Ensures we never exceed Etsy's rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def get(self, endpoint, params=None, max_retries=3):
        """Performs a safe, rate-limited GET request to Etsy Open API v3."""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            self._rate_limit()
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                
                # 200 OK
                if response.status_code == 200:
                    return response.json()
                
                # 429 Rate Limit Exceeded: Wait and retry
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 2
                    print(f"⚠️ Rate limited (429). Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                
                # Other HTTP errors
                else:
                    print(f"❌ API Error [{response.status_code}] on {endpoint}: {response.text}")
                    return None

            except requests.RequestException as e:
                print(f"⚠️ Network error on attempt {attempt + 1}: {e}")
                time.sleep(1)

        print(f"❌ Failed to fetch {endpoint} after {max_retries} retries.")
        return None

    def search_active_listings(self, keywords, limit=10, sort_on="created", sort_order="desc"):
        """Fetches active listings for a given keyword query."""
        endpoint = "listings/active"
        params = {
            "keywords": keywords,
            "limit": limit,
            "sort_on": sort_on,
            "sort_order": sort_order
        }
        return self.get(endpoint, params=params)


# --- Live Connection Test ---
if __name__ == "__main__":
    print("Testing Etsy API connection...")
    client = EtsyClient()
    
    # Simple test query for POD blankets
    result = client.search_active_listings(keywords="custom blanket", limit=1)
    
    if result and "results" in result and len(result["results"]) > 0:
        sample = result["results"][0]
        print("\n✅ Etsy API Connection Successful!")
        print(f"Found sample listing: {sample.get('title')[:60]}...")
        print(f"Listing ID: {sample.get('listing_id')}")
        print(f"Price: {sample.get('price', {}).get('amount')} {sample.get('price', {}).get('currency_code')}")
    else:
        print("\n❌ Failed to get results from Etsy. Check your API credentials or response.")
```

# etsy_trend_finder.py

```py
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

You need a free Etsy API key + shared secret:
    1. Go to https://www.etsy.com/developers/register and create a Personal App.
    2. On your app's dashboard you'll see both a "Keystring" and a "Shared Secret" —
       you need BOTH. Every request's x-api-key header must be
       "<keystring>:<shared_secret>" — the keystring alone returns 403 Forbidden.

Usage:
    python etsy_trend_finder.py "prop firm risk calculator" \
        --api-key YOUR_KEYSTRING \
        --api-secret YOUR_SHARED_SECRET \
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

API_BASE = "https://api.etsy.com/v3/application"
LISTINGS_PER_PAGE = 100  # Etsy API max per page

# Real limits from the Etsy Developer dashboard for this key: 5 QPS, 5,000 QPD.
# 0.22s between calls keeps us under 5/sec with a safety margin.
REQUEST_DELAY_SEC = 0.22
DAILY_QUOTA = 5000


def api_get(path, api_key, api_secret, params=None):
    """Call the Etsy Open API with basic retry/backoff on rate limiting.

    Every v3 request needs x-api-key as "<keystring>:<shared_secret>" —
    the keystring alone is not sufficient and returns 403 Forbidden.
    """
    headers = {"x-api-key": f"{api_key}:{api_secret}"}
    url = f"{API_BASE}{path}"
    for attempt in range(5):
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 429:
            wait = 2 ** attempt
            print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code >= 400:
            print(f"  Etsy API error {resp.status_code} on {url}: {resp.text[:300]}", file=sys.stderr)
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Failed after retries: {url}")


def fetch_listings(search_term, api_key, api_secret, max_pages):
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
        data = api_get("/listings/active", api_key, api_secret, params)
        results = data.get("results", [])
        if not results:
            break
        all_listings.extend(results)
        print(f"  Fetched page {page + 1} ({len(results)} listings)")
        time.sleep(REQUEST_DELAY_SEC)
        if len(results) < LISTINGS_PER_PAGE:
            break  # last page
    return all_listings


def fetch_review_count(listing_id, api_key, api_secret):
    """Get the true review count for a listing (limit=1, we only need the count)."""
    params = {"limit": 1, "offset": 0}
    data = api_get(f"/listings/{listing_id}/reviews", api_key, api_secret, params)
    time.sleep(REQUEST_DELAY_SEC)
    return data.get("count", 0)


def days_since(creation_timestamp):
    created = datetime.fromtimestamp(creation_timestamp, tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    delta = now - created
    return max(delta.total_seconds() / 86400, 0.01)  # floor to avoid div-by-zero


def analyze(search_term, api_key, api_secret, days_threshold, min_reviews, max_pages, dry_run=False):
    print(f"Searching Etsy for: '{search_term}' (up to {max_pages} pages)...")

    if dry_run:
        # Dry-run only estimates cost: it fetches listing metadata (which we need
        # anyway to know ages) but skips the per-listing review-count calls,
        # since those are the bulk of quota usage.
        listings = fetch_listings(search_term, api_key, api_secret, max_pages)
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

    listings = fetch_listings(search_term, api_key, api_secret, max_pages)
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

        review_count = fetch_review_count(listing_id, api_key, api_secret)
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
    parser.add_argument("--api-secret", required=True,
                         help="Etsy App shared secret (shown next to your keystring on the dashboard). "
                              "Required — Etsy rejects requests with the keystring alone.")
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
        api_secret=args.api_secret,
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
```

# etsy_trend_report.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Etsy Trend Finder — personalized kids books</title>
<style>
  :root {
    --bg: #14171C;
    --panel: #1C2027;
    --border: #2A2F38;
    --text: #E8E6E0;
    --text-dim: #8B9099;
    --accent: #5EC8B8;
    --price: #D9A34A;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", Inter, sans-serif;
    padding: 40px 24px 80px;
  }
  .wrap { max-width: 980px; margin: 0 auto; }
  h1 {
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 4px;
  }
  .subterm {
    color: var(--text-dim);
    font-size: 14px;
    margin: 0 0 28px;
  }
  .stats {
    display: flex;
    gap: 16px;
    margin-bottom: 28px;
    flex-wrap: wrap;
  }
  .stat {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    min-width: 140px;
  }
  .stat .num {
    font-family: "SF Mono", "JetBrains Mono", ui-monospace, monospace;
    font-size: 22px;
    color: var(--accent);
  }
  .stat .label {
    font-size: 12px;
    color: var(--text-dim);
    margin-top: 2px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  thead th {
    text-align: left;
    padding: 10px 12px;
    font-size: 12px;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  thead th:hover { color: var(--text); }
  thead th.sorted::after { content: " ↓"; color: var(--accent); }
  tbody td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: rgba(94, 200, 184, 0.06); }
  .mono { font-family: "SF Mono", "JetBrains Mono", ui-monospace, monospace; }
  .price { color: var(--price); }
  .title-cell a { color: var(--text); text-decoration: none; }
  .title-cell a:hover { color: var(--accent); text-decoration: underline; }
  .velocity-cell { position: relative; min-width: 110px; }
  .velocity-bar {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    background: rgba(94, 200, 184, 0.18);
    z-index: 0;
  }
  .velocity-val { position: relative; z-index: 1; }
  .empty {
    color: var(--text-dim);
    padding: 40px;
    text-align: center;
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>Etsy Trend Finder</h1>
  <p class="subterm">Search term: "personalized kids books" — 9 candidates found</p>

  <div class="stats">
    <div class="stat"><div class="num mono">9</div><div class="label">Candidates</div></div>
    <div class="stat"><div class="num mono">0.097</div><div class="label">Best velocity (rev/day)</div></div>
    <div class="stat"><div class="num mono">0.053</div><div class="label">Avg velocity</div></div>
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
  const data = [{"listing_id": 4559819367, "title": "Personalized Zoo Book for Kids | Custom Name Children&#39;s Book | Birthday Gift", "url": "https://www.etsy.com/listing/4559819367/personalized-zoo-book-for-kids-custom", "price": 34.99, "age_days": 10.3, "review_count": 1, "favorites": 3, "review_velocity": 0.097}, {"listing_id": 4550764161, "title": "Custom Photo Playing Cards for Wedding | Personalized Wedding Newspaper Guest Bo", "url": "https://www.etsy.com/listing/4550764161/custom-photo-playing-cards-for-wedding", "price": 9.73, "age_days": 25.5, "review_count": 2, "favorites": 166, "review_velocity": 0.079}, {"listing_id": 4548387793, "title": "Personalized First Prayer Book for Kids with Photo & Name, Christian Everyday Be", "url": "https://www.etsy.com/listing/4548387793/personalized-first-prayer-book-for-kids", "price": 27.58, "age_days": 29.3, "review_count": 2, "favorites": 29, "review_velocity": 0.068}, {"listing_id": 4552841607, "title": "Custom First Birthday Story Book for Baby Boy Girl, Personalized 1st Birthday Gi", "url": "https://www.etsy.com/listing/4552841607/custom-first-birthday-story-book-for", "price": 34.26, "age_days": 21.8, "review_count": 1, "favorites": 45, "review_velocity": 0.046}, {"listing_id": 4551935590, "title": "Personalized Mimi Book for Grandchild, Custom Name Mimi and Me Storybook, I Love", "url": "https://www.etsy.com/listing/4551935590/personalized-mimi-book-for-grandchild", "price": 52.5, "age_days": 23.6, "review_count": 1, "favorites": 11, "review_velocity": 0.042}, {"listing_id": 4550286343, "title": "Personalized Christian Goose Book, Custom Farm Storybook With Name, Baptism Gift", "url": "https://www.etsy.com/listing/4550286343/personalized-christian-goose-book-custom", "price": 22.5, "age_days": 26.2, "review_count": 1, "favorites": 16, "review_velocity": 0.038}, {"listing_id": 4550232723, "title": "Personalized All Characters Autograph Book, Mickey and Friends Signatures Book, ", "url": "https://www.etsy.com/listing/4550232723/personalized-all-characters-autograph", "price": 22.0, "age_days": 26.2, "review_count": 1, "favorites": 110, "review_velocity": 0.038}, {"listing_id": 4549726824, "title": "Personalized Christmas Book for Kids, Custom Name Storybook for Boy or Girl, Mag", "url": "https://www.etsy.com/listing/4549726824/personalized-christmas-book-for-kids", "price": 21.98, "age_days": 27.1, "review_count": 1, "favorites": 4, "review_velocity": 0.037}, {"listing_id": 4548833685, "title": "Personalized Christmas Gift for Kids, Custom Christmas Book, Personalized Story ", "url": "https://www.etsy.com/listing/4548833685/personalized-christmas-gift-for-kids", "price": 39.99, "age_days": 28.5, "review_count": 1, "favorites": 19, "review_velocity": 0.035}];
  const maxVelocity = Math.max(1e-6, ...data.map(d => d.review_velocity));
  let sortKey = "review_velocity";
  let sortDir = -1;

  function render() {
    const tbody = document.getElementById("tbody");
    const rows = [...data].sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : -1) * sortDir);
    tbody.innerHTML = rows.map(r => {
      const barWidth = (r.review_velocity / maxVelocity * 100).toFixed(1);
      return `
        <tr>
          <td class="title-cell"><a href="${r.url}" target="_blank" rel="noopener">${r.title}</a></td>
          <td class="mono price">$${Number(r.price).toFixed(2)}</td>
          <td class="mono">${r.age_days}</td>
          <td class="mono">${r.review_count}</td>
          <td class="mono">${r.favorites}</td>
          <td class="mono velocity-cell">
            <div class="velocity-bar" style="width:${barWidth}%"></div>
            <span class="velocity-val">${r.review_velocity.toFixed(3)}</span>
          </td>
        </tr>`;
    }).join("");
    document.getElementById("emptyState").style.display = data.length ? "none" : "block";
  }

  document.querySelectorAll("th[data-key]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) {
        sortDir *= -1;
      } else {
        sortKey = key;
        sortDir = -1;
      }
      document.querySelectorAll("th").forEach(h => h.classList.remove("sorted"));
      th.classList.add("sorted");
      render();
    });
  });

  render();
</script>
</body>
</html>

```

# etsy_trend_results.csv

```csv
listing_id,title,url,price,age_days,review_count,favorites,review_velocity
4559819367,Personalized Zoo Book for Kids | Custom Name Children&#39;s Book | Birthday Gift,https://www.etsy.com/listing/4559819367/personalized-zoo-book-for-kids-custom,34.99,10.3,1,3,0.097
4550764161,Custom Photo Playing Cards for Wedding | Personalized Wedding Newspaper Guest Bo,https://www.etsy.com/listing/4550764161/custom-photo-playing-cards-for-wedding,9.73,25.5,2,166,0.079
4548387793,"Personalized First Prayer Book for Kids with Photo & Name, Christian Everyday Be",https://www.etsy.com/listing/4548387793/personalized-first-prayer-book-for-kids,27.58,29.3,2,29,0.068
4552841607,"Custom First Birthday Story Book for Baby Boy Girl, Personalized 1st Birthday Gi",https://www.etsy.com/listing/4552841607/custom-first-birthday-story-book-for,34.26,21.8,1,45,0.046
4551935590,"Personalized Mimi Book for Grandchild, Custom Name Mimi and Me Storybook, I Love",https://www.etsy.com/listing/4551935590/personalized-mimi-book-for-grandchild,52.5,23.6,1,11,0.042
4550286343,"Personalized Christian Goose Book, Custom Farm Storybook With Name, Baptism Gift",https://www.etsy.com/listing/4550286343/personalized-christian-goose-book-custom,22.5,26.2,1,16,0.038
4550232723,"Personalized All Characters Autograph Book, Mickey and Friends Signatures Book, ",https://www.etsy.com/listing/4550232723/personalized-all-characters-autograph,22.0,26.2,1,110,0.038
4549726824,"Personalized Christmas Book for Kids, Custom Name Storybook for Boy or Girl, Mag",https://www.etsy.com/listing/4549726824/personalized-christmas-book-for-kids,21.98,27.1,1,4,0.037
4548833685,"Personalized Christmas Gift for Kids, Custom Christmas Book, Personalized Story ",https://www.etsy.com/listing/4548833685/personalized-christmas-gift-for-kids,39.99,28.5,1,19,0.035

```

# pod_winners.json

```json
[
  {
    "listing_id": 4558595599,
    "title": "Custom Gingham Applique Mock Neck Sweatshirt, Personalized Embroidered Name Pullover, Custom Text Crewneck, Gift for Her",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 12,
    "num_favorers": 244,
    "momentum_score": 18.77,
    "price": "30.99 USD",
    "url": "https://www.etsy.com/listing/4558595599/custom-gingham-applique-mock-neck",
    "image_url": "https://i.etsystatic.com/65642607/r/il/e050b3/8450118201/il_570xN.8450118201_diac.jpg",
    "tags": [
      "custom sweatshirt",
      "custom mock neck",
      "gingham sweatshirt",
      "personalized shirt",
      "custom name shirt",
      "applique sweatshirt",
      "custom text shirt",
      "varsity sweatshirt",
      "personalized gift",
      "custom crewneck",
      "gingham applique",
      "gift for her"
    ],
    "views": 8801,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550381430,
    "title": "Custom Varsity Applique Sweatshirt, Personalized School Name Crewneck, Embroidered Patchwork College Spirit Sweatshirt",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 26,
    "num_favorers": 307,
    "momentum_score": 11.37,
    "price": "34.49 USD",
    "url": "https://www.etsy.com/listing/4550381430/custom-varsity-applique-sweatshirt",
    "image_url": "https://i.etsystatic.com/62330725/r/il/75f743/8390624219/il_570xN.8390624219_vmj2.jpg",
    "tags": [
      "custom sweatshirt",
      "school sweatshirt",
      "varsity applique",
      "custom crewneck",
      "embroidered top",
      "college spirit",
      "school mascot",
      "patch sweatshirt",
      "gingham applique",
      "preppy style",
      "personalized",
      "school gift",
      "custom name"
    ],
    "views": 9296,
    "is_personalizable": true
  },
  {
    "listing_id": 4548820012,
    "title": "Embroidered Dragon Sweatshirt, Fourth Wing Embroidered Sweatshirt, Basgiath War College Hoodie, Dragon Rider Fantasy Reader Gift",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 28,
    "num_favorers": 258,
    "momentum_score": 8.9,
    "price": "24.59 USD",
    "url": "https://www.etsy.com/listing/4548820012/embroidered-dragon-sweatshirt-fourth",
    "image_url": "https://i.etsystatic.com/59645722/r/il/edadf0/8379363815/il_570xN.8379363815_t49r.jpg",
    "tags": [
      "Bookish Gift",
      "Gift For Book Lover",
      "Fantasy Sweatshirt",
      "Fourth Wing Sweater",
      "Romantasy Reader",
      "Fantasy Hoodie",
      "Book Lover Sweater",
      "Reading lover Gift",
      "Dragon Sweatshirt",
      "Fourth Wing Merch",
      "Rebecca Yarros",
      "Basgiath War College",
      "Book Lover Gift"
    ],
    "views": 2591,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550187805,
    "title": "Custom Pet Portrait Mug — Hand-Painted Ceramic Dog Cat Cup, Personalized Gift For Pet Lovers",
    "search_keyword": "custom pet portrait mug",
    "age_days": 26,
    "num_favorers": 229,
    "momentum_score": 8.48,
    "price": "38.40 USD",
    "url": "https://www.etsy.com/listing/4550187805/custom-pet-portrait-mug-hand-painted",
    "image_url": "https://i.etsystatic.com/63172802/r/il/8d22bd/8389247633/il_570xN.8389247633_g72y.jpg",
    "tags": [
      "pet portrait mug",
      "christmas pet gift",
      "dog lovers gift",
      "cat lovers gift",
      "pet coffee cup",
      "birthday pet gift",
      "pet memorial gift",
      "dog memorial gift",
      "custom pet portrait",
      "pet remembrance gift",
      "pet loss gift",
      "personalized gift",
      "birthday gift"
    ],
    "views": 2831,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558064982,
    "title": "The Valkyries ACOTAR Shirt, Gift for Romantasy Readers, ACOTAR 6 Book Tshirt with Winged Sword, Comfort Colors Shirts for SJM fans",
    "search_keyword": "romantasy reader shirt",
    "age_days": 13,
    "num_favorers": 107,
    "momentum_score": 7.64,
    "price": "26.00 GBP",
    "url": "https://www.etsy.com/listing/4558064982/valkyrie-acotar-shirt-gift-for-romantasy",
    "image_url": "https://i.etsystatic.com/65532687/r/il/ae1511/8435257490/il_570xN.8435257490_e6m8.jpg",
    "tags": [
      "Sarah J Maas",
      "Bookish Gift",
      "Fantasy Reader Gift",
      "Fantasy Tee",
      "ACOTAR Merch",
      "Sarah J Maas Merch",
      "Dark Romance",
      "Fantasy Lover Gift",
      "Gift for her",
      "Book Trope",
      "the valkyries",
      "valkyrie",
      "nesta archeron"
    ],
    "views": 725,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553128091,
    "title": "Personalized Wildflower Baby Blanket Name, Custom Embroidered Floral Butterfly Baby Shower Gift, Gift for Baby Girl, Welcome Baby Blanket",
    "search_keyword": "personalized baby name blanket",
    "age_days": 21,
    "num_favorers": 159,
    "momentum_score": 7.23,
    "price": "34.98 USD",
    "url": "https://www.etsy.com/listing/4553128091/personalized-wildflower-baby-blanket",
    "image_url": "https://i.etsystatic.com/65178907/r/il/8ef400/8362721492/il_570xN.8362721492_d1eq.jpg",
    "tags": [
      "custom baby blanket",
      "embroidered blankets",
      "custom name blanket",
      "personalized blanket",
      "baby shower gift",
      "baby name blanket",
      "custom knit blanket",
      "nersey blanket",
      "newborn name blanket",
      "floral baby blanket",
      "wildflower blanket",
      "girl baby blanket",
      "keepsake newborn"
    ],
    "views": 3871,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4562874122,
    "title": "Embroidered Halloween Radiology Sweatshirt, Halloween Xray Tech Tee, Rad Tech Halloween Gift, Ghost Radiology Gift, Radiology Student Gift",
    "search_keyword": "radiology tech sweatshirt",
    "age_days": 5,
    "num_favorers": 33,
    "momentum_score": 5.5,
    "price": "27.80 USD",
    "url": "https://www.etsy.com/listing/4562874122/embroidered-halloween-radiology",
    "image_url": "https://i.etsystatic.com/56351970/r/il/829418/8481230271/il_570xN.8481230271_3yf7.jpg",
    "tags": [
      "radiology sweatshirt",
      "halloween xray tech",
      "spooky radiology",
      "rad tech halloween",
      "xray tech sweatshirt",
      "radiology tech gift",
      "radiology sweater",
      "spooky xray tech",
      "halloween rad tech",
      "radiology student",
      "rad tech crewneck"
    ],
    "views": 229,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549561047,
    "title": "Spooky Season Embroidered Sweatshirt, Black Cat and Bat Applique Tee, Coquette Halloween Crewneck, Cozy Season Gift, Halloween Gift",
    "search_keyword": "cute retro halloween crewneck",
    "age_days": 27,
    "num_favorers": 143,
    "momentum_score": 5.11,
    "price": "24.59 USD",
    "url": "https://www.etsy.com/listing/4549561047/spooky-season-embroidered-sweatshirt",
    "image_url": "https://i.etsystatic.com/59645722/r/il/8992a5/8384863619/il_570xN.8384863619_snoq.jpg",
    "tags": [
      "halloween shirt",
      "retro halloween",
      "cute halloween",
      "spooky season tee",
      "striped ghost shirt",
      "gliter applique",
      "coquette halloween",
      "ghost shirt",
      "fall halloween tee",
      "boo season shirt",
      "pumpkin halloween",
      "halloween town tee",
      "trick or treat"
    ],
    "views": 1908,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4556246950,
    "title": "Embroidered Monorail Dachshund Sweatshirt, Magical Land Vacation Crewneck, Holiday Girl Trip Shirt, Doxie Lover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 16,
    "num_favorers": 83,
    "momentum_score": 4.88,
    "price": "41.54 USD",
    "url": "https://www.etsy.com/listing/4556246950/embroidered-monorail-dachshund",
    "image_url": "https://i.etsystatic.com/51285704/r/il/c64e50/8385193798/il_570xN.8385193798_nzvs.jpg",
    "tags": [
      "dachshund monorail",
      "disney vacation gift",
      "park day shirt",
      "wiener dog sweater",
      "embroidered doxies",
      "magical theme park",
      "dog mom disney",
      "sausage dog outfit",
      "vacation sweatshirt",
      "cute dog graphic",
      "travel lover gift",
      "retro monorail",
      "disneyland merch"
    ],
    "views": 1102,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4563130719,
    "title": "Embroidered Dollywood Imagination Library Pink Glitter Sweatshirt, Inspired Book Lover Shirt, Fan Shirt",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 5,
    "num_favorers": 29,
    "momentum_score": 4.83,
    "price": "63.76 USD",
    "url": "https://www.etsy.com/listing/4563130719/embroidered-dollywood-imagination",
    "image_url": "https://i.etsystatic.com/52526162/r/il/0740ad/8483350863/il_570xN.8483350863_1udp.jpg",
    "tags": [
      "dollywood sweatshirt",
      "imagination library",
      "dolly parton shirt",
      "reading teacher gift",
      "library lover gift",
      "embroidered books",
      "bookish crewneck",
      "teacher sweatshirt",
      "reading lover shirt",
      "dolly fan gift",
      "book club sweatshirt",
      "literacy gift"
    ],
    "views": 162,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557239928,
    "title": "Embroidered Radiology Xray Tech Sweatshirt: Radiography Icons Crewneck",
    "search_keyword": "radiology tech sweatshirt",
    "age_days": 14,
    "num_favorers": 71,
    "momentum_score": 4.73,
    "price": "25.99 USD",
    "url": "https://www.etsy.com/listing/4557239928/embroidered-radiology-xray-tech-icon",
    "image_url": "https://i.etsystatic.com/64535074/r/il/4175c3/8392518918/il_570xN.8392518918_k6o3.jpg",
    "tags": [
      "embroidered",
      "sweatshirt",
      "crewneck",
      "women",
      "women's gifts",
      "women's crewnecks",
      "xray",
      "radiology",
      "radiology tech",
      "xray tech",
      "radiography",
      "xray student",
      "radiology student"
    ],
    "views": 508,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4563599116,
    "title": "Para Normal Activities PNG SPED Teacher Halloween Design, Funny Ghost Special Education Shirt SVG Digital Download",
    "search_keyword": "special education teacher shirt",
    "age_days": 4,
    "num_favorers": 17,
    "momentum_score": 3.4,
    "price": "46.00 MAD",
    "url": "https://www.etsy.com/listing/4563599116/para-normal-activities-png-sped-teacher",
    "image_url": "https://i.etsystatic.com/60951385/r/il/ba0cd7/8438787994/il_570xN.8438787994_5psj.jpg",
    "tags": [
      "sped teacher png",
      "para educator",
      "halloween teacher",
      "sped halloween",
      "teacher ghost",
      "para professional",
      "special education",
      "teacher humor",
      "halloween png",
      "classroom ghost",
      "school staff gift",
      "teacher svg",
      "spooky teacher"
    ],
    "views": 129,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4551468643,
    "title": "Personalized Gingham Tote Bag,Custom Name Canvas Bag,Bridesmaid Gift Bag, Gift For Her",
    "search_keyword": "personalized bridal party tote bag",
    "age_days": 24,
    "num_favorers": 85,
    "momentum_score": 3.4,
    "price": "9.90 USD",
    "url": "https://www.etsy.com/listing/4551468643/personalized-gingham-tote-bagcustom-name",
    "image_url": "https://i.etsystatic.com/58719189/r/il/035e43/8397667587/il_570xN.8397667587_5l0r.jpg",
    "tags": [
      "Bridesmaid Gifts",
      "Custom Tote Bag",
      "Bachelorette Gifts",
      "Gift for Her",
      "Bridesmaid gift bags",
      "Bridal Shower",
      "Travel Tote bag",
      "Personalized Gifts",
      "canvas tote bag",
      "custom name tote",
      "Bridal Party Favor",
      "Wedding Welcome Bag",
      "Market Bag"
    ],
    "views": 628,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4552054791,
    "title": "Cute Doxie Monorail Embroidered Sweatshirt, Retro Theme Sausage Dog Shirt, Dachshund Lover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 23,
    "num_favorers": 79,
    "momentum_score": 3.29,
    "price": "16.65 USD",
    "url": "https://www.etsy.com/listing/4552054791/cute-doxie-monorail-embroidered",
    "image_url": "https://i.etsystatic.com/58154715/r/il/35e392/8402726977/il_570xN.8402726977_57g9.jpg",
    "tags": [
      "embroidered apparel",
      "dachshund lover",
      "funny dog shirt",
      "disney inspired",
      "crewneck sweater",
      "cozy park style",
      "doxie mom",
      "handmade clothing",
      "custom embroidery",
      "puppy gift idea",
      "whimsical fashion",
      "unisex sweatshirt",
      "disney fan gift"
    ],
    "views": 2144,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550193249,
    "title": "Personalized Flower Baby Name Blanket,Embroidered Butterfly Floral Baby Blanket,Floral Baby Knitted Throw,Newborn Blanket,Custom Baby Gift",
    "search_keyword": "custom floral baby blanket",
    "age_days": 26,
    "num_favorers": 88,
    "momentum_score": 3.26,
    "price": "2128.71 PHP",
    "url": "https://www.etsy.com/listing/4550193249/personalized-flower-baby-name",
    "image_url": "https://i.etsystatic.com/65652011/r/il/946984/8341404712/il_570xN.8341404712_dx4y.jpg",
    "tags": [
      "Baby Shower Gift",
      "Baby Keepsake Gift",
      "custom name blanket",
      "personalized blanket",
      "Embroidered Blankets",
      "cotton baby blanket",
      "Custom Blanket baby",
      "knit baby blanket",
      "Welcome Baby Blanket",
      "Newborn Keepsake",
      "baby blanket",
      "floral baby blanket",
      "wildflower blanket"
    ],
    "views": 3621,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550429142,
    "title": "Labor & Delivery Nurse Embroidered Sweatshirt, Preppy Seersucker Pullover",
    "search_keyword": "l&d nurse crewneck",
    "age_days": 26,
    "num_favorers": 86,
    "momentum_score": 3.19,
    "price": "25.99 USD",
    "url": "https://www.etsy.com/listing/4550429142/labor-delivery-nurse-embroidered",
    "image_url": "https://i.etsystatic.com/64535074/r/il/f34e71/8343084034/il_570xN.8343084034_tgog.jpg",
    "tags": [
      "embroidered crewneck",
      "applique crewneck",
      "ob nurse",
      "ld nurse sweatshirt",
      "obgyn christmas",
      "obgyn sweatshirt",
      "labor and delivery",
      "labor delivery nurse",
      "labor nurse gift",
      "delivery nurse shirt",
      "l and d sweatshirt",
      "delivery nurse",
      "labor delivery shirt"
    ],
    "views": 775,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553987219,
    "title": "Personalized Winnie the Pooh Baby Book, Custom Story Keepsake, Watercolor Illustrations, Personal New Mom Baby Customized Storybook Gift",
    "search_keyword": "personalized first birthday story book",
    "age_days": 20,
    "num_favorers": 67,
    "momentum_score": 3.19,
    "price": "45.00 USD",
    "url": "https://www.etsy.com/listing/4553987219/personalized-winnie-the-pooh-baby-book",
    "image_url": "https://i.etsystatic.com/36628331/r/il/d9d097/8416722325/il_570xN.8416722325_aakp.jpg",
    "tags": [
      "winnie the pooh book",
      "custom newborn gift",
      "personalized newborn",
      "new baby gift",
      "baby keepsake book",
      "custom baby book",
      "newborn keepsake",
      "baby story book",
      "personalized story",
      "first birthday gift",
      "winnie the pooh baby",
      "custom story book",
      "personalized book"
    ],
    "views": 807,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4552111408,
    "title": "Blue Flowers Embroidered Sweatshirt, Sword Stick Shirt, Anime Wand Shirt, Bookish Lovers Gift, Embroidered Anime Wand Crewneck,",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 23,
    "num_favorers": 74,
    "momentum_score": 3.08,
    "price": "22.00 USD",
    "url": "https://www.etsy.com/listing/4552111408/blue-flowers-embroidered-sweatshirt",
    "image_url": "https://i.etsystatic.com/52539890/r/il/e2359b/8403082903/il_570xN.8403082903_8cyd.jpg",
    "tags": [
      "embroidered shirt",
      "Crewneck embroidery",
      "Sousou No Frieren",
      "Frieren Sweatshirt",
      "Anime Lover Shirt",
      "Blue Moon Flower",
      "Anime Wand Crewneck",
      "Blue Flowers Shirt",
      "Bookish Lovers Gift",
      "Sword Stick Shirt",
      "blue flower shirt"
    ],
    "views": 491,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4561566866,
    "title": "Cute Doxie Monorail Embroidered Sweatshirt, Retro Theme Park Dachshund Shirt, Custom Name Matching Tee, Doxie Lover Gift, Family Trip Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 7,
    "num_favorers": 23,
    "momentum_score": 2.88,
    "price": "30.80 USD",
    "url": "https://www.etsy.com/listing/4561566866/cute-doxie-monorail-embroidered",
    "image_url": "https://i.etsystatic.com/56351970/r/il/06be48/8471716533/il_570xN.8471716533_pao1.jpg",
    "tags": [
      "embroidered apparel",
      "dachshund lover",
      "funny dog shirt",
      "disney inspired",
      "cozy park style",
      "doxie mom",
      "custom embroidery",
      "puppy gift idea",
      "disney fan gift",
      "pet embroidered",
      "pet custom shirt",
      "dog portrait custom",
      "dog embroidered"
    ],
    "views": 308,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550890360,
    "title": "Embroidered Halloween Dachshund Sweatshirt, Spooky Wiener Dog Fall Graphic Tee",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 25,
    "num_favorers": 75,
    "momentum_score": 2.88,
    "price": "21.99 USD",
    "url": "https://www.etsy.com/listing/4550890360/embroidered-halloween-dachshund",
    "image_url": "https://i.etsystatic.com/65358000/r/il/2c33dc/8346389380/il_570xN.8346389380_pf5z.jpg",
    "tags": [
      "halloween dachshund",
      "weiner dog shirt",
      "spooky season tee",
      "cute ghost dog",
      "cute pumpkin patch",
      "horror shirt",
      "spooky shirt",
      "dachshund halloween",
      "dog halloween",
      "Halloween shirt",
      "fall shirt",
      "embroidered dog",
      "dog pumpkin"
    ],
    "views": 921,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4563131701,
    "title": "Dollywood Imagination Library Pink Glitter Embroidered Sweatshirt, Fan Shirt, Parton Inspired Book Lover Shirt",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 5,
    "num_favorers": 17,
    "momentum_score": 2.83,
    "price": "104.84 USD",
    "url": "https://www.etsy.com/listing/4563131701/dollywood-imagination-library-pink",
    "image_url": "https://i.etsystatic.com/39816661/r/il/3af136/8483357741/il_570xN.8483357741_aokw.jpg",
    "tags": [
      "dollywood sweatshirt",
      "imagination library",
      "dolly parton shirt",
      "reading teacher gift",
      "library lover gift",
      "embroidered books",
      "bookish crewneck",
      "teacher sweatshirt",
      "reading lover shirt",
      "dolly fan gift",
      "book club sweatshirt",
      "literacy gift"
    ],
    "views": 133,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550264420,
    "title": "Personalized Name Baby Romper Set, Custom Embroidered Newborn Romper With Blanket, Coming Home Outfit, Baby Shower Gift, First Birthday Gift",
    "search_keyword": "personalized baby name blanket",
    "age_days": 26,
    "num_favorers": 67,
    "momentum_score": 2.48,
    "price": "18.00 USD",
    "url": "https://www.etsy.com/listing/4550264420/personalized-name-baby-romper-set-custom",
    "image_url": "https://i.etsystatic.com/63965631/r/il/1be345/8389816365/il_570xN.8389816365_ovc0.jpg",
    "tags": [
      "baby gift set",
      "baby shower gift",
      "my first Christmas",
      "custom nursery decor",
      "baby announcement",
      "personalized gift",
      "custom baby name",
      "baby birth outfit",
      "nursery gift",
      "baby romper",
      "baby blanket",
      "coming home outfit",
      "baby hospital outfit"
    ],
    "views": 1709,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549593400,
    "title": "Custom Wooden Office Door Sign, Personalized Office Name Plaque with In Meeting Sign, Floral Office Decor, Business Office Gift for Her",
    "search_keyword": "personalized business desk plaque",
    "age_days": 27,
    "num_favorers": 69,
    "momentum_score": 2.46,
    "price": "53.06 USD",
    "url": "https://www.etsy.com/listing/4549593400/custom-wooden-office-door-sign",
    "image_url": "https://i.etsystatic.com/56859158/r/il/051033/8385013575/il_570xN.8385013575_41a6.jpg",
    "tags": [
      "office sign",
      "office door decor",
      "meeting slider",
      "custom wood sign",
      "personalized office",
      "floral office",
      "office accessory",
      "desk name sign",
      "work office decor",
      "gift for coworker",
      "boss office sign",
      "business decor",
      "office wall sign"
    ],
    "views": 1307,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550190902,
    "title": "Personalized Floral Baby Blanket With Name,Custom Wildflower Knit Baby Blanket,Embroidered Rabbit Flower Baby Blanket,Newborn Gift,Baby Gift",
    "search_keyword": "custom floral baby blanket",
    "age_days": 26,
    "num_favorers": 64,
    "momentum_score": 2.37,
    "price": "1710.54 PHP",
    "url": "https://www.etsy.com/listing/4550190902/personalized-floral-baby-blanket-with",
    "image_url": "https://i.etsystatic.com/65666085/r/il/8a4414/8389170401/il_570xN.8389170401_e4tg.jpg",
    "tags": [
      "newborn blanket",
      "embroidered blankets",
      "monogrammed blanket",
      "Girl Baby Blanket",
      "Custom Name Blanket",
      "Newborn Name Blanket",
      "Baby show gift",
      "custom baby gift",
      "nursery blanket",
      "Baby name blanket",
      "coming baby blanket",
      "Name Knitted Throw",
      "Newborn Keepsake"
    ],
    "views": 1731,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557226789,
    "title": "Custom Embroidered Golden Retriever Sweatshirt, Dog Lover Gift",
    "search_keyword": "golden retriever custom crewneck",
    "age_days": 14,
    "num_favorers": 35,
    "momentum_score": 2.33,
    "price": "500000.00 VND",
    "url": "https://www.etsy.com/listing/4557226789/custom-embroidered-golden-retriever",
    "image_url": "https://i.etsystatic.com/54532854/r/il/e0851e/8440418459/il_570xN.8440418459_c4cw.jpg",
    "tags": [
      "Black Lab Mama",
      "Labrador Gift",
      "Custom Dog Shirt",
      "Black Lab Dad",
      "Dog Lover Gift",
      "Pet Memorial Gift",
      "Minimalist Dog Art",
      "Retro Dog Sweater",
      "Lab Mom Crewneck",
      "Labrador Owner",
      "Golden Retriever",
      "Embroidered Sweater",
      "Dog Sweatshirt"
    ],
    "views": 310,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4551387799,
    "title": "Custom Embroidered Heart Locket Initials Sweatshirt, Personalized Bride Tshirt, Vintage Wedding Gift, T-shirt, Hoodie, Sweatshirt",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 24,
    "num_favorers": 56,
    "momentum_score": 2.24,
    "price": "14.95 USD",
    "url": "https://www.etsy.com/listing/4551387799/custom-embroidered-heart-locket-initials",
    "image_url": "https://i.etsystatic.com/66088139/r/il/2632e3/8397848835/il_570xN.8397848835_t6ww.jpg",
    "tags": [
      "personalized bride",
      "Gift for Bride",
      "custom bride sweater",
      "Bride Sweatshirt",
      "bride to be gift",
      "custom embroidered",
      "Bridal Shower Gift",
      "Heart sweatshirt",
      "Engagement Gift",
      "Mrs Sweatshirt",
      "Future Mrs Shirt",
      "coquette sweatshirt",
      "wedding gift"
    ],
    "views": 464,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4561474535,
    "title": "Custom Embroidered Bunny Floral Baby Name Blanket,Personalized Rabbit Wildflowers Knit Baby Blanket,Rabbit Nersury Blanket,Baby Shower Gift",
    "search_keyword": "personalized baby name blanket",
    "age_days": 7,
    "num_favorers": 17,
    "momentum_score": 2.12,
    "price": "1788.44 PHP",
    "url": "https://www.etsy.com/listing/4561474535/custom-embroidered-bunny-floral-baby",
    "image_url": "https://i.etsystatic.com/65682694/r/il/82aac0/8423236022/il_570xN.8423236022_m04t.jpg",
    "tags": [
      "knit baby blanket",
      "custom name blanket",
      "soft baby blanket",
      "personalized blanket",
      "newborn baby gift",
      "name baby blanket",
      "girl name blanket",
      "gift for baby",
      "floral baby blanket",
      "bunny baby blanket",
      "wildflower blanket",
      "custom bunny blanket",
      "welcome baby gift"
    ],
    "views": 410,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4548894454,
    "title": "Custom Flower Night Light for Kids, LED Wooden Bedside Lamp, Teen Girl Room Decor, Unique Birthday Gift for Daughter,Personalized Name Light",
    "search_keyword": "custom night light kids name",
    "age_days": 28,
    "num_favorers": 60,
    "momentum_score": 2.07,
    "price": "2785.59 PHP",
    "url": "https://www.etsy.com/listing/4548894454/custom-flower-night-light-for-kids-led",
    "image_url": "https://i.etsystatic.com/53410189/r/il/17483a/8385152319/il_570xN.8385152319_53g5.jpg",
    "tags": [
      "Custom Name Light",
      "Floral Name Light",
      "Baby Girl Keepsake",
      "Baby Night Light",
      "Custom Night Light",
      "Flower Night Light",
      "Gifts for Kids",
      "Toddler Room Glow",
      "Unique Teenager Gift",
      "Nursery Decoration",
      "Monogram Nightlight",
      "Name Light Gift",
      "Gift for Her"
    ],
    "views": 728,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4552841607,
    "title": "Custom First Birthday Story Book for Baby Boy Girl, Personalized 1st Birthday Gift, One Year Old Keepsake Present",
    "search_keyword": "personalized first birthday story book",
    "age_days": 21,
    "num_favorers": 45,
    "momentum_score": 2.05,
    "price": "34.26 USD",
    "url": "https://www.etsy.com/listing/4552841607/custom-first-birthday-story-book-for",
    "image_url": "https://i.etsystatic.com/62989657/r/il/fdeba4/8360591340/il_570xN.8360591340_novp.jpg",
    "tags": [
      "first birthday book",
      "one year old present",
      "keepsake story book",
      "custom baby book",
      "custom name book",
      "personalized book",
      "girl first birthday",
      "boy first birthday",
      "baby boy girl gift",
      "1st birthday present",
      "1 year old birthday",
      "baby story book gift",
      "book with name"
    ],
    "views": 1362,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4551506618,
    "title": "Personalized Princess Embroidered Sweatshirt, Custom Name On Sleeve, Fairytale Magic Kingdom Shirt, Girls Trip Tee, Disney Girls Trip Shirt",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 24,
    "num_favorers": 51,
    "momentum_score": 2.04,
    "price": "12.84 USD",
    "url": "https://www.etsy.com/listing/4551506618/personalized-princess-embroidered",
    "image_url": "https://i.etsystatic.com/56931962/r/il/63af67/8350836600/il_570xN.8350836600_spu8.jpg",
    "tags": [
      "embroidered princess",
      "custom princess gift",
      "fairytale sweatshirt",
      "magic kingdom tee",
      "disney family shirts",
      "custom disney crew",
      "princess girls trip",
      "magical land shirt",
      "vintage princess",
      "custom castle shirt",
      "disney trip 2026",
      "disney embroidery",
      "princess embrodered"
    ],
    "views": 601,
    "is_personalizable": true
  },
  {
    "listing_id": 4557404756,
    "title": "Personalized Dog Memorial Photo Blanket, Custom Pet Loss Keepsake, Pet Memory Gift, In Loving Memory Blanket",
    "search_keyword": "personalized pet memorial blanket",
    "age_days": 14,
    "num_favorers": 30,
    "momentum_score": 2.0,
    "price": "26.58 USD",
    "url": "https://www.etsy.com/listing/4557404756/personalized-dog-memorial-photo-blanket",
    "image_url": "https://i.etsystatic.com/22775504/r/il/752a7f/8393644334/il_570xN.8393644334_oued.jpg",
    "tags": [
      "Dog Photo Blanket",
      "Gifts for Dog Lovers",
      "Dog Lovers Gift",
      "Custom Dog Blanket",
      "Dog Memorial Gifts",
      "Pet Memorial Gift",
      "Dog Mom Gift",
      "Personalized Blanket",
      "Gift for Dog Owner",
      "Pet Sympathy Gift",
      "Dog Remembrance Gift",
      "Bereavement Gift",
      "Cat Memorial Gift"
    ],
    "views": 688,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4562263053,
    "title": "Personalized Quilted Tote Bag, Custom Wedding Party Gift, Embroidered Name Bag for Bridesmaids, Bridal Shower Gift, Soft Gingham Bag",
    "search_keyword": "personalized bridal party tote bag",
    "age_days": 6,
    "num_favorers": 14,
    "momentum_score": 2.0,
    "price": "12.50 AUD",
    "url": "https://www.etsy.com/listing/4562263053/personalized-quilted-tote-bag-custom",
    "image_url": "https://i.etsystatic.com/53485995/r/il/41a5c1/8429168204/il_570xN.8429168204_l2zb.jpg",
    "tags": [
      "personalized tote",
      "bridesmaid gift",
      "wedding tote bag",
      "custom name bag",
      "bridal shower gift",
      "maid of honor gift",
      "embroidered tote",
      "quilted tote bag",
      "gingham bag",
      "wedding party gift",
      "custom bridesmaid",
      "personalized bag",
      "puffer tote"
    ],
    "views": 300,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557868086,
    "title": "Embroidered Monorail Dachshund Sweatshirt, Holiday Girl Trip Shirt, Magical Land Vacation Crewneck, Doxie Lover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 13,
    "num_favorers": 26,
    "momentum_score": 1.86,
    "price": "42.30 USD",
    "url": "https://www.etsy.com/listing/4557868086/embroidered-monorail-dachshund",
    "image_url": "https://i.etsystatic.com/42749111/r/il/4c3414/8396766404/il_570xN.8396766404_9shs.jpg",
    "tags": [
      "dachshund monorail",
      "disney vacation gift",
      "park day shirt",
      "wiener dog sweater",
      "embroidered doxies",
      "magical theme park",
      "dog mom disney",
      "sausage dog outfit",
      "vacation sweatshirt",
      "cute dog graphic",
      "travel lover gift",
      "retro monorail",
      "disneyland merch"
    ],
    "views": 387,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558553452,
    "title": "Personalized Embroidered Wine Tote Bag, Bridesmaid Gift, Bachelorette Party Bridal Shower Favor, Custom Name Wine  2 Bottle Carrier",
    "search_keyword": "personalized bridal party tote bag",
    "age_days": 12,
    "num_favorers": 23,
    "momentum_score": 1.77,
    "price": "10.68 USD",
    "url": "https://www.etsy.com/listing/4558553452/personalized-embroidered-wine-tote-bag",
    "image_url": "https://i.etsystatic.com/57894963/r/il/29d7dc/8401559010/il_570xN.8401559010_cbiy.jpg",
    "tags": [
      "Custom Wine Tote",
      "Wine Bottle Bag",
      "Bridesmaid Gift",
      "Bachelorette Gift",
      "Bridal Shower Gift",
      "Bride Tribe Gift",
      "Wine Lover Gift",
      "Embroidered Bag",
      "Monogram Wine Bag",
      "Custom Name Bag",
      "Wedding Party Gift",
      "Hostess Wine Gift",
      "Canvas Wine Bag"
    ],
    "views": 533,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550125099,
    "title": "Custom Dog Portrait Woven Blanket  Personalized Pet Photo Tapestry Throw  Custom Dog Dad Gift",
    "search_keyword": "personalized pet memorial blanket",
    "age_days": 26,
    "num_favorers": 47,
    "momentum_score": 1.74,
    "price": "14.99 USD",
    "url": "https://www.etsy.com/listing/4550125099/custom-dog-portrait-woven-blanket",
    "image_url": "https://i.etsystatic.com/25168585/r/il/a88594/8388784249/il_570xN.8388784249_h0os.jpg",
    "tags": [
      "dog photo blanket",
      "pet face blanket",
      "pet portrait blanket",
      "gifts for dog lovers",
      "dog lovers gifts",
      "gifts for dog owners",
      "custom dog blanket",
      "dog memorial gifts",
      "pet memorial gifts",
      "dog loss gifts",
      "cat dad gifts",
      "dog mom gifts",
      "custom pet blanket"
    ],
    "views": 721,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549582721,
    "title": "Embroidered Fall Movie Inspired Canvas Tote Bag, Autumn Movie Series Bag, Where You Lead I Will Follow Tote, Autumn Festival Gift, Movie Fan",
    "search_keyword": "custom embroidered book tote bag",
    "age_days": 27,
    "num_favorers": 47,
    "momentum_score": 1.68,
    "price": "49.99 USD",
    "url": "https://www.etsy.com/listing/4549582721/embroidered-fall-movie-inspired-canvas",
    "image_url": "https://i.etsystatic.com/51285704/r/il/88e02d/8337146916/il_570xN.8337146916_7o1e.jpg",
    "tags": [
      "custom tote bag",
      "movie fan merch",
      "movie canvas tote",
      "stars hollow tote",
      "gilmore girls fall",
      "fall movie series",
      "book lover gift",
      "gift for her",
      "christmas gift",
      "embroidered bag",
      "canvas tote bag",
      "fall coffee bag",
      "fall festival gift"
    ],
    "views": 267,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4563096332,
    "title": "Cup Of Ambition Coffee Mug, Retro 9 to 5 Dolly Parton Lyric Mug, Vintage 70s Typography Ceramic Cup, Morning Coffee Gift 11oz 15oz",
    "search_keyword": "funny retro coworker mug",
    "age_days": 5,
    "num_favorers": 10,
    "momentum_score": 1.67,
    "price": "25.99 USD",
    "url": "https://www.etsy.com/listing/4563096332/cup-of-ambition-coffee-mug-retro-9-to-5",
    "image_url": "https://i.etsystatic.com/65305528/r/il/a2b3e0/8482914591/il_570xN.8482914591_kmv2.jpg",
    "tags": [
      "cup of ambition",
      "9 to 5 coffee mug",
      "dolly parton mug",
      "retro lyric mug",
      "funny work mug",
      "motivational mug",
      "cute office mug",
      "country music mug",
      "retro 70s coffee cup",
      "nashville gift",
      "15oz ceramic mug",
      "11oz coffee mug",
      "gift for coworker"
    ],
    "views": 80,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557777977,
    "title": "Embroidered Monorail Dachshund Sweatshirt Hoodie, Magical Land Vacation Crewneck, Holiday Girl Trip Shirt, Doxie Dog Lover Gift",
    "search_keyword": "embroidered dog mom hoodie",
    "age_days": 13,
    "num_favorers": 23,
    "momentum_score": 1.64,
    "price": "12.99 USD",
    "url": "https://www.etsy.com/listing/4557777977/embroidered-monorail-dachshund",
    "image_url": "https://i.etsystatic.com/57740532/r/il/55be3d/8396462882/il_570xN.8396462882_guo6.jpg",
    "tags": [
      "dachshund monorail",
      "disney vacation gift",
      "park day shirt",
      "wiener dog sweater",
      "embroidered doxies",
      "magical theme park",
      "dog mom disney",
      "sausage dog outfit",
      "vacation sweatshirt",
      "cute dog graphic",
      "travel lover gift",
      "retro monorail",
      "disneyland merch"
    ],
    "views": 256,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553124357,
    "title": "Personalized Forest Animal Blanket, Custom Baby Name Blanket, Vintage Storybook Nursery Decor, Toddler Bear Throw, Kids Birthday Gift",
    "search_keyword": "personalized baby name blanket",
    "age_days": 21,
    "num_favorers": 36,
    "momentum_score": 1.64,
    "price": "22.83 USD",
    "url": "https://www.etsy.com/listing/4553124357/personalized-forest-animal-blanket",
    "image_url": "https://i.etsystatic.com/63736349/r/il/532e4f/8362706142/il_570xN.8362706142_dee5.jpg",
    "tags": [
      "Custom Baby Blanket",
      "Little Bear Blanket",
      "Personalized Blanket",
      "Vintage Nursery",
      "Farm Animal Throw",
      "Toddler Birthday",
      "Baby Shower Gift",
      "Cozy Bear Blanket",
      "Kids Plaid Blanket",
      "Custom Name Blanket",
      "Little Bear Nursery",
      "Soft Flannel Throw",
      "Nostalgic Bear Gift"
    ],
    "views": 754,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557306891,
    "title": "Personalized Dog Sweater Custom Name, Hand Embroidered Puppy Jumper, Cozy Knit Pet Clothes, Small Dog Gift, Dog Mom Gift, Pet Birthday Gift",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 14,
    "num_favorers": 24,
    "momentum_score": 1.6,
    "price": "25.90 USD",
    "url": "https://www.etsy.com/listing/4557306891/personalized-dog-sweater-custom-name",
    "image_url": "https://i.etsystatic.com/60036242/r/il/04b78a/8393189908/il_570xN.8393189908_2ct9.jpg",
    "tags": [
      "Puppy Sweatshirt",
      "Small Dog Clothes",
      "Sweatshirt for Dog",
      "Dog Sweater",
      "Pets Pyjamas",
      "Cat sports shirt",
      "cat clothes",
      "cat sweater",
      "Custom Dog Clothes",
      "Custom Pet Gift",
      "Dog Birthday Gift",
      "Cute Dog Outfit",
      "Pet Lover Gift"
    ],
    "views": 328,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549569475,
    "title": "Personalized Embroidered Speech Language Pathologist Quarter Zip, Speech Therapy Sweatshirt, SLP Graduation Gift, Speech Therapist Gift",
    "search_keyword": "speech therapy sweatshirt",
    "age_days": 27,
    "num_favorers": 43,
    "momentum_score": 1.54,
    "price": "49.76 USD",
    "url": "https://www.etsy.com/listing/4549569475/personalized-embroidered-speech-language",
    "image_url": "https://i.etsystatic.com/41495367/r/il/f4eb57/8384920391/il_570xN.8384920391_3yuf.jpg",
    "tags": [
      "slp quarter zip",
      "embroidered slp",
      "speech pathologist",
      "slp graduation gift",
      "therapist gift",
      "custom slp sweater",
      "speech teacher",
      "back to school gift",
      "teacher appreciation",
      "gift for slp",
      "therapy shirt",
      "speech therapy gift",
      "custom teacher gifts"
    ],
    "views": 287,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4560448328,
    "title": "Embroidered Radiology Tech Quarter Zip Sweatshirt, Xray Tech Sweatshirt, Radiology Student Sweatshirt, Radiology Gift",
    "search_keyword": "radiology tech sweatshirt",
    "age_days": 9,
    "num_favorers": 15,
    "momentum_score": 1.5,
    "price": "24.99 USD",
    "url": "https://www.etsy.com/listing/4560448328/embroidered-radiology-tech-quarter-zip",
    "image_url": "https://i.etsystatic.com/66428476/r/il/ce345b/8463481951/il_570xN.8463481951_1jm0.jpg",
    "tags": [
      "custom quarter zip",
      "quater zip sweater",
      "radiology sweatshirt",
      "x ray tech shirt",
      "radiology shirt",
      "xray tech gift",
      "radiology tech gift",
      "rad tech gift",
      "xray sweatshirt",
      "radiology student",
      "skeleton sweatshirt",
      "medical sweatshirt"
    ],
    "views": 88,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4563086545,
    "title": "Cup Of Ambition Two-Tone Coffee Mug, Pink Handle 9 to 5 Dolly Parton Lyric Mug, Retro 70s Typographic Ceramic Cup, Cute Office Coworker Gift",
    "search_keyword": "funny retro coworker mug",
    "age_days": 5,
    "num_favorers": 9,
    "momentum_score": 1.5,
    "price": "25.99 USD",
    "url": "https://www.etsy.com/listing/4563086545/cup-of-ambition-two-tone-coffee-mug-pink",
    "image_url": "https://i.etsystatic.com/65305528/r/il/df31ff/8435170188/il_570xN.8435170188_84rd.jpg",
    "tags": [
      "cup of ambition",
      "9 to 5 coffee mug",
      "dolly parton mug",
      "retro lyric mug",
      "funny work mug",
      "motivational mug",
      "cute office mug",
      "country music mug",
      "retro 70s coffee cup",
      "nashville gift",
      "15oz ceramic mug",
      "11oz coffee mug",
      "gift for coworker"
    ],
    "views": 77,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4552056099,
    "title": "Retro Monorail Dachshund Embroidered Sweater, Disney World Vacation Shirt, Doxie Lover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 23,
    "num_favorers": 33,
    "momentum_score": 1.38,
    "price": "16.65 USD",
    "url": "https://www.etsy.com/listing/4552056099/retro-monorail-dachshund-embroidered",
    "image_url": "https://i.etsystatic.com/58154715/r/il/3f1cc1/8354853610/il_570xN.8354853610_npy5.jpg",
    "tags": [
      "embroidered apparel",
      "puppy lover gift",
      "dog theme shirt",
      "custom embroidery",
      "aesthetic sweater",
      "cozy fall fashion",
      "doggo graphic tee",
      "handmade clothing",
      "gift for dog dad",
      "whimsical fashion",
      "unisex sweatshirt",
      "pet owner gift",
      "canine illustration"
    ],
    "views": 469,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4559825189,
    "title": "Personalized Swan Baby Name Blanket,Custom Floral Embroidered Baby Blanket,Custom Baby Knitted Blanket,Newborn Keepsake,Baby Shower Gift",
    "search_keyword": "personalized baby name blanket",
    "age_days": 10,
    "num_favorers": 15,
    "momentum_score": 1.36,
    "price": "2128.71 PHP",
    "url": "https://www.etsy.com/listing/4559825189/personalized-swan-baby-name",
    "image_url": "https://i.etsystatic.com/65652011/r/il/c0f1e0/8411174294/il_570xN.8411174294_rlhw.jpg",
    "tags": [
      "Baby Keepsake Gift",
      "custom name blanket",
      "Embroidered Blankets",
      "cotton baby blanket",
      "Custom Blanket baby",
      "Welcome Baby Blanket",
      "Blanket Floral Duck",
      "flower baby blanket",
      "Newborn Keepsake",
      "nursery blanket",
      "Baby Keepsake",
      "Blanket Floral Swan",
      "Name Knitted Throw"
    ],
    "views": 487,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550255348,
    "title": "EMBROIDERED Dog Boop Halloween Sweater, Dog Skeleton Hoodie, Dog Lover Gifts, Spooky Dog Shirt, Dog Mom Crewneck, Funny Dog Sweatshirt",
    "search_keyword": "embroidered dog mom hoodie",
    "age_days": 26,
    "num_favorers": 35,
    "momentum_score": 1.3,
    "price": "12.99 USD",
    "url": "https://www.etsy.com/listing/4550255348/embroidered-dog-boop-halloween-sweater",
    "image_url": "https://i.etsystatic.com/62985822/r/il/34b8a1/8341787080/il_570xN.8341787080_rmac.jpg",
    "tags": [
      "halloween ghost",
      "halloween tee",
      "Ghost Shirt",
      "dog lover shirt",
      "dog sweater",
      "spooky ghost shirt",
      "animal lover gift",
      "Dog Owner Gift",
      "dog mom sweatshirt",
      "funny dog tees",
      "pet lover gift",
      "fall graphic tee",
      "Skeleton shirt"
    ],
    "views": 197,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4552035631,
    "title": "Custom Embroidered College Varsity Sweatshirt, Floral Applique Letter Sweatshirt, Preppy Patchwork Embroidery Crewneck Gift",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 23,
    "num_favorers": 31,
    "momentum_score": 1.29,
    "price": "33.69 USD",
    "url": "https://www.etsy.com/listing/4552035631/custom-embroidered-college-varsity",
    "image_url": "https://i.etsystatic.com/66822697/r/il/528019/8354691364/il_570xN.8354691364_1if3.jpg",
    "tags": [
      "college sweatshirt",
      "school crewneck",
      "varsity sweatshirt",
      "team sweatshirt",
      "custom college",
      "applique sweater",
      "patchwork shirt",
      "preppy sweatshirt",
      "school spirit",
      "volleyball gift",
      "team mom gift",
      "senior gift",
      "embroidered top"
    ],
    "views": 671,
    "is_personalizable": true
  },
  {
    "listing_id": 4557388902,
    "title": "Custom Patchwork Appliqué Mascot Sweatshirt | School Spirit Crewneck Wear",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 14,
    "num_favorers": 19,
    "momentum_score": 1.27,
    "price": "40.00 USD",
    "url": "https://www.etsy.com/listing/4557388902/custom-patchwork-applique-mascot",
    "image_url": "https://i.etsystatic.com/44554160/r/il/96547e/8441485533/il_570xN.8441485533_56ga.jpg",
    "tags": [
      "mascot",
      "school spirit",
      "team spirit",
      "applique sweatshirt",
      "spirit wear",
      "embroidered mascot",
      "custom spirit wear"
    ],
    "views": 348,
    "is_personalizable": true
  },
  {
    "listing_id": 4558470315,
    "title": "Personalized Baby Blanket, Birth Stats Blanket with Custom Name, Wildflower Embroidered Newborn Keepsake, New Baby Gift, Baby Shower Gift",
    "search_keyword": "custom floral baby blanket",
    "age_days": 12,
    "num_favorers": 16,
    "momentum_score": 1.23,
    "price": "19.98 USD",
    "url": "https://www.etsy.com/listing/4558470315/personalized-birth-stats-baby-blanket",
    "image_url": "https://i.etsystatic.com/66212237/r/il/235f95/8401246344/il_570xN.8401246344_dwae.jpg",
    "tags": [
      "birth stats blanket",
      "custom name blanket",
      "baby name blanket",
      "personalized blanket",
      "knit baby blanket",
      "embroidered blanket",
      "wildflower blanket",
      "floral baby blanket",
      "neutral baby blanket",
      "baby shower blanket",
      "grandma baby gift",
      "first grandchild",
      "gift for new mom"
    ],
    "views": 302,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4554866967,
    "title": "Custom Name Frozen Elsa Night Light, Personalised Frozen Night Light, Frozen Fan Gift, Birthday Gift For Daughter, Christmas Gift For Girl",
    "search_keyword": "custom night light kids name",
    "age_days": 18,
    "num_favorers": 23,
    "momentum_score": 1.21,
    "price": "33.00 USD",
    "url": "https://www.etsy.com/listing/4554866967/custom-name-frozen-elsa-night-light",
    "image_url": "https://i.etsystatic.com/63926352/r/il/eb8a91/8374960264/il_570xN.8374960264_lfw3.jpg",
    "tags": [
      "frozen night light",
      "Elsa frozen gift",
      "Kids Night Light",
      "Nursery Light",
      "night light baby",
      "Nursery night light",
      "kids christmas gift",
      "girls room decor",
      "Elsa night light",
      "Disney light",
      "Elsa Frozen",
      "Frozen themed gift",
      "Elsa Princess decor"
    ],
    "views": 269,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557204445,
    "title": "Minimally striped mug, Custom ceramic cup with pet portrait, Handmade personalized cat and dog statue cup, 400ml cup",
    "search_keyword": "custom pet portrait mug",
    "age_days": 14,
    "num_favorers": 18,
    "momentum_score": 1.2,
    "price": "18.15 EUR",
    "url": "https://www.etsy.com/listing/4557204445/minimally-striped-mug-custom-ceramic-cup",
    "image_url": "https://i.etsystatic.com/13079015/r/il/71c32c/8440244305/il_570xN.8440244305_pm5t.jpg",
    "tags": [
      "Custom Cup",
      "Pet Mug",
      "Taza Cafe Westie",
      "Mugs",
      "Custom pet portrait",
      "Ceramic Mug Handmade",
      "Dog memorial gift",
      "Pet memorial gift",
      "Cat memorial gift",
      "Pet remembrance gift",
      "Home decor",
      "Personalized gift",
      "Drinkware"
    ],
    "views": 268,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4562906232,
    "title": "Embroidered Monorail Dachshund Sweatshirt, Personalized Family Vacation Crewneck, Custom Disney Trip Pullover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 5,
    "num_favorers": 7,
    "momentum_score": 1.17,
    "price": "41.10 GBP",
    "url": "https://www.etsy.com/listing/4562906232/embroidered-monorail-dachshund",
    "image_url": "https://i.etsystatic.com/67021583/r/il/3395d3/8433610286/il_570xN.8433610286_iv81.jpg",
    "tags": [
      "disney sweatshirt",
      "disney world shirt",
      "disney trip shirt",
      "disney vacation",
      "family vacation",
      "disney crewneck",
      "theme park shirt",
      "disney gift",
      "vacation sweatshirt",
      "custom disney gift",
      "family trip shirt",
      "cozy pullover",
      "embroidered"
    ],
    "views": 36,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557778469,
    "title": "Embroidered Monorail Dachshund Sweatshirt Hoodie, Magical Land Vacation Crewneck, Holiday Girl Trip Shirt, Doxie Dog Lover Gift",
    "search_keyword": "embroidered dog mom hoodie",
    "age_days": 13,
    "num_favorers": 16,
    "momentum_score": 1.14,
    "price": "12.99 USD",
    "url": "https://www.etsy.com/listing/4557778469/embroidered-monorail-dachshund",
    "image_url": "https://i.etsystatic.com/57740532/r/il/41ae7d/8396466032/il_570xN.8396466032_jmuz.jpg",
    "tags": [
      "dachshund monorail",
      "disney vacation gift",
      "park day shirt",
      "wiener dog sweater",
      "embroidered doxies",
      "magical theme park",
      "dog mom disney",
      "sausage dog outfit",
      "vacation sweatshirt",
      "cute dog graphic",
      "travel lover gift",
      "retro monorail",
      "disneyland merch"
    ],
    "views": 133,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553650418,
    "title": "Fall Pumpkin & Books Woven Blanket | Autumn Book Blanket | Cozy Book Lover Gift",
    "search_keyword": "book lover woven blanket",
    "age_days": 20,
    "num_favorers": 24,
    "momentum_score": 1.14,
    "price": "54.95 USD",
    "url": "https://www.etsy.com/listing/4553650418/fall-pumpkin-books-woven-blanket-autumn",
    "image_url": "https://i.etsystatic.com/51745103/r/il/b5ab98/8475375307/il_570xN.8475375307_pol3.jpg",
    "tags": [
      "bookish blanket",
      "fall book blanket",
      "book lover gift",
      "autumn blanket",
      "pumpkin blanket",
      "reader gift",
      "fall home decor",
      "booktok gift",
      "cozy fall decor",
      "book club gift",
      "book blanket",
      "fall woven blanket",
      "autumn book blanket"
    ],
    "views": 154,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4562140424,
    "title": "Storytime Basket for Baby, Personalized Baby book Basket, A New Chapter Begins, Just One More Story, Baby Shower Gifts, Nursery Storage",
    "search_keyword": "personalized first birthday story book",
    "age_days": 6,
    "num_favorers": 8,
    "momentum_score": 1.14,
    "price": "32.80 USD",
    "url": "https://www.etsy.com/listing/4562140424/baby-shower-gifts-storytime-basket-for",
    "image_url": "https://i.etsystatic.com/58241263/r/il/ae88f3/8475870873/il_570xN.8475870873_5yta.jpg",
    "tags": [
      "welcome baby gift",
      "first birthday gift",
      "nursery storage",
      "newborn gift",
      "Baby shower registry",
      "nursery basket",
      "baby basket for boy",
      "baby basket for girl",
      "baby shower gift",
      "babybook organizer",
      "Book Storage Basket",
      "Baby Book Organizer",
      "kids book storage"
    ],
    "views": 68,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4548040875,
    "title": "Personalized Kids Seersucker Library Bag, Embroidered School Tote, Custom Book Bag, Toddler Daycare, Back To School Gift",
    "search_keyword": "custom embroidered book tote bag",
    "age_days": 30,
    "num_favorers": 35,
    "momentum_score": 1.13,
    "price": "14.08 USD",
    "url": "https://www.etsy.com/listing/4548040875/personalized-kids-seersucker-library-bag",
    "image_url": "https://i.etsystatic.com/62865122/r/il/3bcfc5/8326080290/il_570xN.8326080290_e3ko.jpg",
    "tags": [
      "kids library bag",
      "seersucker bag",
      "book bag kids",
      "school tote bag",
      "personalized bag",
      "embroidered bag",
      "preschool bag",
      "kindergarten bag",
      "custom tote bag",
      "kids book tote",
      "library tote",
      "back to school",
      "toddler school bag"
    ],
    "views": 882,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4561814591,
    "title": "Embroidered Monorail Dachshund Sweatshirt, Personalized Magical Land Vacation Crewneck, Holiday Girl Trip Shirt, Doxie Lover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 7,
    "num_favorers": 9,
    "momentum_score": 1.12,
    "price": "53.00 USD",
    "url": "https://www.etsy.com/listing/4561814591/embroidered-monorail-dachshund",
    "image_url": "https://i.etsystatic.com/58533509/r/il/9396d6/8473787861/il_570xN.8473787861_guzm.jpg",
    "tags": [
      "dachshund monorail",
      "disney vacation gift",
      "park day shirt",
      "wiener dog sweater",
      "embroidered doxies",
      "magical theme park",
      "dog mom disney",
      "sausage dog outfit",
      "vacation sweatshirt",
      "cute dog graphic",
      "travel lover gift",
      "retro monorail",
      "disneyland merch"
    ],
    "views": 117,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4551483704,
    "title": "Embroidered Personalized Tote Bag, Teacher Appreciation Gift, Book Tote Bag, First Day Of School Classroom Gift",
    "search_keyword": "custom embroidered book tote bag",
    "age_days": 24,
    "num_favorers": 28,
    "momentum_score": 1.12,
    "price": "28.90 USD",
    "url": "https://www.etsy.com/listing/4551483704/embroidered-personalized-tote-bag",
    "image_url": "https://i.etsystatic.com/58347731/r/il/7fb6f9/8350646760/il_570xN.8350646760_olwq.jpg",
    "tags": [
      "teacher bag",
      "teacher gifts",
      "teacher appreciation",
      "first day of school",
      "book bag",
      "book tote bag",
      "work bag",
      "custom tote bag",
      "embroidered bag",
      "tote bags for women",
      "farmers market bag",
      "monogram tote bag",
      "weekender bag"
    ],
    "views": 613,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4554539255,
    "title": "My First Rodeo Birthday Book, Personalized First Rodeo Birthday Boy Gift, Western Cowboy Keepsake Story for 1 Year Old Boy Turning One",
    "search_keyword": "personalized first birthday story book",
    "age_days": 19,
    "num_favorers": 22,
    "momentum_score": 1.1,
    "price": "26.00 EUR",
    "url": "https://www.etsy.com/listing/4554539255/my-first-rodeo-birthday-book",
    "image_url": "https://i.etsystatic.com/64164716/r/il/4b6d8a/8441866779/il_570xN.8441866779_2hln.jpg",
    "tags": [
      "first rodeo birthday",
      "my first rodeo",
      "first rodeo",
      "1 year old boy gifts",
      "toddler boy gift",
      "cowboy nursery",
      "first birthday boy",
      "1 year old gifts",
      "western gifts",
      "first rodeo book",
      "cowgirl birthday",
      "western nursery",
      "cowboy 1st birthday"
    ],
    "views": 405,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4556531113,
    "title": "Custom puff print, School name, Puff vinyl, School spirit, cougars",
    "search_keyword": "puff print custom sweatshirt",
    "age_days": 15,
    "num_favorers": 16,
    "momentum_score": 1.0,
    "price": "26.95 USD",
    "url": "https://www.etsy.com/listing/4556531113/custom-puff-print-school-name-puff-vinyl",
    "image_url": "https://i.etsystatic.com/52708601/r/il/435be6/8436063255/il_570xN.8436063255_rhk0.jpg",
    "tags": [
      "custom sweatshirt",
      "school sweatshirt",
      "puff print",
      "bulldogs sweatshirt",
      "custom school wear",
      "team sweatshirt",
      "mascot sweatshirt",
      "game day sweatshirt",
      "puff vinyl",
      "custom school shirt",
      "cougars sweatshirt",
      "byu sweastshirt",
      "sports mom"
    ],
    "views": 269,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550700640,
    "title": "Custom Dog Portrait Woven Blanket with Name Personalized Pattern Tapestry Throw Pet Memorial Keepsake",
    "search_keyword": "personalized baby name blanket",
    "age_days": 25,
    "num_favorers": 26,
    "momentum_score": 1.0,
    "price": "14.99 USD",
    "url": "https://www.etsy.com/listing/4550700640/custom-dog-portrait-woven-blanket-with",
    "image_url": "https://i.etsystatic.com/25168585/r/il/c9e951/8344974292/il_570xN.8344974292_jm3z.jpg",
    "tags": [
      "dog photo blanket",
      "pet face blanket",
      "pet portrait blanket",
      "gifts for dog lovers",
      "dog lovers gifts",
      "gifts for dog owners",
      "custom dog blanket",
      "dog memorial gifts",
      "pet memorial gifts",
      "dog loss gifts",
      "cat dad gifts",
      "dog mom gifts",
      "custom pet blanket"
    ],
    "views": 505,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550006458,
    "title": "Custom Pet Blanket, Personalized Dog Blanket, Pet Photo Blanket, Pet Memorial Blanket",
    "search_keyword": "personalized pet memorial blanket",
    "age_days": 26,
    "num_favorers": 27,
    "momentum_score": 1.0,
    "price": "49.98 USD",
    "url": "https://www.etsy.com/listing/4550006458/custom-pet-blanket-personalized-dog",
    "image_url": "https://i.etsystatic.com/23829589/r/il/12bf63/8340101308/il_570xN.8340101308_6wsd.jpg",
    "tags": [
      "dog memorial gifts",
      "dog remembrance gift",
      "Custom Pet Blanket",
      "Pet Photo Blanket",
      "Pet Memorial Blanket",
      "Custom Dog Blanket",
      "custom cat blanket",
      "dog blanket",
      "dog mom gift",
      "pet blanket",
      "gift for dog lovers",
      "pet memorial gifts",
      "dog mom gifts"
    ],
    "views": 449,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550810059,
    "title": "Personalized Name Night Light For Kids, Custom Baby Nursery Decor, Cute Forest Ocean Farm Animal Lamp, Newborn Gift for Boys and Girls",
    "search_keyword": "custom night light kids name",
    "age_days": 25,
    "num_favorers": 26,
    "momentum_score": 1.0,
    "price": "1845.52 PHP",
    "url": "https://www.etsy.com/listing/4550810059/personalized-name-night-light-for-kids",
    "image_url": "https://i.etsystatic.com/53410189/r/il/2e6694/8345843256/il_570xN.8345843256_iday.jpg",
    "tags": [
      "Baby Night Light",
      "Kids Bedroom Light",
      "Nursery Night light",
      "Custom Night Light",
      "Gift for the Birth",
      "Kid Newborn Gift",
      "Baby Shower Gift",
      "New Baby Gifts",
      "baby gift idea",
      "Night Light Children",
      "Bedside Lamp",
      "Kids Room Decor",
      "Child Bedroom Light"
    ],
    "views": 385,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4548387793,
    "title": "Personalized First Prayer Book for Kids with Photo & Name, Christian Everyday Bedtime Keepsake, Baptism Christening Boy Girl Baby Dedication",
    "search_keyword": "custom bedtime story book for kids",
    "age_days": 29,
    "num_favorers": 29,
    "momentum_score": 0.97,
    "price": "27.58 CAD",
    "url": "https://www.etsy.com/listing/4548387793/personalized-first-prayer-book-for-kids",
    "image_url": "https://i.etsystatic.com/65304954/r/il/c3fe20/8340123974/il_570xN.8340123974_f419.jpg",
    "tags": [
      "baby book name",
      "toddler name book",
      "custom name book",
      "baby dedication gift",
      "naming day gift",
      "christian story book",
      "gods promises",
      "baby story book",
      "godmother gift",
      "custom storybook",
      "christianity gift",
      "bedtime routine",
      "Christening gifts"
    ],
    "views": 655,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4554357309,
    "title": "Gothic Skeleton Wedding Wooden Block, Personalized Dancing Couple Decor, Custom Halloween Anniversary Gift",
    "search_keyword": "custom acrylic wedding sign",
    "age_days": 19,
    "num_favorers": 19,
    "momentum_score": 0.95,
    "price": "32.00 GBP",
    "url": "https://www.etsy.com/listing/4554357309/gothic-skeleton-wedding-wooden-block",
    "image_url": "https://i.etsystatic.com/56414419/r/il/36acb2/8371425626/il_570xN.8371425626_hkjt.jpg",
    "tags": [
      "gothic skeleton",
      "skeleton decor",
      "wedding keepsake",
      "halloween couple",
      "custom couple gift",
      "spooky wedding",
      "gothic home decor",
      "dancing skeleton",
      "anniversary gift",
      "witchy decor",
      "custom names",
      "halloween wedding",
      "romantic skeleton"
    ],
    "views": 268,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558439657,
    "title": "Embroidered Doxie Monorail Sweatshirt, Funny Dachshund Monorail Train Shirt, Cute Dog Lover Crewneck Sweater, Retro Theme Sausage Dog Shirt",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 12,
    "num_favorers": 12,
    "momentum_score": 0.92,
    "price": "18.56 USD",
    "url": "https://www.etsy.com/listing/4558439657/embroidered-doxie-monorail-sweatshirt",
    "image_url": "https://i.etsystatic.com/61683128/r/il/6b270c/8401108440/il_570xN.8401108440_1nbt.jpg",
    "tags": [
      "embroidered shirt",
      "monorail dog shirt",
      "dachshund monorail",
      "funny dog sweater",
      "park monorail shirt",
      "disney monorail",
      "wiener dog shirt",
      "dachshund sweater",
      "cute dog lover gift",
      "disney trip shirt",
      "monorail train shirt",
      "funny park sweater",
      "dachshund lover gift"
    ],
    "views": 113,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558613103,
    "title": "Personalized Cross Baby Blanket, Christian Nursery Decor, Custom Name Baby Throw, Baptism Keepsake Blanket, Religious Baby Gift",
    "search_keyword": "custom floral baby blanket",
    "age_days": 12,
    "num_favorers": 12,
    "momentum_score": 0.92,
    "price": "22.41 USD",
    "url": "https://www.etsy.com/listing/4558613103/personalized-cross-baby-blanket",
    "image_url": "https://i.etsystatic.com/66711240/r/il/6ef95c/8450398149/il_570xN.8450398149_payi.jpg",
    "tags": [
      "christian blanket",
      "cross baby blanket",
      "baptism blanket",
      "christening gift",
      "religious baby",
      "christian nursery",
      "baby name blanket",
      "custom baby gift",
      "personalized baby",
      "embroidered blanket",
      "baptism keepsake",
      "baby shower gift",
      "infant blanket"
    ],
    "views": 198,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555533269,
    "title": "Personalized Fairy First Birthday StoryBook, Custom Girl Birthday Gift, Keepsake Storybook, 1st Birthday Book for Baby Girl",
    "search_keyword": "personalized first birthday story book",
    "age_days": 17,
    "num_favorers": 16,
    "momentum_score": 0.89,
    "price": "20.99 EUR",
    "url": "https://www.etsy.com/listing/4555533269/personalized-fairy-first-birthday",
    "image_url": "https://i.etsystatic.com/66882848/r/il/553a74/8379893474/il_570xN.8379893474_dx40.jpg",
    "tags": [
      "baby storybook",
      "custom storybook",
      "custom baby book",
      "toddler book",
      "bedtime story",
      "kids bedtime book",
      "1st birthday gift",
      "first birthday",
      "birthday keepsake",
      "Fairy First Birthday",
      "Girls 1st Birthday",
      "fairy princess book",
      "birthday girl"
    ],
    "views": 450,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550298202,
    "title": "Personalized Christian Goose Book, Custom Farm Storybook With Name, Baptism Gift for Girl, Bedtime Keepsake for Toddlers",
    "search_keyword": "custom bedtime story book for kids",
    "age_days": 26,
    "num_favorers": 24,
    "momentum_score": 0.89,
    "price": "22.50 EUR",
    "url": "https://www.etsy.com/listing/4550298202/personalized-christian-goose-book-custom",
    "image_url": "https://i.etsystatic.com/24550011/r/il/4b5994/8390044191/il_570xN.8390044191_l1qa.jpg",
    "tags": [
      "goose story book",
      "farm name book",
      "toddler name book",
      "custom storybook",
      "christianity gift",
      "bedtime routine",
      "1 year old gift",
      "baby dedication gift",
      "girl keepsake book",
      "christian story book",
      "personalized book",
      "faith baby gift",
      "silly goose gift"
    ],
    "views": 263,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558823986,
    "title": "Cute Doxie Monorail Embroidered Sweatshirt, Retro Theme Sausage Dog Shirt, Dachshund Lover Gift,  Personalized Name Embroidered Sweater",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 12,
    "num_favorers": 11,
    "momentum_score": 0.85,
    "price": "53.00 USD",
    "url": "https://www.etsy.com/listing/4558823986/custom-dog-monorail-sweatshirt",
    "image_url": "https://i.etsystatic.com/58533509/r/il/17cca1/8403799524/il_570xN.8403799524_d4rx.jpg",
    "tags": [
      "embroidered apparel",
      "dachshund lover",
      "funny dog shirt",
      "disney inspired",
      "cozy park style",
      "doxie mom",
      "custom embroidery",
      "puppy gift idea",
      "disney fan gift",
      "pet embroidered",
      "pet custom shirt",
      "dog portrait custom",
      "dog embroidered"
    ],
    "views": 227,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4562767503,
    "title": "Embroidered Monorail Dachshund Quarter Zip Sweatshirt, Walt Disney World Doxie Pullover, Vacation Theme Park Apparel",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 5,
    "num_favorers": 5,
    "momentum_score": 0.83,
    "price": "9.99 USD",
    "url": "https://www.etsy.com/listing/4562767503/embroidered-monorail-dachshund-quarter",
    "image_url": "https://i.etsystatic.com/67203692/r/il/71a785/8432743166/il_570xN.8432743166_kvl8.jpg",
    "tags": [
      "dachshund monorail",
      "disney vacation gift",
      "park day shirt",
      "wiener dog sweater",
      "embroidered doxies",
      "magical theme park",
      "dog mom disney",
      "sausage dog outfit",
      "vacation top",
      "cute dog graphic",
      "travel lover gift",
      "retro monorail",
      "wdw merch"
    ],
    "views": 35,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4559782736,
    "title": "Personalized Pet Portrait Pottery Mug, Custom Photo Dog Cup, Dog Cat Lover Gifts",
    "search_keyword": "custom pet portrait mug",
    "age_days": 10,
    "num_favorers": 9,
    "momentum_score": 0.82,
    "price": "30.95 USD",
    "url": "https://www.etsy.com/listing/4559782736/personalized-pet-portrait-pottery-mug",
    "image_url": "https://i.etsystatic.com/63567275/r/il/4e1408/8410759994/il_570xN.8410759994_ri7c.jpg",
    "tags": [
      "Pet Portrait Mug",
      "custom dog lover mug",
      "cat owner gift mug",
      "dog remembrance gift",
      "dog memorial gifts",
      "gift for pet owner",
      "dog lover gift",
      "Custom Cat Mug",
      "dog coffee mug",
      "dog portrait",
      "custom dog gifts",
      "custom cat photo",
      "dog pottery mug"
    ],
    "views": 183,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557894514,
    "title": "Gingerbread Family PNG Bundle, Christmas Clipart, Holiday Sublimation Designs (100 PNG)",
    "search_keyword": "personalized family watercolor canvas",
    "age_days": 13,
    "num_favorers": 11,
    "momentum_score": 0.79,
    "price": "3.29 GBP",
    "url": "https://www.etsy.com/listing/4557894514/gingerbread-family-png-bundle-christmas",
    "image_url": "https://i.etsystatic.com/65860116/r/il/343d72/8397148400/il_570xN.8397148400_ru0f.jpg",
    "tags": [
      "festive gingerbread",
      "Christmas family png",
      "christmas clipart",
      "sublimation graphics",
      "watercolour holiday",
      "family ornament svg",
      "cartoon family print",
      "digital wall art",
      "personalised clipart",
      "christmas pet dtf",
      "xmas character png",
      "cute holiday digital",
      "2026 bauble clipart"
    ],
    "views": 85,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4561095525,
    "title": "Drachen Sweatshirt bestickt | Geschenk für Fantasy Leser | Bookish Merch Vierter Flügel | Drachenmotiv",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 8,
    "num_favorers": 7,
    "momentum_score": 0.78,
    "price": "49.00 EUR",
    "url": "https://www.etsy.com/listing/4561095525/drachen-sweatshirt-bestickt-o-geschenk",
    "image_url": "https://i.etsystatic.com/42420661/r/il/b9d523/8468544621/il_570xN.8468544621_clqj.jpg",
    "tags": [
      "Fourth Wing",
      "Drachen Sweatshirt",
      "Wing Leader",
      "Vierter Flügel",
      "Dragon Sweater",
      "Drachen Sweatshirt bestickt",
      "Fantasy Reader Geschenk",
      "Fantasy Geschenk",
      "Fantasy Pullover",
      "Buchreihen",
      "Bookish Merch",
      "Geschenk Fantasy",
      "Geschenk Fourth Wing"
    ],
    "views": 46,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550801815,
    "title": "Embroidered Dachshund Sweatshirt – Cotton Polyester Blend Comfort",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 25,
    "num_favorers": 20,
    "momentum_score": 0.77,
    "price": "17.00 USD",
    "url": "https://www.etsy.com/listing/4550801815/embroidered-dachshund-sweatshirt-cotton",
    "image_url": "https://i.etsystatic.com/64544059/r/il/cb68f6/8393657335/il_570xN.8393657335_n3li.jpg",
    "tags": [
      "Embroidered Crewneck",
      "Embroidered Design",
      "Custom Embroidery",
      "Paris Gift",
      "Dachshund Crewneck",
      "weiner dog",
      "Adorable Dog Shirt",
      "Custom Pet Apparel",
      "Cute Dachshund",
      "Dachshund Gift",
      "Dachshund mama",
      "Dachshund daddy",
      "weiner sweatshirt"
    ],
    "views": 348,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4547896994,
    "title": "Embroidered Teddy Bears Halloween Sweatshirt, Vintage 90s Trick or Treat Crewneck, Haunted House Shirt, Pumpkin Lover Gift",
    "search_keyword": "cute retro halloween crewneck",
    "age_days": 30,
    "num_favorers": 23,
    "momentum_score": 0.74,
    "price": "52.99 USD",
    "url": "https://www.etsy.com/listing/4547896994/embroidered-teddy-bears-halloween",
    "image_url": "https://i.etsystatic.com/41681139/r/il/13d318/8372836637/il_570xN.8372836637_84dr.jpg",
    "tags": [
      "Spooky Season Tee",
      "Halloween shirt",
      "pumpkin season shirt",
      "Pumpkin Shirt",
      "Vintage Halloween",
      "Fall cozy sweater",
      "embroidered shirt",
      "retro halloween tee",
      "spooky cute sweater",
      "90s halloween shirt",
      "halloween aesthetic",
      "Trick or Treat",
      "teddy bear halloween"
    ],
    "views": 197,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555651937,
    "title": "From The Windows To The Walls Sweatshirt, Funny Halloween Haunted Halls Crewneck, Retro Spooky Season Gift",
    "search_keyword": "cute retro halloween crewneck",
    "age_days": 17,
    "num_favorers": 13,
    "momentum_score": 0.72,
    "price": "13.99 USD",
    "url": "https://www.etsy.com/listing/4555651937/from-the-windows-to-the-walls-sweatshirt",
    "image_url": "https://i.etsystatic.com/53513393/r/il/2065e7/8380786774/il_570xN.8380786774_a4ax.jpg",
    "tags": [
      "From The Windows",
      "Haunted Halls",
      "Sweater Hoodie",
      "Funny Halloween Tee",
      "Mid Century Shirt",
      "Spooky Teacher",
      "Haunted House",
      "Funny Spooky Season",
      "Cute Boo",
      "Retro Graphics",
      "Halloween Merch",
      "Trick Or Treat Tee",
      "Jack O Lantern Tee"
    ],
    "views": 263,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557804820,
    "title": "Hello Friend Sesame Street Inspired Vintage T-Shirt, Retro 90s Cartoon Tee, Y2K Back to School Teacher Gift, Special Education School",
    "search_keyword": "special education teacher shirt",
    "age_days": 13,
    "num_favorers": 10,
    "momentum_score": 0.71,
    "price": "27.68 USD",
    "url": "https://www.etsy.com/listing/4557804820/hello-friend-sesame-street-inspired",
    "image_url": "https://i.etsystatic.com/64317846/r/il/5c89a0/8442199720/il_570xN.8442199720_5vlk.jpg",
    "tags": [
      "Animated TV Show",
      "Crewneck Clothing",
      "sesame street party",
      "TV cartoons",
      "sesame street faces",
      "Nick Jr",
      "sesame street shirt",
      "oscar the grouch",
      "TV Series Shirt",
      "elmo shirt",
      "Cookie Monster",
      "Saturday cartoons",
      "teacher shirt"
    ],
    "views": 125,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550788315,
    "title": "Personalized Floral Baby Blanket, Embroidered Name Ruffle Quilt, Newborn Gift",
    "search_keyword": "personalized baby name blanket",
    "age_days": 25,
    "num_favorers": 18,
    "momentum_score": 0.69,
    "price": "75.00 USD",
    "url": "https://www.etsy.com/listing/4550788315/personalized-floral-baby-blanket",
    "image_url": "https://i.etsystatic.com/65960263/r/il/1c33a9/8372640172/il_570xN.8372640172_f1sq.jpg",
    "tags": [
      "personalized blanket",
      "baby name blanket",
      "embroidered blanket",
      "muslin baby blanket",
      "ruffle baby blanket",
      "custom baby blanket",
      "newborn baby gift",
      "soft muslin blanket",
      "stroller blanket",
      "nursery blanket",
      "baby keepsake gift",
      "tummy time blanket",
      "Baby Summer Blanket"
    ],
    "views": 346,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553046812,
    "title": "Embroidered Heated Rivalry Hockey Quarter Zip Sweatshirt, Team Hollanov Canada, Rozanov Montreal Metros",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 21,
    "num_favorers": 15,
    "momentum_score": 0.68,
    "price": "22.99 USD",
    "url": "https://www.etsy.com/listing/4553046812/embroidered-heated-rivalry-hockey",
    "image_url": "https://i.etsystatic.com/60675446/r/il/8517d4/8361933872/il_570xN.8361933872_du57.jpg",
    "tags": [
      "team hunter",
      "hockey romance shirt",
      "boston raiders shirt",
      "connor storrie",
      "heatedrivalry hoodie",
      "heated rivalry shirt",
      "hollander shirt",
      "ilya rozanov shirt",
      "montreal metros",
      "new york admirals",
      "queer bookish shirt",
      "team rozanov",
      "heated rivalry"
    ],
    "views": 184,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4560806748,
    "title": "Golden Retriever Patchwork Silhouette, Dog Golden Retriever with Butterfly Crewneck, Patchwork custom name dog shirt Comfort Colors",
    "search_keyword": "golden retriever custom crewneck",
    "age_days": 8,
    "num_favorers": 6,
    "momentum_score": 0.67,
    "price": "20.99 USD",
    "url": "https://www.etsy.com/listing/4560806748/golden-retriever-patchwork-silhouette",
    "image_url": "https://i.etsystatic.com/53547948/r/il/77f6b6/8418290754/il_570xN.8418290754_8h1r.jpg",
    "tags": [
      "Golden Retriever",
      "dog Golden Retriever",
      "Golden Retriever tee",
      "Golden Retriever gif",
      "Golden Retriever mom",
      "dog Retriever",
      "Golden",
      "custom dog shirt",
      "dog mama",
      "dog name",
      "Retriever lover",
      "dog Golden",
      "dog shirt"
    ],
    "views": 41,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4548071056,
    "title": "Mirror Vinyl Decal | Personalised Wedding Welcome Sign | Custom Mirror Lettering | Choose Your Own Font & Colour",
    "search_keyword": "custom acrylic wedding sign",
    "age_days": 30,
    "num_favorers": 20,
    "momentum_score": 0.65,
    "price": "9.55 GBP",
    "url": "https://www.etsy.com/listing/4548071056/mirror-vinyl-decal-personalised-wedding",
    "image_url": "https://i.etsystatic.com/23263608/r/il/49e1a2/8374095951/il_570xN.8374095951_q5ot.jpg",
    "tags": [
      "mirror decal",
      "mirror lettering",
      "wedding mirror",
      "vinyl decal",
      "welcome sign",
      "mirror sticker",
      "acrylic sign",
      "wedding decor",
      "custom vinyl",
      "wedding decal",
      "mirror vinyl",
      "choose font",
      "wedding sign"
    ],
    "views": 876,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4559263741,
    "title": "Personalized Muslin Swaddle Blanket, Embroidered Baby Name, Cotton Gauze Newborn Wrap, Baby Shower Gift, Custom Nursery Keepsake, 47 x 47 in",
    "search_keyword": "personalized baby name blanket",
    "age_days": 11,
    "num_favorers": 7,
    "momentum_score": 0.58,
    "price": "42.38 MYR",
    "url": "https://www.etsy.com/listing/4559263741/personalized-muslin-swaddle-blanket",
    "image_url": "https://i.etsystatic.com/56297843/r/il/b07749/8454910309/il_570xN.8454910309_spk1.jpg",
    "tags": [
      "personalized swaddle",
      "muslin baby blanket",
      "embroidered name",
      "newborn wrap",
      "cotton gauze blanket",
      "baby shower gift",
      "new mom gift",
      "nursery keepsake",
      "newborn photo prop",
      "christening gift",
      "baby registry gift",
      "boho baby blanket",
      "custom name blanket"
    ],
    "views": 341,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550185333,
    "title": "Embroidered Fall Movie Inspired Canvas Tote Bag, Autumn Movie Series Bag, Where You Lead I Will Follow Tote, Autumn Festival Gift",
    "search_keyword": "custom embroidered book tote bag",
    "age_days": 26,
    "num_favorers": 15,
    "momentum_score": 0.56,
    "price": "49.99 USD",
    "url": "https://www.etsy.com/listing/4550185333/embroidered-fall-movie-inspired-canvas",
    "image_url": "https://i.etsystatic.com/51241639/r/il/3ab870/8341370670/il_570xN.8341370670_swmx.jpg",
    "tags": [
      "custom tote bag",
      "movie fan merch",
      "movie canvas tote",
      "stars hollow tote",
      "gilmore girls fall",
      "fall movie series",
      "book lover gift",
      "gift for her",
      "christmas gift",
      "embroidered bag",
      "canvas tote bag",
      "fall coffee bag",
      "fall festival gift"
    ],
    "views": 89,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553148369,
    "title": "Personalized Silly Goose Story Book for Kids, Custom Name Meadow Storybook for Boy or Girl, Playful Bedtime Adventure, Toddler Keepsake Gift",
    "search_keyword": "personalized first birthday story book",
    "age_days": 21,
    "num_favorers": 12,
    "momentum_score": 0.55,
    "price": "22.98 USD",
    "url": "https://www.etsy.com/listing/4553148369/personalized-silly-goose-story-book-for",
    "image_url": "https://i.etsystatic.com/67330751/r/il/c38c80/8410745121/il_570xN.8410745121_1jma.jpg",
    "tags": [
      "personalized book",
      "custom baby book",
      "silly goose book",
      "goose storybook",
      "custom name book",
      "meadow story book",
      "baby shower book",
      "bedtime story kids",
      "toddler keepsake",
      "first birthday gift",
      "kids keepsake book",
      "new mom gift book",
      "playful animal book"
    ],
    "views": 151,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553903149,
    "title": "Custom Pet Portrait Embroidered Sweatshirt Dog Mom Shirt Cat Hoodie Quarterzip Baby Tee Custom Dog Dad Gift Pet Lover",
    "search_keyword": "embroidered dog mom hoodie",
    "age_days": 20,
    "num_favorers": 11,
    "momentum_score": 0.52,
    "price": "22.00 EUR",
    "url": "https://www.etsy.com/listing/4553903149/custom-pet-portrait-embroidered",
    "image_url": "https://i.etsystatic.com/64994169/r/il/659ab1/8416215175/il_570xN.8416215175_somc.jpg",
    "tags": [
      "custom pet portrait",
      "dog mom sweatshirt",
      "custom dog shirt",
      "cat portrait shirt",
      "custom pet hoodie",
      "pet portrait hoodie",
      "dog dad gift",
      "cat mom sweater",
      "pet memorial gift",
      "custom baby tee",
      "dog lover gift",
      "dog portrait shirt",
      "pet quarterzip"
    ],
    "views": 141,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555660313,
    "title": "Custom Name Kids Tote Bag, Personalized Library Bag For Kids, Toddler School Tote Bag, Embroidered Book Bag With Name, Back to School Gifts",
    "search_keyword": "personalized kids book",
    "age_days": 17,
    "num_favorers": 9,
    "momentum_score": 0.5,
    "price": "12.88 USD",
    "url": "https://www.etsy.com/listing/4555660313/custom-name-kids-tote-bag-personalized",
    "image_url": "https://i.etsystatic.com/65503258/r/il/d14a8e/8380807548/il_570xN.8380807548_8le1.jpg",
    "tags": [
      "Kids Tote Bag",
      "Library Bag",
      "Kids Book Bag",
      "Baby Handbag",
      "Toddler Bag",
      "Kids Travel Bag",
      "Back to School Gifts",
      "Kids Birthday Gift",
      "Baby Boy Girl Gift",
      "Gift For kids",
      "Personalized Bag",
      "Custom Name Bag",
      "Baby Name Bag"
    ],
    "views": 325,
    "is_personalizable": true,
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558950480,
    "title": "Custom Pet Portrait from Photo Funny Personalized Pet Art Whimsical Dog Cat Painting Unique Pet Lover Gift Framed Pet Portrait",
    "search_keyword": "personalized dog canvas",
    "age_days": 11,
    "num_favorers": 6,
    "momentum_score": 0.5,
    "price": "16.99 USD",
    "url": "https://www.etsy.com/listing/4558950480/custom-pet-portrait-from-photo-funny",
    "image_url": "https://i.etsystatic.com/53325518/r/il/942d9a/8452430765/il_570xN.8452430765_huii.jpg",
    "tags": [
      "custom pet portrait",
      "mini pet portrait",
      "mini framed art",
      "custom pet art",
      "dog from photo",
      "pet custom photo",
      "custom pet gift",
      "pet family portrait",
      "painting commission",
      "custom dog painting",
      "pet art commission",
      "custom cat painting",
      "hand painted pet"
    ],
    "views": 43,
    "is_personalizable": true,
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4556666650,
    "title": "Embroidered Mama Sweatshirt, Mom Sweater, Personalized Mom Crewneck, Gift for Mom from Kids, New Mom Sweatshirt, Nana",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 15,
    "num_favorers": 8,
    "momentum_score": 0.5,
    "price": "40.00 USD",
    "url": "https://www.etsy.com/listing/4556666650/embroidered-mama-sweatshirt-mom-sweater",
    "image_url": "https://i.etsystatic.com/12212700/r/il/cb4339/8436147575/il_570xN.8436147575_rfgi.jpg",
    "tags": [
      "Mama sweatshirt",
      "Gift for Mom",
      "Floral embroidery",
      "Mama Crewneck",
      "Mom Sweatshirt",
      "Gift for new mom",
      "Personalized Mama",
      "Embroidered Mom Gift",
      "Custom Nana sweater",
      "Custom Mom Sweater",
      "Kids name on sleeve",
      "Embroidered Pullover",
      "Mama Comfy sweater"
    ],
    "views": 137,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4554401403,
    "title": "Personalized 1st Birthday Book for Girl, Custom Name Baby Storybook, First Birthday Gift, Baby Girl Keepsake, One Year Old Gift",
    "search_keyword": "personalized first birthday story book",
    "age_days": 19,
    "num_favorers": 10,
    "momentum_score": 0.5,
    "price": "14.26 EUR",
    "url": "https://www.etsy.com/listing/4554401403/personalized-1st-birthday-book-for-girl",
    "image_url": "https://i.etsystatic.com/67265421/r/il/b97083/8449237241/il_570xN.8449237241_gngx.jpg",
    "tags": [
      "1st birthday girl",
      "personalized book",
      "baby girl gift",
      "first birthday gift",
      "custom name book",
      "baby keepsake",
      "one year old gift",
      "baby story book",
      "birthday keepsake",
      "girl birthday book",
      "first year book",
      "custom baby gift",
      "gift for baby girl"
    ],
    "views": 603,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4560503098,
    "title": "Custom Embroidered Name Gingham Ruffle Makeup Bag, Personalized Cosmetic Pouch, Bridal Party Favor, Travel Toiletry Gift for Her",
    "search_keyword": "personalized bridal party tote bag",
    "age_days": 9,
    "num_favorers": 5,
    "momentum_score": 0.5,
    "price": "1.80 EUR",
    "url": "https://www.etsy.com/listing/4560503098/custom-embroidered-name-gingham-ruffle",
    "image_url": "https://i.etsystatic.com/65934541/r/il/e660df/8416017250/il_570xN.8416017250_kfff.jpg",
    "tags": [
      "gingham makeup bag",
      "ruffle makeup bag",
      "personalized pouch",
      "custom makeup bag",
      "embroidered pouch",
      "name cosmetic bag",
      "bridesmaid favor",
      "bridal party gift",
      "travel toiletry bag",
      "cute makeup pouch",
      "gift for her",
      "personalized gift",
      "cosmetic storage"
    ],
    "views": 129,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4547925792,
    "title": "Personalized Floral Name Night Light, Custom Letter LED Lamp, Baby Nursery Decor, Newborn Keepsake Gift, Custom Flower Night Light for Kids",
    "search_keyword": "custom night light kids name",
    "age_days": 30,
    "num_favorers": 15,
    "momentum_score": 0.48,
    "price": "2798.43 PHP",
    "url": "https://www.etsy.com/listing/4547925792/personalized-floral-name-night-light",
    "image_url": "https://i.etsystatic.com/53410189/r/il/0d86d3/8372906519/il_570xN.8372906519_maum.jpg",
    "tags": [
      "Custom Name Light",
      "Floral Name Light",
      "Baby Girl Keepsake",
      "Baby Night Light",
      "Custom Night Light",
      "Flower Night Light",
      "Gifts for Kids",
      "Toddler Room Glow",
      "New Baby Milestone",
      "Unique Teenager Gift",
      "Nursery Decoration",
      "1st Birthday Gift",
      "Monogram Nightlight"
    ],
    "views": 215,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4551482874,
    "title": "Monogram Custom Tote Bag, Daily Commute Gift, Work Bag, Farmers Market Daily Carry Bag",
    "search_keyword": "custom embroidered book tote bag",
    "age_days": 24,
    "num_favorers": 12,
    "momentum_score": 0.48,
    "price": "28.90 USD",
    "url": "https://www.etsy.com/listing/4551482874/monogram-custom-tote-bag-daily-commute",
    "image_url": "https://i.etsystatic.com/58347731/r/il/9f1efa/8350605380/il_570xN.8350605380_c1nz.jpg",
    "tags": [
      "custom tote bag",
      "embroidered tote bag",
      "farmers market bag",
      "monogram tote bag",
      "work bag",
      "travel accessories",
      "cute tote bag",
      "weekender bag",
      "tote bags for women",
      "book tote bag",
      "teacher gifts",
      "bridesmaid gifts",
      "wedding party favors"
    ],
    "views": 339,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4554997293,
    "title": "Personalized Embroidered Floral Nurse Sweatshirt, Custom Embroidered Registered Nurse Crewneck,  Floral Nursing Gift, Gift For Nurse",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 18,
    "num_favorers": 9,
    "momentum_score": 0.47,
    "price": "9.95 USD",
    "url": "https://www.etsy.com/listing/4554997293/personalized-embroidered-floral-nurse",
    "image_url": "https://i.etsystatic.com/66088139/r/il/6e08bb/8376010404/il_570xN.8376010404_jsct.jpg",
    "tags": [
      "gift for her",
      "nurse sweatshirt",
      "christmas gift",
      "registered nurse",
      "nurse gift",
      "embossed sweater",
      "black on black",
      "birthday gift",
      "sweatshirt",
      "embroidered crewneck",
      "nurse graduation",
      "Nursing Hoodie",
      "sister gift"
    ],
    "views": 71,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557046284,
    "title": "Vintage Halloween Sweatshirt UNSX No Diggity Shirt 90s Nostalgia Halloween Crewneck Retro Trick or Treat Kids Whimsigoth Cute Spooky Sweater",
    "search_keyword": "cute retro halloween crewneck",
    "age_days": 14,
    "num_favorers": 7,
    "momentum_score": 0.47,
    "price": "64.00 CAD",
    "url": "https://www.etsy.com/listing/4557046284/lets-go-ghouls-sweatshirt-vintage",
    "image_url": "https://i.etsystatic.com/51428973/r/il/fe9f9f/8391069444/il_570xN.8391069444_cv96.jpg",
    "tags": [
      "Halloween Crewneck",
      "Vintage Halloween",
      "Halloween Sweatshirt",
      "No Diggity Shirt",
      "90s Retro Fall Top",
      "Nostalgia Halloween",
      "Trick or Treat Kids",
      "Whimsigoth Jumper",
      "Cute Spooky Sweater",
      "Old School Halloween",
      "Halloween Hoodie",
      "Tick or Treaters",
      "Trendy Grunge Horror"
    ],
    "views": 49,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550386968,
    "title": "Put A Smile On Sweatshirt, Pumpkin Head Girl Halloween Sweatshirt, Vintage Halloween Crewneck, Cute Retro Pumpkin Shirt, Spooky Fall Hoodie",
    "search_keyword": "cute retro halloween crewneck",
    "age_days": 26,
    "num_favorers": 12,
    "momentum_score": 0.44,
    "price": "33.99 USD",
    "url": "https://www.etsy.com/listing/4550386968/put-a-smile-on-sweatshirt-pumpkin-head",
    "image_url": "https://i.etsystatic.com/51584462/r/il/0a9d73/8390656719/il_570xN.8390656719_e9fo.jpg",
    "tags": [
      "horror aesthetic",
      "Halloween sweatshirt",
      "spooky hoodie",
      "gothic fashion",
      "fall sweatshirt",
      "Pumpkin Sweatshirt",
      "halloween crewneck",
      "vintage halloween",
      "spooky pumpkin shirt",
      "halloween gift",
      "retro halloween",
      "pumpkin girl shirt",
      "pumpkin head"
    ],
    "views": 177,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555825768,
    "title": "Embroidered Dental Sweatshirt, Dental Assistant Sweatshirt, Teeth Sweatshirt, Hygienist Sweatshirt, Gift for Dentist, Dental Assistant Gift",
    "search_keyword": "dental hygienist sweatshirt",
    "age_days": 17,
    "num_favorers": 7,
    "momentum_score": 0.39,
    "price": "24.99 USD",
    "url": "https://www.etsy.com/listing/4555825768/embroidered-dental-sweatshirt-dental",
    "image_url": "https://i.etsystatic.com/60433336/r/il/1f1dc6/8429905439/il_570xN.8429905439_1lpr.jpg",
    "tags": [
      "emboidered crewneck",
      "orthodontics shirt",
      "dental hygiene gifts",
      "dentist office shirt",
      "dentist student",
      "future dentist",
      "dental assistant",
      "dentist shirt",
      "dentist tee",
      "hygienist shirts",
      "dentist gift",
      "floral dental shirt",
      "gift for dentist"
    ],
    "views": 98,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549633842,
    "title": "Bespoke Snoopy Sweet Cookies Blanket, Custom Peanuts Striped Floral Warm Quilt for Baby Toddler Nap Time Sofa Accessories",
    "search_keyword": "custom floral baby blanket",
    "age_days": 27,
    "num_favorers": 11,
    "momentum_score": 0.39,
    "price": "29.88 USD",
    "url": "https://www.etsy.com/listing/4549633842/bespoke-snoopy-sweet-cookies-blanket",
    "image_url": "https://i.etsystatic.com/66965553/r/il/9361ff/8337446796/il_570xN.8337446796_swwv.jpg",
    "tags": [
      "Sweet cookie pattern",
      "Blue flower print",
      "Striped fleece throw",
      "Cute puppy blanket",
      "Soft baby quilt",
      "Custom girl gift",
      "Floral cartoon wrap",
      "Pastel dog art",
      "Cozy nap companion",
      "Bow tie decor",
      "Relaxed pet throw",
      "Custom Snoopy cover",
      "Soft nursery wrap"
    ],
    "views": 142,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4558581669,
    "title": "Custom Embroidered Pet Portrait Sweatshirt, Personalized Two Dog Photo Heart Gingham Crewneck, Custom Dog Paw Print Gift, Dog Mom Sweater",
    "search_keyword": "golden retriever custom crewneck",
    "age_days": 12,
    "num_favorers": 5,
    "momentum_score": 0.38,
    "price": "15.95 USD",
    "url": "https://www.etsy.com/listing/4558581669/custom-embroidered-pet-portrait",
    "image_url": "https://i.etsystatic.com/61791984/r/il/dc8ec8/8450047433/il_570xN.8450047433_kk6w.jpg",
    "tags": [
      "custom pet portrait",
      "custom dog sweater",
      "two dog sweatshirt",
      "dog mom sweatshirt",
      "pet lover crewneck",
      "dog photo sweatshirt",
      "paw print sleeve",
      "golden retriever",
      "bernese mountain dog",
      "embroidered dog",
      "personalized pet",
      "custom dog name",
      "pet embroidered"
    ],
    "views": 62,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553941585,
    "title": "Custom Engraved Mug Personalized Stoneware Coffee Cup Christmas Gift for Coworker Teacher Nurse Two Tone Speckled Custom Text Name Mug",
    "search_keyword": "personalized teacher appreciation mug",
    "age_days": 20,
    "num_favorers": 8,
    "momentum_score": 0.38,
    "price": "22.49 CAD",
    "url": "https://www.etsy.com/listing/4553941585/custom-engraved-mug-personalized",
    "image_url": "https://i.etsystatic.com/64353066/r/il/2797b6/8368619040/il_570xN.8368619040_ghkl.jpg",
    "tags": [
      "custom engraved mug",
      "personalized cup",
      "custom text mug",
      "personalized gift",
      "custom name mug",
      "rustic stoneware",
      "aesthetic coffee cup",
      "coworker gift",
      "boss appreciation",
      "holiday gifting",
      "name coffee mug",
      "customized ceramic",
      "christmas gift"
    ],
    "views": 210,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549427405,
    "title": "Therapist Embroidered Sweatshirt, Floral Mental Health Gift, Emotional Support Human Tee",
    "search_keyword": "speech therapy sweatshirt",
    "age_days": 27,
    "num_favorers": 10,
    "momentum_score": 0.36,
    "price": "23.12 USD",
    "url": "https://www.etsy.com/listing/4549427405/therapist-embroidered-sweatshirt-floral",
    "image_url": "https://i.etsystatic.com/53633168/r/il/1a045f/8335970920/il_570xN.8335970920_ev61.jpg",
    "tags": [
      "choose kindness",
      "mental health tee",
      "occupational shirt",
      "physical therapy",
      "retro therapist",
      "slp grad gift",
      "social psychology",
      "social worker shirt",
      "speech therapy",
      "therapist tshirt",
      "therapy is cool",
      "therapist sweatshirt",
      "embroidered"
    ],
    "views": 21,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553302144,
    "title": "Embroidered Halloween Crew Sweatshirt, Pumpkin Ghost Crewneck, Cat Skeleton Sweatshirt, Spooky Season Crewneck, Halloween Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 21,
    "num_favorers": 8,
    "momentum_score": 0.36,
    "price": "22.00 USD",
    "url": "https://www.etsy.com/listing/4553302144/embroidered-halloween-crew-sweatshirt",
    "image_url": "https://i.etsystatic.com/52539890/r/il/7e9bf5/8411803611/il_570xN.8411803611_i795.jpg",
    "tags": [
      "embroidered shirt",
      "Crewneck embroidery",
      "Fall Pumpkin Shirt",
      "halloween sweatshirt",
      "pumpkin crewneck",
      "halloween pumpkin",
      "Spooky Season shirt",
      "halloween bat shirt",
      "pumpkin quarter zip",
      "spooky quarter zip",
      "Halloween Dachshunds",
      "halloween crew shirt",
      "skeleton shirt"
    ],
    "views": 32,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4548799968,
    "title": "Embroidered Dog Sweatshirt, Golden Retriever and Ghost, Minimalist Halloween Dog Sweater, Spooky Season Pet, Golden Mom Gift",
    "search_keyword": "embroidered dog mom hoodie",
    "age_days": 28,
    "num_favorers": 10,
    "momentum_score": 0.34,
    "price": "49.98 USD",
    "url": "https://www.etsy.com/listing/4548799968/embroidered-dog-sweatshirt-golden",
    "image_url": "https://i.etsystatic.com/45243891/r/il/ed9bf8/8379210885/il_570xN.8379210885_meq5.jpg",
    "tags": [
      "dog sweater",
      "embroidery sweater",
      "embroidered pet",
      "embroidered dog",
      "fall dog sweatshirt",
      "dog ghost sweatshirt",
      "new dog owner gift",
      "gifts for dog owners",
      "dog halloween",
      "dog hoodie",
      "dog lover sweatshirt",
      "golden retriever",
      "golden mom shirt"
    ],
    "views": 64,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4557202262,
    "title": "Custom Embroidered Labrador Retriever Sweatshirt, Dog Lover Crewneck, Black Lab Mama Shirt",
    "search_keyword": "embroidered dog mom hoodie",
    "age_days": 14,
    "num_favorers": 5,
    "momentum_score": 0.33,
    "price": "22.00 USD",
    "url": "https://www.etsy.com/listing/4557202262/custom-embroidered-labrador-retriever",
    "image_url": "https://i.etsystatic.com/61740956/r/il/306e6f/8440101417/il_570xN.8440101417_awqz.jpg",
    "tags": [
      "Black Lab Mama",
      "Labrador Retriever",
      "Labrador Gift",
      "Dog Embroidery",
      "Custom Dog Shirt",
      "Black Lab Dad",
      "Dog Lover Gift",
      "Embroidered Hoodie",
      "Pet Memorial Gift",
      "Minimalist Dog Art",
      "Retro Dog Sweater",
      "Lab Mom Crewneck",
      "Embroidered Sweater"
    ],
    "views": 95,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555703670,
    "title": "Custom Pet Mug with 3D Dog Cat Figurines, Personalized Name Ceramic Cup",
    "search_keyword": "custom pet portrait mug",
    "age_days": 17,
    "num_favorers": 6,
    "momentum_score": 0.33,
    "price": "564.55 HKD",
    "url": "https://www.etsy.com/listing/4555703670/custom-pet-mug-with-3d-dog-cat-figurines",
    "image_url": "https://i.etsystatic.com/67299561/r/il/43ee67/8381120684/il_570xN.8381120684_4a4a.jpg",
    "tags": [
      "custom pet mug",
      "personalized pet mug",
      "3d pet mug",
      "pet figurine mug",
      "peekaboo pet mug",
      "custom dog mug",
      "custom cat mug",
      "custom bunny mug",
      "pet portrait mug",
      "ceramic pet mug",
      "pet name mug",
      "pet lover gift",
      "pet memorial gift"
    ],
    "views": 136,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4552090501,
    "title": "Personalized Embroidered Psychologist Quarter Zip Sweatshirt, Custom Psychology Sweater, Therapist Gift, Graduation Gift",
    "search_keyword": "dental hygienist sweatshirt",
    "age_days": 23,
    "num_favorers": 7,
    "momentum_score": 0.29,
    "price": "28.95 USD",
    "url": "https://www.etsy.com/listing/4552090501/personalized-embroidered-psychologist",
    "image_url": "https://i.etsystatic.com/66088139/r/il/39e2b0/8355114450/il_570xN.8355114450_3cjp.jpg",
    "tags": [
      "dentist custom shirt",
      "Custom Dental Gift",
      "dental tooth sweater",
      "Dental Hygienist",
      "Dental Student Gift",
      "Dental Assistant",
      "Gift For Dentist",
      "dental student tee",
      "Dental Shirt",
      "Dentist Gifts",
      "tooth shirt",
      "Dentist Sweatshirt",
      "Teeth Sweatshirt"
    ],
    "views": 23,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4556202764,
    "title": "Personalized Sofia The First Castle Blanket, Custom Name Princess Throw",
    "search_keyword": "personalized baby name blanket",
    "age_days": 16,
    "num_favorers": 5,
    "momentum_score": 0.29,
    "price": "29.98 USD",
    "url": "https://www.etsy.com/listing/4556202764/personalized-sofia-the-first-blanket",
    "image_url": "https://i.etsystatic.com/66774531/r/il/92cf43/8432693331/il_570xN.8432693331_ti1t.jpg",
    "tags": [
      "custom name throw",
      "sofia the first gift",
      "fairy tale blanket",
      "girls birthday gift",
      "baby shower present",
      "plush soft throw",
      "princess fan gift",
      "custom kids blanket",
      "toddler girl bedding",
      "castle decor",
      "child room blanket",
      "sofia blanket",
      "princess blanket"
    ],
    "views": 180,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555672061,
    "title": "Embroidered Halloween Radiology Sweatshirt: Spooky Ghost Rad Tech Apparel Crewneck",
    "search_keyword": "radiology tech sweatshirt",
    "age_days": 17,
    "num_favorers": 5,
    "momentum_score": 0.28,
    "price": "32.24 CAD",
    "url": "https://www.etsy.com/listing/4555672061/embroidered-halloween-radiology",
    "image_url": "https://i.etsystatic.com/58324149/r/il/d587e3/8428824947/il_570xN.8428824947_27el.jpg",
    "tags": [
      "rad tech student",
      "Cute Radiology",
      "cute radiology gifts",
      "rad tech sweatshirt",
      "radiologist shirt",
      "radiology grad gift",
      "radiology sweater",
      "xray technician",
      "ct tech mri tech",
      "xray tech sweatshirt",
      "mri sweatshirt",
      "rad tech week gift",
      "radiology skeleton"
    ],
    "views": 45,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4548207827,
    "title": "We All Thrive Under Different Conditions Shirt, Neurodiversity Tee, Autism Acceptance, Special Education Teacher Gift, Comfort Colors",
    "search_keyword": "special education teacher shirt",
    "age_days": 29,
    "num_favorers": 8,
    "momentum_score": 0.27,
    "price": "19.99 USD",
    "url": "https://www.etsy.com/listing/4548207827/we-all-thrive-under-different-conditions",
    "image_url": "https://i.etsystatic.com/61147027/r/il/31cfb1/8327237168/il_570xN.8327237168_dc2h.jpg",
    "tags": [
      "autism awareness",
      "special education",
      "autism mom shirt",
      "bcba gift",
      "neurodiversity shirt",
      "autism acceptance",
      "autism shirt",
      "bcba shirt",
      "autism teacher",
      "autism mom",
      "autism gift",
      "sped shirt",
      "gift for autism mom"
    ],
    "views": 69,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550804676,
    "title": "Custom Human and Pet Family Portrait from Photo, Funny Royal Dog or Cat Owner Painting, Personalized Couple and Pet Wall Art.",
    "search_keyword": "custom pet portrait canvas funny",
    "age_days": 25,
    "num_favorers": 7,
    "momentum_score": 0.27,
    "price": "30.00 USD",
    "url": "https://www.etsy.com/listing/4550804676/custom-human-and-pet-family-portrait",
    "image_url": "https://i.etsystatic.com/66460584/r/il/edd066/8379413407/il_570xN.8379413407_2zyt.jpg",
    "tags": [
      "human pet family",
      "family pet portrait",
      "mom dad pet portrait",
      "royal pet art",
      "dog mom custom art",
      "royal pet family",
      "owner pet painting",
      "family photo pet art",
      "husband wife pet art",
      "multi pet family art",
      "funny pet painting",
      "funny regal artwork",
      "housewarming decor"
    ],
    "views": 241,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555147180,
    "title": "Custom Embossed Puff Sweatshirt, Personalized Team Name Shirt, School Mascot T-Shirt, 3d Lettering Custom Sweatshirt",
    "search_keyword": "puff print custom sweatshirt",
    "age_days": 18,
    "num_favorers": 5,
    "momentum_score": 0.26,
    "price": "15.86 USD",
    "url": "https://www.etsy.com/listing/4555147180/custom-embossed-puff-sweatshirt",
    "image_url": "https://i.etsystatic.com/42620423/r/il/22d01f/8381844014/il_570xN.8381844014_hx2k.jpg",
    "tags": [
      "custom puff shirt",
      "navy team shirt",
      "puff print shirt",
      "coach gift",
      "team name shirt",
      "game day outfit",
      "spirit wear top",
      "high school shirt",
      "football shirt",
      "college sports",
      "embroidered sweater",
      "hockey basketball",
      "school sweater"
    ],
    "views": 185,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4555106602,
    "title": "Personalised Music Photo Acrylic Plaque, Custom Song Picture Frame, Scannable Song Code Couple Gift (USB Powered)",
    "search_keyword": "custom acrylic wedding sign",
    "age_days": 18,
    "num_favorers": 5,
    "momentum_score": 0.26,
    "price": "16.99 GBP",
    "url": "https://www.etsy.com/listing/4555106602/personalised-music-photo-acrylic-plaque",
    "image_url": "https://i.etsystatic.com/39522232/r/il/8ff8e6/8424586281/il_570xN.8424586281_i9vs.jpg",
    "tags": [
      "music photo plaque",
      "spotify plaque",
      "song code plaque",
      "music frame gift",
      "couple photo gift",
      "personalised song",
      "anniversary gift",
      "wedding song gift",
      "custom photo gift",
      "music lover gift",
      "valentines gift",
      "acrylic photo gift",
      "our song plaque"
    ],
    "views": 225,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549706137,
    "title": "Personalized Baby Photo Album, Hand Embroidered Linen Memory Book, Custom Name Newborn Keepsake, Baby Shower Gift for Boy or Girl",
    "search_keyword": "personalized kids book",
    "age_days": 27,
    "num_favorers": 7,
    "momentum_score": 0.25,
    "price": "36.00 GBP",
    "url": "https://www.etsy.com/listing/4549706137/personalized-baby-photo-album-hand",
    "image_url": "https://i.etsystatic.com/66821734/r/il/5965ed/8338031420/il_570xN.8338031420_8gq8.jpg",
    "tags": [
      "personalized album",
      "baby photo album",
      "embroidered album",
      "baby memory book",
      "newborn keepsake",
      "baby shower gift",
      "custom baby gift",
      "linen photo album",
      "hand embroidered",
      "baby girl gift",
      "baby boy gift",
      "first year album",
      "new mom gift"
    ],
    "views": 337,
    "is_personalizable": true
  },
  {
    "listing_id": 4549374484,
    "title": "Regulation Before Expectation Shirt, Comfort Colors® Special Education Shirt, SPED Teacher Gift, RBT Shirt, Occupational Therapy Shirt",
    "search_keyword": "special education teacher shirt",
    "age_days": 27,
    "num_favorers": 7,
    "momentum_score": 0.25,
    "price": "18.95 USD",
    "url": "https://www.etsy.com/listing/4549374484/regulation-before-expectation-shirt",
    "image_url": "https://i.etsystatic.com/5326218/r/il/893451/8417334974/il_570xN.8417334974_5ay6.jpg",
    "tags": [
      "Funny Shirt",
      "SPED Teacher Gift",
      "RBT Shirt",
      "Regulation Before",
      "Expectation Shirt",
      "Special Education",
      "Occupational Therapy",
      "Speech Therapy",
      "Funny Teacher Tshirt",
      "Sped Behavior Shirts",
      "Learning Support",
      "OT shirt",
      "Teacher team shirts"
    ],
    "views": 93,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4553717378,
    "title": "Embroidered Dachshund Sweatshirt, Autumn Dog Crewneck, Fall Tree Embroidery Shirt, Cute Wiener Dog Pullover, Cozy Dog Lover Gift",
    "search_keyword": "dachshund embroidered sweatshirt",
    "age_days": 20,
    "num_favorers": 5,
    "momentum_score": 0.24,
    "price": "15.99 USD",
    "url": "https://www.etsy.com/listing/4553717378/embroidered-dachshund-sweatshirt-autumn",
    "image_url": "https://i.etsystatic.com/52683420/r/il/7e6d3a/8366893460/il_570xN.8366893460_6jle.jpg",
    "tags": [
      "embroidered clothing",
      "embroidered crewneck",
      "halloween sweatshirt",
      "spooky gifts",
      "Spooky Season shirt",
      "halloween Gift",
      "ghost lover gift",
      "halloween ghost",
      "halloween dog",
      "dog lover gift",
      "spooky dog shirt",
      "cute dog sweatshirt",
      "dog mom halloween"
    ],
    "views": 75,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4550230425,
    "title": "Custom Wedding Guest Book Canvas Banner, Embroidered Wedding Pennant Flag, Keepsake Wedding Sign, Last Name Reception Sign, Guest Book Sign",
    "search_keyword": "personalized kids book",
    "age_days": 26,
    "num_favorers": 5,
    "momentum_score": 0.19,
    "price": "9.99 USD",
    "url": "https://www.etsy.com/listing/4550230425/custom-wedding-guest-book-canvas-banner",
    "image_url": "https://i.etsystatic.com/65399410/r/il/a46383/8389542923/il_570xN.8389542923_l4t1.jpg",
    "tags": [
      "wedding guest sign",
      "wedding table decor",
      "engagement gift",
      "personalized wedding",
      "custom wedding sign",
      "embroidered banner",
      "wedding keepsake",
      "family name sign",
      "bridal shower gift",
      "wedding flag",
      "fabric wedding sign",
      "wedding banner"
    ],
    "views": 117,
    "is_personalizable": true
  },
  {
    "listing_id": 4547864778,
    "title": "Custom Embroidered Gymnastics Mom Sweatshirt, Personalized Gymnast Mom Sleeve Name Shirt, Gymnastics Mama Gift, Gymnastic Crewneck",
    "search_keyword": "custom embroidered sweatshirt",
    "age_days": 30,
    "num_favorers": 6,
    "momentum_score": 0.19,
    "price": "24.95 USD",
    "url": "https://www.etsy.com/listing/4547864778/custom-embroidered-gymnastics-mom",
    "image_url": "https://i.etsystatic.com/66088139/r/il/5bbe02/8372383613/il_570xN.8372383613_c47v.jpg",
    "tags": [
      "gymnastics mom",
      "gym mom sweatshirt",
      "gymnastic mom shirt",
      "custom gym mom",
      "gym mom gift",
      "embroidered gym mom",
      "gymnastics sweater",
      "gym mama sweatshirt",
      "gym mom crewneck",
      "gymnast mom shirt",
      "custom gymnast gift",
      "gym mom hoodie",
      "personalized gym"
    ],
    "views": 74,
    "is_personalizable": true
  },
  {
    "listing_id": 4550095056,
    "title": "Embroidered Sweatshirt, &quot;I&#39;m Cold But Brave&quot; Funny Quote, Cozy Cotton Blend Top",
    "search_keyword": "bookish embroidered sweatshirt",
    "age_days": 26,
    "num_favorers": 5,
    "momentum_score": 0.19,
    "price": "24.00 USD",
    "url": "https://www.etsy.com/listing/4550095056/embroidered-sweatshirt-im-cold-but-brave",
    "image_url": "https://i.etsystatic.com/50699871/r/il/38e051/8340576840/il_570xN.8340576840_kx8u.jpg",
    "tags": [
      "but I'm being brave",
      "gift for friend",
      "gift for her",
      "my tummy hurts",
      "I'm a delight",
      "bookish shirt",
      "gift for girlfriend",
      "funny gift",
      "funny",
      "I'm cold shirt",
      "I'm cold tshirt",
      "funny shirt",
      "funny tshirt"
    ],
    "views": 80,
    "is_personalizable": false,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  },
  {
    "listing_id": 4549909628,
    "title": "Personalized Acrylic QR Code Sign, Scan To Pay Counter Display, Google Review Plaque, Social Media Business Decor",
    "search_keyword": "personalized business desk plaque",
    "age_days": 27,
    "num_favorers": 5,
    "momentum_score": 0.18,
    "price": "15.99 USD",
    "url": "https://www.etsy.com/listing/4549909628/personalized-acrylic-qr-code-sign-scan",
    "image_url": "https://i.etsystatic.com/65775180/r/il/83536b/8387270351/il_570xN.8387270351_p12o.jpg",
    "tags": [
      "venmo checkout",
      "cash app marker",
      "instagram link",
      "facebook profile",
      "wifi access",
      "salon desk",
      "restaurant stand",
      "airbnb welcome",
      "small shop gift",
      "digital menu",
      "website scanner",
      "custom quote",
      "frosted block"
    ],
    "views": 41,
    "is_personalizable": true,
    "first_discovered": "2026-08-31",
    "last_updated": "2026-08-31"
  }
]
```

# README.md

```md
# Etsy Listing Research Tool

A personal research tool for analyzing publicly available Etsy listing data. Given a search term, it finds recently listed items that are already showing early sales traction, so I can spot products worth researching further before deciding what to make or sell.

## What it does

- Searches Etsy's public listings for a given search term (via the official [Etsy Open API v3](https://developers.etsy.com/documentation/)), sorted by newest first.
- For each newly listed item, checks its public review count.
- Ranks candidates by **review velocity** (`review_count / days_since_listed`) — a mathematically grounded signal, since Etsy only allows a review after a verified purchase, making review count a real, provable floor on sales rather than an estimate.
- Outputs the results as a CSV and a simple, self-contained HTML report for easy browsing.

## What it does *not* do

- Does not upload, edit, or manage any listings.
- Does not access private shop or seller account data.
- Does not send email or interact with buyers/sellers in any way.
- Does not scrape Etsy pages — all data comes from the official, public, read-only Open API endpoints.

## Why

Etsy's API doesn't expose a direct "sales count" field for listings outside your own shop. Review count is the closest real (non-guessed) proxy available publicly, since it requires a verified purchase. This tool combines that with listing age to compute a fair, comparable velocity score across listings of different ages.

## Usage

\`\`\`bash
pip install requests --break-system-packages

python etsy_trend_finder.py "your search term" \
    --api-key YOUR_ETSY_API_KEY \
    --days 30 \
    --min-reviews 1 \
    --max-pages 10
\`\`\`

This produces:
- `etsy_trend_results.csv` — raw ranked data
- `etsy_trend_report.html` — a browsable report with sortable columns and a visual velocity indicator

## Requirements

- Python 3.8+
- `requests`
- A free Etsy API key ([register here](https://www.etsy.com/developers/register)) — public read-only endpoints work with just the API key, no OAuth needed.

## Scope

This is a personal-use tool built for my own product research. It is not distributed or intended for use by others.

```

# requirements.txt

```txt
requests==2.31.0
python-dotenv==1.0.1
pandas>=2.2.3
streamlit>=1.38.0
```

# scanner.py

```py
import json
import os
import time
from datetime import datetime, timezone
from etsy_client import EtsyClient

# ==========================================
# 🎯 HIGH-CONVERTING POD MICRO-NICHES
# ==========================================
POD_SEARCH_TERMS = [
    # --- 1. Top Apparel Micro-Niches (Puff, Embroidery, Sweatshirts) ---
    "custom embroidered sweatshirt",
    "puff print custom sweatshirt",
    "retro nurse sweatshirt",
    "l&d nurse crewneck",
    "dental hygienist sweatshirt",
    "speech therapy sweatshirt",
    "radiology tech sweatshirt",
    "special education teacher shirt",
    "promoted to grandma sweatshirt",
    "grandma garden sweatshirt",
    "bachelorette party custom shirts",
    "embroidered dog mom hoodie",
    "dachshund embroidered sweatshirt",
    "golden retriever custom crewneck",
    "pickleball embroidered sweatshirt",
    "bookish embroidered sweatshirt",
    "romantasy reader shirt",

    # --- 2. Blankets & Home Decor ---
    "personalized baby name blanket",
    "custom floral baby blanket",
    "custom photo collage blanket",
    "personalized pet memorial blanket",
    "custom birth month flower blanket",
    "grandkids names blanket",
    "book lover woven blanket",

    # --- 3. Acrylic / Night Lights / Plaques ---
    "acrylic song plaque with stand",
    "custom night light kids name",
    "custom acrylic wedding sign",
    "personalized business desk plaque",
    "custom couple map acrylic plaque",

    # --- 4. Customized Books, Canvas & Wall Art ---
    "personalized first birthday story book",
    "custom bedtime story book for kids",
    "custom pet portrait canvas funny",
    "personalized family watercolor canvas",
    "custom soundwave canvas art",

    # --- 5. Drinkware & Mugs ---
    "custom pet portrait mug",
    "funny retro coworker mug",
    "personalized teacher appreciation mug",
    "custom golf mug for dad",

    # --- 6. Totes & Accessories ---
    "custom embroidered book tote bag",
    "personalized bridal party tote bag",
    "nurse utility tote bag personalized",

    # --- 7. High-Traction Seasonal / Milestones ---
    "cute retro halloween crewneck",
    "personalized baby first christmas ornament",
    "custom dog christmas ornament wood"
]

# ==========================================
# ⚙️ SCANNER CONFIGURATION & SAFETY SETTINGS
# ==========================================
MAX_LISTING_AGE_DAYS = 30     # Only look at listings created in the last 30 days
MIN_FAVORITES = 5             # Minimum favorites threshold to filter out zero-traction noise
LISTINGS_PER_KEYWORD = 100    # Depth per keyword (100 = 1 page, 200 = 2 pages)
OUTPUT_FILENAME = "pod_winners.json"


def calculate_age_days(timestamp):
    """Calculates listing age in days from a Unix timestamp."""
    if not timestamp:
        return 0
    created_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - created_date
    return max(0, delta.days)


def get_listing_image(client, listing_id):
    """Fetches the primary display image URL for a specific listing."""
    data = client.get(f"listings/{listing_id}/images")
    if data and "results" in data and len(data["results"]) > 0:
        return data["results"][0].get("url_570xN")
    return None


def load_existing_vault():
    """Loads existing listings so we never lose past discoveries."""
    if not os.path.exists(OUTPUT_FILENAME):
        return {}
    try:
        with open(OUTPUT_FILENAME, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {str(item["listing_id"]): item for item in data}
    except Exception:
        return {}


def fetch_paginated_listings(client, keyword, total_target=100):
    """Fetches listings using pagination (100 items per request)."""
    all_results = []
    page_size = min(100, total_target)
    offset = 0

    while offset < total_target:
        params = {
            "keywords": keyword,
            "limit": page_size,
            "offset": offset,
            "sort_on": "created",
            "sort_order": "desc"
        }
        
        response = client.get("listings/active", params=params)
        
        if not response or "results" not in response:
            break

        results = response["results"]
        if not results:
            break

        all_results.extend(results)
        offset += page_size

        # If Etsy returned fewer items than requested, we reached the end
        if len(results) < page_size:
            break

    return all_results


def run_scanner():
    client = EtsyClient()
    vault = load_existing_vault()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    new_discoveries = 0
    updated_items = 0
    total_listings_checked = 0

    print("======================================================")
    print(f"🏛️  Etsy POD Permanent Vault Engine")
    print(f"📦  Loaded {len(vault)} existing products from Vault")
    print(f"🎯  Scanning {len(POD_SEARCH_TERMS)} High-Converting Micro-Niches")
    print(f"📊  Target Depth: {LISTINGS_PER_KEYWORD} newest items per niche")
    print("======================================================\n")

    for idx, keyword in enumerate(POD_SEARCH_TERMS, 1):
        print(f"[{idx}/{len(POD_SEARCH_TERMS)}] 🔍 Scanning: '{keyword}'...")
        
        listings = fetch_paginated_listings(client, keyword, total_target=LISTINGS_PER_KEYWORD)
        total_listings_checked += len(listings)

        for item in listings:
            listing_id_str = str(item.get("listing_id"))

            # 1. Age verification (only items <= 30 days old)
            created_ts = item.get("original_creation_timestamp") or item.get("creation_timestamp")
            age_days = calculate_age_days(created_ts)

            if age_days > MAX_LISTING_AGE_DAYS:
                continue

            # 2. Favorites threshold
            num_favorers = item.get("num_favorers", 0)
            if num_favorers < MIN_FAVORITES:
                continue

            # 3. Momentum Score calculation
            momentum_score = round(num_favorers / (age_days + 1), 2)

            # 4. Format price properly
            price_info = item.get("price", {})
            amount = price_info.get("amount", 0)
            divisor = price_info.get("divisor", 100)
            currency = price_info.get("currency_code", "USD")
            formatted_price = f"{amount / divisor:.2f} {currency}"

            # Check if this item is already known in our Vault
            if listing_id_str in vault:
                vault[listing_id_str]["num_favorers"] = num_favorers
                vault[listing_id_str]["momentum_score"] = momentum_score
                vault[listing_id_str]["age_days"] = age_days
                vault[listing_id_str]["last_updated"] = today_str
                updated_items += 1
            else:
                # Brand new breakout discovery!
                image_url = get_listing_image(client, listing_id_str)
                
                vault[listing_id_str] = {
                    "listing_id": item.get("listing_id"),
                    "title": item.get("title"),
                    "search_keyword": keyword,
                    "age_days": age_days,
                    "num_favorers": num_favorers,
                    "momentum_score": momentum_score,
                    "price": formatted_price,
                    "url": item.get("url"),
                    "image_url": image_url,
                    "tags": item.get("tags", []),
                    "views": item.get("views", 0),
                    "is_personalizable": item.get("is_personalizable", False),
                    "first_discovered": today_str,
                    "last_updated": today_str
                }
                new_discoveries += 1
                print(f"   ✨ NEW WINNER: {item.get('title')[:40]}... (Favs: {num_favorers} | Age: {age_days}d | Score: {momentum_score})")

    # Sort entire vault by Momentum Score (descending)
    all_vault_items = list(vault.values())
    all_vault_items.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)

    # Save to JSON
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        json.dump(all_vault_items, f, indent=2, ensure_ascii=False)

    print("\n======================================================")
    print(f"✅ Scan Complete!")
    print(f"🔎 Total Recent Listings Inspected: {total_listings_checked}")
    print(f"✨ New Winners Added to Vault: {new_discoveries}")
    print(f"🔄 Existing Winners Updated: {updated_items}")
    print(f"🏛️  Total Products in Permanent Vault: {len(all_vault_items)}")
    print("======================================================")


if __name__ == "__main__":
    run_scanner()
```

# test_env.py

```py
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ETSY_API_KEY")

if api_key and api_key != "your_keystring_here":
    print("✅ Environment is configured properly! API Key loaded.")
else:
    print("❌ Error: ETSY_API_KEY not found or still set to placeholder in .env")
```


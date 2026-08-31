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

```bash
pip install requests --break-system-packages

python etsy_trend_finder.py "your search term" \
    --api-key YOUR_ETSY_API_KEY \
    --days 30 \
    --min-reviews 1 \
    --max-pages 10
```

This produces:
- `etsy_trend_results.csv` — raw ranked data
- `etsy_trend_report.html` — a browsable report with sortable columns and a visual velocity indicator

## Requirements

- Python 3.8+
- `requests`
- A free Etsy API key ([register here](https://www.etsy.com/developers/register)) — public read-only endpoints work with just the API key, no OAuth needed.

## Scope

This is a personal-use tool built for my own product research. It is not distributed or intended for use by others.

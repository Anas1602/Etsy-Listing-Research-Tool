import json
import time
from datetime import datetime, timezone
from etsy_client import EtsyClient

# --- Configuration & POD Search Terms ---
POD_SEARCH_TERMS = [
    "custom blanket",
    "personalized kids book",
    "custom embroidered sweatshirt",
    "acrylic song plaque",
    "custom photo mug",
    "retro nurse sweatshirt",
    "personalized dog canvas"
]

MAX_LISTING_AGE_DAYS = 30   # Only look at listings created in the last 30 days
MIN_FAVORITES = 5           # Minimum favorites to filter out zero-traction noise
RESULTS_PER_KEYWORD = 25    # How many recent items to inspect per keyword


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
        return data["results"][0].get("url_570xN")  # Clean medium/high-res preview
    return None


def run_scanner():
    client = EtsyClient()
    winners = []
    seen_listing_ids = set()

    print("🚀 Starting POD Winning Listings Scan...\n")

    for keyword in POD_SEARCH_TERMS:
        print(f"🔍 Scanning keyword: '{keyword}'...")
        
        # Sort by 'created' descending to get the newest listings first
        response = client.search_active_listings(
            keywords=keyword, 
            limit=RESULTS_PER_KEYWORD, 
            sort_on="created", 
            sort_order="desc"
        )
        
        if not response or "results" not in response:
            print(f"   ⚠️ No listings returned for '{keyword}'.")
            continue

        listings = response["results"]
        
        for item in listings:
            listing_id = item.get("listing_id")
            
            # Avoid duplicate listings across different keyword searches
            if listing_id in seen_listing_ids:
                continue
            seen_listing_ids.add(listing_id)

            # 1. Determine actual creation date
            created_ts = item.get("original_creation_timestamp") or item.get("creation_timestamp")
            age_days = calculate_age_days(created_ts)

            # 2. Filter: Only recent listings
            if age_days > MAX_LISTING_AGE_DAYS:
                continue

            num_favorers = item.get("num_favorers", 0)

            # 3. Filter: Minimum favorites threshold
            if num_favorers < MIN_FAVORITES:
                continue

            # 4. Calculate Momentum Score (Favorites per day)
            momentum_score = round(num_favorers / (age_days + 1), 2)

            # Format price properly (Etsy uses cents/divisors)
            price_info = item.get("price", {})
            amount = price_info.get("amount", 0)
            divisor = price_info.get("divisor", 100)
            currency = price_info.get("currency_code", "USD")
            formatted_price = f"{amount / divisor:.2f} {currency}"

            # 5. Fetch primary mockup image for this candidate
            image_url = get_listing_image(client, listing_id)

            listing_data = {
                "listing_id": listing_id,
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
                "is_personalizable": item.get("is_personalizable", False)
            }

            winners.append(listing_data)
            print(f"   🔥 Winner Found: {listing_data['title'][:40]}... (Age: {age_days}d | Favs: {num_favorers} | Score: {momentum_score})")

    # Sort all discovered winners by Momentum Score (highest first)
    winners.sort(key=lambda x: x["momentum_score"], reverse=True)

    # Save to JSON file
    output_filename = "pod_winners.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(winners, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Scan Complete! Discovered {len(winners)} high-momentum POD listings.")
    print(f"📁 Results saved to '{output_filename}'")


if __name__ == "__main__":
    run_scanner()
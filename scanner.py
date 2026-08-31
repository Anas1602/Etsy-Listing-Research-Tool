import json
import os
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

MAX_LISTING_AGE_DAYS = 30   # Only scan items created in the last 30 days
MIN_FAVORITES = 5           # Minimum favorites threshold
RESULTS_PER_KEYWORD = 25    # How many items to check per keyword
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
            # Store by listing_id as string for fast lookup
            return {str(item["listing_id"]): item for item in data}
    except Exception:
        return {}


def run_scanner():
    client = EtsyClient()
    vault = load_existing_vault()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_discoveries = 0
    updated_items = 0

    print(f"📦 Loaded {len(vault)} existing products from your Permanent Vault.")
    print("🚀 Starting POD Winning Listings Scan...\n")

    for keyword in POD_SEARCH_TERMS:
        print(f"🔍 Scanning keyword: '{keyword}'...")
        
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
            listing_id_str = str(item.get("listing_id"))

            # 1. Determine creation date & age
            created_ts = item.get("original_creation_timestamp") or item.get("creation_timestamp")
            age_days = calculate_age_days(created_ts)

            # 2. Filter: Only recent listings
            if age_days > MAX_LISTING_AGE_DAYS:
                continue

            num_favorers = item.get("num_favorers", 0)

            # 3. Filter: Minimum favorites
            if num_favorers < MIN_FAVORITES:
                continue

            # 4. Calculate Momentum Score
            momentum_score = round(num_favorers / (age_days + 1), 2)

            # Format price
            price_info = item.get("price", {})
            amount = price_info.get("amount", 0)
            divisor = price_info.get("divisor", 100)
            currency = price_info.get("currency_code", "USD")
            formatted_price = f"{amount / divisor:.2f} {currency}"

            # Check if this item is already in our vault
            if listing_id_str in vault:
                # Update stats with the latest numbers
                vault[listing_id_str]["num_favorers"] = num_favorers
                vault[listing_id_str]["momentum_score"] = momentum_score
                vault[listing_id_str]["age_days"] = age_days
                vault[listing_id_str]["last_updated"] = today_str
                updated_items += 1
            else:
                # Brand new discovery! Fetch its image
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
                print(f"   ✨ NEW Winner Discovered: {item.get('title')[:35]}... (Favs: {num_favorers} | Score: {momentum_score})")

    # Convert dictionary back to list and sort by Momentum Score
    all_vault_items = list(vault.values())
    all_vault_items.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)

    # Save to JSON file
    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        json.dump(all_vault_items, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Scan Complete!")
    print(f"✨ New Winners Added: {new_discoveries}")
    print(f"🔄 Existing Winners Updated: {updated_items}")
    print(f"📁 Total Products in Permanent Vault: {len(all_vault_items)}")


if __name__ == "__main__":
    run_scanner()
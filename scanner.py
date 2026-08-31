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
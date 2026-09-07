"""
2-Tier Etsy POD Intelligence Engine
===================================
Tier 1: Discovery Engine — Scans keywords for fresh breakouts (< 30 days).
Tier 2: Surveillance Engine — Pings tracked items directly by ID to monitor
        favorite growth deltas over time (Evergreens vs. Faded).
"""

import html
import time
from datetime import datetime, timezone
from typing import Dict, Any

from etsy_client import EtsyClient
from storage import VaultStorage, DATA_FILE

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
# ⚙️ SCANNER CONFIGURATION
# ==========================================
MAX_DISCOVERY_AGE_DAYS = 30   # Only discover items created in the last 30 days
MIN_FAVORITES = 5             # Filter out noise with zero traction
ITEMS_PER_KEYWORD = 100       # Single page per niche (1 API call per niche)
MAX_SURVEILLANCE_CHECKS = 150 # Max mature vault items to check per daily run


def parse_price(item: Dict[str, Any]) -> str:
    """Formats the price dictionary into a readable string."""
    price_info = item.get("price", {})
    if isinstance(price_info, dict):
        amount = price_info.get("amount", 0)
        divisor = price_info.get("divisor", 100)
        currency = price_info.get("currency_code", "USD")
        return f"{amount / divisor:.2f} {currency}"
    return f"{price_info} USD"


def run_discovery_tier(
    client: EtsyClient,
    vault: Dict[str, Dict[str, Any]],
    today_str: str,
    now_ts: float
) -> int:
    """
    Tier 1: Scans micro-niches for newly listed products with rapid traction.
    """
    new_discoveries = 0
    print("\n" + "=" * 60)
    print("🚀 TIER 1: DISCOVERY ENGINE (Scanning New Listings < 30d)")
    print("=" * 60)

    for idx, keyword in enumerate(POD_SEARCH_TERMS, 1):
        print(f"[{idx:02d}/{len(POD_SEARCH_TERMS)}] 🔍 Niche: '{keyword}'...")

        data = client.search_active_listings(
            keywords=keyword,
            limit=ITEMS_PER_KEYWORD,
            sort_on="created",
            sort_order="desc"
        )

        if not data or "results" not in data:
            continue

        listings = data["results"]
        for item in listings:
            listing_id_str = str(item.get("listing_id"))
            num_favorers = int(item.get("num_favorers", 0))

            # Timestamp check
            created_ts = item.get("original_creation_timestamp") or item.get("creation_timestamp") or now_ts
            age_seconds = max(now_ts - created_ts, 3600)
            age_days = round(age_seconds / 86400, 1)

            # Discovery filter: Under 30 days old and >= MIN_FAVORITES
            if age_days > MAX_DISCOVERY_AGE_DAYS or num_favorers < MIN_FAVORITES:
                continue

            # Update existing or add new discovery
            if listing_id_str in vault:
                # Update current metrics
                entry = vault[listing_id_str]
                entry["num_favorers"] = num_favorers
                entry["last_updated"] = today_str
                fav_history = entry.setdefault("fav_history", {})
                fav_history[today_str] = num_favorers
            else:
                # New Breakout Found! Fetch its image URL
                clean_title = html.unescape(item.get("title", ""))
                image_url = client.get_listing_image(listing_id_str)
                price_str = parse_price(item)
                momentum = round(num_favorers / max(age_days, 0.1), 2)

                vault[listing_id_str] = {
                    "listing_id": item.get("listing_id"),
                    "title": clean_title,
                    "search_keyword": keyword,
                    "created_timestamp": int(created_ts),
                    "age_days": age_days,
                    "num_favorers": num_favorers,
                    "momentum_score": momentum,
                    "price": price_str,
                    "url": item.get("url"),
                    "image_url": image_url,
                    "tags": item.get("tags", []),
                    "views": item.get("views", 0),
                    "is_personalizable": item.get("is_personalizable", False),
                    "first_discovered": today_str,
                    "last_updated": today_str,
                    "fav_history": {today_str: num_favorers}
                }
                new_discoveries += 1
                print(f"   ✨ NEW BREAKOUT: {clean_title[:45]}... (Favs: {num_favorers} | Age: {age_days}d | Momentum: {momentum})")

    return new_discoveries


def run_surveillance_tier(
    client: EtsyClient,
    vault: Dict[str, Dict[str, Any]],
    today_str: str,
    now_ts: float
) -> int:
    """
    Tier 2: Direct lookup of older vault items (> 30 days) to track growth.
    """
    print("\n" + "=" * 60)
    print("🌲 TIER 2: VAULT SURVEILLANCE ENGINE (Tracking Growth of Older Items)")
    print("=" * 60)

    # Find vault items that were NOT updated in today's discovery scan
    items_to_check = [
        listing_id for listing_id, item in vault.items()
        if item.get("last_updated") != today_str
    ]

    print(f"👁️ Identified {len(items_to_check)} items needing surveillance checkpoints...")
    if not items_to_check:
        print("✅ All items already updated today.")
        return 0

    checked_count = 0
    for listing_id in items_to_check[:MAX_SURVEILLANCE_CHECKS]:
        data = client.get_listing(listing_id)
        if not data:
            continue

        item_data = data.get("results", [data])[0] if "results" in data else data
        new_favs = int(item_data.get("num_favorers", 0))

        entry = vault[listing_id]
        prev_favs = entry.get("num_favorers", new_favs)
        fav_delta = new_favs - prev_favs

        entry["num_favorers"] = new_favs
        entry["last_updated"] = today_str
        fav_history = entry.setdefault("fav_history", {})
        fav_history[today_str] = new_favs

        # Dynamic age update
        created_ts = entry.get("created_timestamp", now_ts)
        entry["age_days"] = round(max(now_ts - created_ts, 3600) / 86400, 1)

        checked_count += 1
        if fav_delta > 0:
            print(f"   📈 [{entry['title'][:35]}...] Gained +{fav_delta} favorites! (Total: {new_favs})")

    return checked_count


def run_scanner():
    storage = VaultStorage(DATA_FILE)
    vault = storage.load_vault()
    client = EtsyClient()

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    now_ts = now.timestamp()

    print("======================================================")
    print(f"🏛️  Etsy POD Permanent Vault Engine v2.0")
    print(f"📦  Loaded {len(vault)} products from Vault")
    print(f"🎯  Scanning {len(POD_SEARCH_TERMS)} High-Converting Niches")
    print("======================================================")

    # 1. Run Discovery Tier (Fresh Breakouts < 30 days)
    new_breakouts = run_discovery_tier(client, vault, today_str, now_ts)

    # 2. Run Surveillance Tier (Established items > 30 days)
    surveillance_checks = run_surveillance_tier(client, vault, today_str, now_ts)

    # 3. Save atomically and re-enrich
    storage.save_vault(vault)

    # Summarize lifecycle distribution
    statuses = [item.get("lifecycle_status") for item in vault.values()]
    print("\n" + "=" * 60)
    print("📊 RUN COMPLETE & VAULT REFRESHED")
    print("=" * 60)
    print(f"✨ New Breakouts Discovered: {new_breakouts}")
    print(f"👁️ Surveillance Items Checked: {surveillance_checks}")
    print(f"🏛️ Total Vault Library: {len(vault)} listings")
    print(f"   • 🚀 Breakouts (< 30d): {statuses.count('Breakout')}")
    print(f"   • 🌲 Evergreens (> 30d, actively growing): {statuses.count('Evergreen')}")
    print(f"   • 🥀 Faded (> 30d, flatlined): {statuses.count('Faded')}")
    print("======================================================\n")


if __name__ == "__main__":
    run_scanner()
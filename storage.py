"""
Vault Storage Layer
===================
Handles atomic persistence, schema migration, dynamic age calculation,
favorite timeline tracking, and product lifecycle classification.
"""

import html
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

DATA_FILE = "pod_winners.json"


class VaultStorage:
    def __init__(self, filepath: str = DATA_FILE):
        self.filepath = filepath

    def load_vault(self) -> Dict[str, Dict[str, Any]]:
        """
        Loads the vault from disk and enriches every item with dynamic
        lifecycle statistics (current age, 7d/14d growth, and lifecycle status).
        """
        if not os.path.exists(self.filepath):
            return {}

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
        except Exception as err:
            print(f"⚠️ Error reading {self.filepath}: {err}. Starting with empty vault.")
            return {}

        vault: Dict[str, Dict[str, Any]] = {}
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        for item in raw_items:
            listing_id = str(item.get("listing_id"))
            if not listing_id:
                continue

            migrated = self._migrate_and_enrich_item(item, now, now_ts)
            vault[listing_id] = migrated

        return vault

    def _migrate_and_enrich_item(
        self, item: Dict[str, Any], now: datetime, now_ts: float
    ) -> Dict[str, Any]:
        """
        Ensures backward compatibility with older pod_winners.json schemas
        and computes dynamic lifecycle indicators.
        """
        today_str = now.strftime("%Y-%m-%d")
        current_favs = int(item.get("num_favorers", 0))

        # 1. Ensure created_timestamp exists
        created_ts = item.get("created_timestamp")
        if not created_ts:
            # Fallback for legacy items: estimate created_timestamp from static age_days
            legacy_age = float(item.get("age_days", 0))
            created_ts = now_ts - (legacy_age * 86400)
            item["created_timestamp"] = int(created_ts)

        # 2. Dynamic fractional age in days
        age_seconds = max(now_ts - created_ts, 3600)  # floor at 1 hour
        age_days = round(age_seconds / 86400, 1)
        item["age_days"] = age_days

        # 3. Clean up HTML entities in title
        item["title"] = html.unescape(item.get("title", ""))

        # 4. Migrate / Update Timeline History
        fav_history = item.get("fav_history", {})
        first_discovered = item.get("first_discovered", today_str)

        if not fav_history:
            # Seed history with discovery checkpoint
            fav_history[first_discovered] = current_favs
        
        # Ensure today is recorded or updated
        fav_history[item.get("last_updated", today_str)] = current_favs
        item["fav_history"] = fav_history

        # 5. Compute Velocity Deltas (7-day and 14-day growth)
        favs_7d_ago = self._get_favs_at_checkpoint(fav_history, now - timedelta(days=7))
        favs_14d_ago = self._get_favs_at_checkpoint(fav_history, now - timedelta(days=14))

        delta_7d = max(0, current_favs - favs_7d_ago)
        delta_14d = max(0, current_favs - favs_14d_ago)

        item["delta_7d"] = delta_7d
        item["delta_14d"] = delta_14d

        # 6. Recalculate Smooth Momentum Score
        item["momentum_score"] = round(current_favs / max(age_days, 0.1), 2)

        # 7. Lifecycle Classification
        # - Breakout: <= 30 days old and showing fast traction
        # - Evergreen: > 30 days old and still actively gaining favorites (>= 3 in last 14d)
        # - Faded: > 30 days old and flatlined/stopped gaining
        if age_days <= 30:
            item["lifecycle_status"] = "Breakout"
        elif delta_14d >= 3:
            item["lifecycle_status"] = "Evergreen"
        else:
            item["lifecycle_status"] = "Faded"

        return item

    def _get_favs_at_checkpoint(self, fav_history: Dict[str, int], target_date: datetime) -> int:
        """Finds the recorded favorite count on or closest before target_date."""
        target_str = target_date.strftime("%Y-%m-%d")
        sorted_dates = sorted(fav_history.keys())
        
        closest_favs = fav_history[sorted_dates[0]]
        for date_str in sorted_dates:
            if date_str <= target_str:
                closest_favs = fav_history[date_str]
            else:
                break
        return closest_favs

    def save_vault(self, vault: Dict[str, Dict[str, Any]]) -> None:
        """
        Atomically saves the vault using a tempfile and os.replace
        to prevent partial writes and corrupted data.
        """
        all_items = list(vault.values())
        # Sort by momentum score descending
        all_items.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)

        dir_name = os.path.dirname(os.path.abspath(self.filepath)) or "."
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(all_items, tf, indent=2, ensure_ascii=False)
            temp_path = tf.name

        os.replace(temp_path, self.filepath)


# --- Verification Test ---
if __name__ == "__main__":
    print("Testing Vault Storage and Schema Migration...")
    storage = VaultStorage(DATA_FILE)
    vault = storage.load_vault()

    print(f"\n📦 Successfully loaded {len(vault)} listings from {DATA_FILE}")

    # Inspect lifecycle distribution
    statuses = [item.get("lifecycle_status") for item in vault.values()]
    breakouts = statuses.count("Breakout")
    evergreens = statuses.count("Evergreen")
    faded = statuses.count("Faded")

    print(f"• 🚀 Breakouts (<30d): {breakouts}")
    print(f"• 🌲 Evergreens (>30d, growing): {evergreens}")
    print(f"• 🥀 Faded (>30d, flatlined): {faded}")

    # Inspect a sample item
    if vault:
        sample = next(iter(vault.values()))
        print("\n🔍 Sample Enriched Listing:")
        print(f"• Title: {sample.get('title')[:55]}...")
        print(f"• Dynamic Age: {sample.get('age_days')} days")
        print(f"• Status: {sample.get('lifecycle_status')}")
        print(f"• Favorites: {sample.get('num_favorers')} (Last 14d Growth: +{sample.get('delta_14d')})")
        print(f"• Fav History Points: {sample.get('fav_history')}")

    # Test atomic save
    storage.save_vault(vault)
    print("\n✅ Storage test & atomic migration complete!")
"""
Unified Etsy API v3 Client
==========================
Handles authenticated requests, connection pooling, rate-limiting,
and query methods for both Discovery and Surveillance modes.
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class EtsyClient:
    BASE_URL = "https://openapi.etsy.com/v3/application"

    def __init__(self):
        self.api_key = os.getenv("ETSY_API_KEY")
        self.api_secret = os.getenv("ETSY_API_SECRET")

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Both ETSY_API_KEY and ETSY_API_SECRET must be set in your environment or .env file."
            )

        # Etsy v3 Open API requires combining keystring and shared secret:
        # header format: "x-api-key": "<keystring>:<shared_secret>"
        self.headers = {
            "x-api-key": f"{self.api_key}:{self.api_secret}",
            "Accept": "application/json",
            "User-Agent": "EtsyPODVault/2.0"
        }

        # Safe rate limit: 0.25s keeps requests under ~4 calls/sec (under 5 QPS limit)
        self.min_delay = 0.25
        self.last_request_time = 0.0

        # Connection pooling across all requests
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _rate_limit(self) -> None:
        """Enforces a minimum interval between outbound API calls."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 4) -> Optional[Dict[str, Any]]:
        """
        Executes a rate-limited GET request to Etsy Open API v3 with exponential backoff.
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        for attempt in range(max_retries):
            self._rate_limit()
            try:
                response = self.session.get(url, params=params, timeout=15)

                # 200 OK
                if response.status_code == 200:
                    return response.json()

                # 429 Too Many Requests: Exponential backoff
                elif response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    print(f"⚠️ [429] Rate limited on /{endpoint}. Pausing {wait_time}s...", file=sys.stderr)
                    time.sleep(wait_time)
                    continue

                # 404 Not Found (e.g. deactivated/sold-out listing during surveillance)
                elif response.status_code == 404:
                    return None

                # Other HTTP errors
                else:
                    print(
                        f"❌ API Error [{response.status_code}] on /{endpoint}: {response.text[:200]}",
                        file=sys.stderr
                    )
                    return None

            except requests.RequestException as err:
                wait_time = attempt + 1
                print(f"⚠️ Network error on attempt {attempt + 1}: {err}. Retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)

        print(f"❌ Aborted: Failed to fetch /{endpoint} after {max_retries} attempts.", file=sys.stderr)
        return None

    def search_active_listings(
        self,
        keywords: str,
        limit: int = 100,
        offset: int = 0,
        sort_on: str = "created",
        sort_order: str = "desc"
    ) -> Optional[Dict[str, Any]]:
        """
        Searches active listings for discovery mode.
        """
        params = {
            "keywords": keywords,
            "limit": min(limit, 100),
            "offset": offset,
            "sort_on": sort_on,
            "sort_order": sort_order
        }
        return self.get("listings/active", params=params)

    def get_listing(self, listing_id: int | str) -> Optional[Dict[str, Any]]:
        """
        Fetches an individual listing directly by ID (for surveillance mode).
        """
        return self.get(f"listings/{listing_id}", params={"includes": "images"})

    def get_listing_image(self, listing_id: int | str) -> Optional[str]:
        """
        Fetches the primary image URL (570xN) for a qualified winner listing.
        """
        data = self.get(f"listings/{listing_id}/images")
        if data and "results" in data and len(data["results"]) > 0:
            return data["results"][0].get("url_570xN")
        return None

    def get_listing_reviews(self, listing_id: int | str) -> int:
        """
        Fetches verified review count for a listing.
        """
        params = {"limit": 1, "offset": 0}
        data = self.get(f"listings/{listing_id}/reviews", params=params)
        if data and "count" in data:
            return int(data["count"])
        return 0


# --- Verification Test ---
if __name__ == "__main__":
    print("Testing upgraded Etsy Client...")
    try:
        client = EtsyClient()
        test_search = client.search_active_listings("custom embroidered sweatshirt", limit=1)

        if test_search and "results" in test_search and len(test_search["results"]) > 0:
            sample = test_search["results"][0]
            listing_id = sample.get("listing_id")
            title = sample.get("title", "")[:50]

            # Fetch the image for this listing
            img_url = client.get_listing_image(listing_id)

            print("\n✅ EtsyClient test successful!")
            print(f"• Listing ID: {listing_id}")
            print(f"• Title: {title}...")
            print(f"• Image fetched successfully: {bool(img_url)} -> {img_url}")
        else:
            print("\n⚠️ Request completed, but returned no listings. Check your query or permissions.")
    except Exception as e:
        print(f"\n❌ Client test failed: {e}")
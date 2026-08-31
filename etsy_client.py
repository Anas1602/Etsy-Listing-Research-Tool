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
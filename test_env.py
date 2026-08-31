import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ETSY_API_KEY")

if api_key and api_key != "your_keystring_here":
    print("✅ Environment is configured properly! API Key loaded.")
else:
    print("❌ Error: ETSY_API_KEY not found or still set to placeholder in .env")
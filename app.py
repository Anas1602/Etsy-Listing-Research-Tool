import json
import os
import streamlit as st
import pandas as pd
from collections import Counter
import subprocess

st.set_page_config(
    page_title="Etsy POD Trend Hunter",
    page_icon="🔥",
    layout="wide"
)

# --- Data Loading ---
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
st.title("🔥 Etsy POD Trend Hunter")
st.caption("Spotting high-momentum, recently created Print-on-Demand listings on Etsy.")

col_top1, col_top2 = st.columns([3, 1])
with col_top2:
    if st.button("🔄 Run Live Scan Now", use_container_width=True):
        with st.spinner("Scanning Etsy API for recent winners..."):
            subprocess.run(["python", "scanner.py"])
            st.rerun()

if not listings:
    st.warning("No listings found yet. Click 'Run Live Scan Now' above or run `python scanner.py` in your terminal.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")

all_keywords = sorted(list(set(item.get("search_keyword", "Other") for item in listings)))
selected_keywords = st.sidebar.multiselect("Filter by Seed Keyword", all_keywords, default=all_keywords)

min_score = st.sidebar.slider(
    "Minimum Momentum Score", 
    min_value=0.0, 
    max_value=float(max(item.get("momentum_score", 1.0) for item in listings)), 
    value=0.0, 
    step=0.5
)

max_age = st.sidebar.slider(
    "Max Listing Age (Days)", 
    min_value=1, 
    max_value=30, 
    value=30
)

only_customizable = st.sidebar.checkbox("Only Customizable / Personalized Items", value=False)

# --- Apply Filters ---
filtered_listings = [
    item for item in listings
    if item.get("search_keyword") in selected_keywords
    and item.get("momentum_score", 0) >= min_score
    and item.get("age_days", 0) <= max_age
    and (not only_customizable or item.get("is_personalizable", False))
]

# --- Top Stats Banner ---
st.write("---")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Winners Tracked", len(listings))
m2.metric("Matching Filters", len(filtered_listings))
if filtered_listings:
    top_score = max(item["momentum_score"] for item in filtered_listings)
    avg_favs = round(sum(item["num_favorers"] for item in filtered_listings) / len(filtered_listings), 1)
    m3.metric("Top Momentum Score", f"🔥 {top_score}")
    m4.metric("Avg. Favorites", avg_favs)
st.write("---")

# --- Product Display Grid ---
st.subheader("📦 Winning Listings Grid")

if not filtered_listings:
    st.info("No listings match the selected filters.")
else:
    # Render in 3-column grid
    cols_per_row = 3
    for i in range(0, len(filtered_listings), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(filtered_listings):
                item = filtered_listings[i + j]
                with cols[j]:
                    with st.container(border=True):
                        # Display Mockup Image
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
                        score = item["momentum_score"]
                        if score >= 5.0:
                            st.success(f"🚀 Breakout Score: **{score}**")
                        elif score >= 2.0:
                            st.info(f"⚡ High Traction: **{score}**")
                        else:
                            st.warning(f"📈 Momentum Score: **{score}**")
                        
                        # Tags Accordion
                        if item.get("tags"):
                            with st.expander("🏷️ View 13 SEO Tags"):
                                st.write(", ".join([f"`{t}`" for t in item["tags"]]))

# --- SEO Tag Analysis Section ---
st.write("---")
st.subheader("🏷️ Top Recurring Tags Across Winners")

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
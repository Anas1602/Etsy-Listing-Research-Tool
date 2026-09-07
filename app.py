"""
Etsy POD Trend Vault — Intelligence Dashboard
==============================================
Interactive dashboard featuring Product Lifecycle segmentation
(Breakouts vs. Evergreens vs. Faded), 14-day velocity deltas,
and tag analytics.
"""

import html
import subprocess
from collections import Counter
from datetime import datetime, timezone
import pandas as pd
import streamlit as st

from storage import VaultStorage, DATA_FILE

st.set_page_config(
    page_title="Etsy POD Trend Vault",
    page_icon="🏛️",
    layout="wide"
)

# --- Data Loading with Streamlit Caching ---
@st.cache_data(ttl=60)
def get_vault_data():
    storage = VaultStorage(DATA_FILE)
    vault = storage.load_vault()
    return list(vault.values())

listings = get_vault_data()

# --- Header & Scanner Trigger ---
col_title, col_btn = st.columns([3, 1])
with col_title:
    st.title("🏛️ Etsy POD Intelligence Vault")
    st.caption("Surveillance system tracking newly emerging breakouts and compounding evergreen winners over time.")

with col_btn:
    if st.button("🔄 Run Live Scan Now", use_container_width=True, type="primary"):
        with st.spinner("Scanning 44 micro-niches & updating surveillance checkpoints..."):
            subprocess.run(["python", "scanner.py"], check=True)
            st.cache_data.clear()
            st.rerun()

if not listings:
    st.warning("Vault is empty. Click 'Run Live Scan Now' above to start finding winners.")
    st.stop()

# --- Top Key Metrics Banner ---
st.write("---")
breakouts = [i for i in listings if i.get("lifecycle_status") == "Breakout"]
evergreens = [i for i in listings if i.get("lifecycle_status") == "Evergreen"]
faded = [i for i in listings if i.get("lifecycle_status") == "Faded"]

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("🏛️ Total Vault Library", len(listings))
kpi2.metric("🚀 Fresh Breakouts (<30d)", len(breakouts))
kpi3.metric("🌲 Proven Evergreens", len(evergreens))
kpi4.metric("🥀 Faded / Flatlined", len(faded))
top_recent_gainer = max(listings, key=lambda x: x.get("delta_14d", 0))
kpi5.metric("🔥 Top 14d Growth", f"+{top_recent_gainer.get('delta_14d', 0)} favs")
st.write("---")

# --- Sidebar Filters & Controls ---
st.sidebar.header("🔍 Vault Filters & Controls")

# Lifecycle Filter Tab Mode
lifecycle_mode = st.sidebar.radio(
    "Select Vault Section",
    [
        "🚀 Fresh Breakouts (< 30d)",
        "🌲 Proven Evergreens (> 30d)",
        "🥀 Faded Trends (> 30d Stagnant)",
        "🌐 All Listings (Complete Vault)"
    ]
)

# Keyword Filter
all_keywords = sorted(list(set(item.get("search_keyword", "Other") for item in listings)))
selected_keywords = st.sidebar.multiselect("Filter by Seed Niche", all_keywords, default=all_keywords)

# Sorting Options
sort_by = st.sidebar.selectbox(
    "Sort Products By",
    [
        "Highest 14-Day Growth (+Favs)",
        "Highest Momentum Score",
        "Most Total Favorites",
        "Newest Listing Age",
        "Recently Discovered"
    ]
)

# Minimum Favorites Slider
max_fav_in_data = max((item.get("num_favorers", 10) for item in listings), default=100)
min_favs = st.sidebar.slider("Minimum Total Favorites", min_value=0, max_value=int(max_fav_in_data), value=5)

# Minimum 14-Day Growth Slider
min_growth_14d = st.sidebar.slider("Minimum 14-Day Fav Growth (Δ)", min_value=0, max_value=100, value=0)

# Customizable only
only_customizable = st.sidebar.checkbox("Only Personalized / Customizable Items", value=False)

# --- Filter Application ---
filtered_listings = []
for item in listings:
    # 1. Lifecycle filter
    status = item.get("lifecycle_status", "Breakout")
    if lifecycle_mode == "🚀 Fresh Breakouts (< 30d)" and status != "Breakout":
        continue
    elif lifecycle_mode == "🌲 Proven Evergreens (> 30d)" and status != "Evergreen":
        continue
    elif lifecycle_mode == "🥀 Faded Trends (> 30d Stagnant)" and status != "Faded":
        continue

    # 2. Keyword filter
    if item.get("search_keyword") not in selected_keywords:
        continue

    # 3. Numeric thresholds
    if item.get("num_favorers", 0) < min_favs:
        continue
    if item.get("delta_14d", 0) < min_growth_14d:
        continue

    # 4. Customization filter
    if only_customizable and not item.get("is_personalizable", False):
        continue

    filtered_listings.append(item)

# --- Sort Application ---
if sort_by == "Highest 14-Day Growth (+Favs)":
    filtered_listings.sort(key=lambda x: x.get("delta_14d", 0), reverse=True)
elif sort_by == "Highest Momentum Score":
    filtered_listings.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)
elif sort_by == "Most Total Favorites":
    filtered_listings.sort(key=lambda x: x.get("num_favorers", 0), reverse=True)
elif sort_by == "Newest Listing Age":
    filtered_listings.sort(key=lambda x: x.get("age_days", 999))
elif sort_by == "Recently Discovered":
    filtered_listings.sort(key=lambda x: x.get("first_discovered", ""), reverse=True)

# --- Product Grid & Pagination ---
st.subheader(f"{lifecycle_mode} — ({len(filtered_listings)} listings)")

# Pagination settings
ITEMS_PER_PAGE = 18
total_pages = max(1, (len(filtered_listings) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

if total_pages > 1:
    page_num = st.number_input("Page", min_value=1, max_value=total_pages, step=1, value=1)
else:
    page_num = 1

start_idx = (page_num - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
current_page_items = filtered_listings[start_idx:end_idx]

if not current_page_items:
    st.info("No listings match the selected filters.")
else:
    cols_per_row = 3
    for i in range(0, len(current_page_items), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(current_page_items):
                item = current_page_items[i + j]
                clean_title = html.unescape(item.get("title", ""))
                status = item.get("lifecycle_status", "Breakout")

                with cols[j]:
                    with st.container(border=True):
                        # Thumbnail image
                        if item.get("image_url"):
                            st.image(item["image_url"], use_container_width=True)
                        else:
                            st.write("*(No Image Available)*")

                        # Clickable Title
                        st.markdown(f"**[{clean_title[:55]}...]({item.get('url', '#')})**")

                        # Metrics row
                        c1, c2, c3 = st.columns(3)
                        c1.caption(f"💰 **{item.get('price', 'N/A')}**")
                        c2.caption(f"📅 **{item.get('age_days', 0)}d old**")
                        c3.caption(f"❤️ **{item.get('num_favorers', 0)} favs**")

                        # Lifecycle & Velocity Badges
                        delta = item.get("delta_14d", 0)
                        b1, b2 = st.columns([1, 1])
                        with b1:
                            if status == "Breakout":
                                st.success(f"🚀 Breakout: **{item.get('momentum_score', 0)}**")
                            elif status == "Evergreen":
                                st.info(f"🌲 Evergreen Seller")
                            else:
                                st.warning("🥀 Flatlined Trend")

                        with b2:
                            if delta > 0:
                                st.metric("14d Growth", f"+{delta} favs", label_visibility="collapsed")
                            else:
                                st.caption("Growth: 0 recent")

                        # Expandable Timeline & Tags
                        with st.expander("📈 Favorite History Timeline"):
                            fav_hist = item.get("fav_history", {})
                            if fav_hist:
                                df_hist = pd.DataFrame(
                                    list(fav_hist.items()),
                                    columns=["Date", "Favorites"]
                                ).sort_values("Date")
                                st.dataframe(df_hist, hide_index=True, use_container_width=True)

                        if item.get("tags"):
                            with st.expander("🏷️ SEO Tags"):
                                st.write(", ".join([f"`{t}`" for t in item["tags"]]))

# --- SEO Tag Intelligence Section ---
st.write("---")
st.subheader("🏷️ Recurring Winning SEO Tags in Current View")

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
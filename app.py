import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# Load interconnectors
df = pd.read_csv("interconnectors.csv")

# Define middle points
middle_points = {
    "Turkey": [39.0, 35.2],
    "Bulgaria": [42.8, 25.3],
    "Romania": [45.9, 24.9],
    "Greece": [39.1, 22.9],
    "Serbia": [44.0, 20.5],
    "Hungary": [47.2, 19.5],
    "Croatia": [45.1, 15.6],
    "Slovenia": [46.1, 14.8],
    "Austria": [47.5, 14.6],
    "Slovakia": [48.7, 19.7],
    "Ukraine": [48.4, 31.0],
    "Moldova": [47.0, 28.8]
}

st.set_page_config(page_title="Gas Interconnector Map", layout="wide")

st.title("🗺️ CEE Gas Interconnector Market Intelligence Map")

# Filter section
countries = sorted(set(df['from']) | set(df['to']))
selected = st.multiselect("Filter by country (from or to)", countries, default=countries)

filtered_df = df[df["from"].isin(selected) | df["to"].isin(selected)]

# Create map
m = folium.Map(location=[47, 20], zoom_start=6, tiles="CartoDB Positron")

# Add interconnector markers
for _, row in filtered_df.iterrows():
    folium.Marker(
        location=[row["lat"], row["lon"]],
        tooltip=f"{row['name']} ({row['from']} → {row['to']})",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

    from_mid = middle_points.get(row["from"])
    to_mid = middle_points.get(row["to"])

    if from_mid:
        folium.PolyLine([from_mid, [row["lat"], row["lon"]]], color="gray", weight=2.5, opacity=0.6).add_to(m)
    if to_mid:
        folium.PolyLine([to_mid, [row["lat"], row["lon"]]], color="gray", weight=2.5, opacity=0.6).add_to(m)

# Show map
st_data = st_folium(m, width=1000, height=600)

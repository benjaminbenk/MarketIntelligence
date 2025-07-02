import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os

EXCEL_PATH = "interconnectors_data.xlsx"

# Ensure Excel file exists
if not os.path.isfile(EXCEL_PATH):
    # Initial columns: ID, Country, Interconnector, Date, Info, Lat, Lon
    pd.DataFrame(columns=[
        "ID", "Country", "Interconnector", "Date", "Info", "Lat", "Lon"
    ]).to_excel(EXCEL_PATH, index=False)

# Load Excel data
@st.cache_data(ttl=30)
def load_data():
    return pd.read_excel(EXCEL_PATH)

def save_data(df):
    df.to_excel(EXCEL_PATH, index=False)

df = load_data()

# Midpoints for countries
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

# Filters
countries = sorted(set(middle_points.keys()))
interconnectors = sorted(df['Interconnector'].dropna().unique()) if not df.empty else []
selected_country = st.sidebar.multiselect("Country", countries, default=countries)
selected_interconnector = st.sidebar.multiselect("Interconnector", interconnectors, default=interconnectors)

# Date filter
min_date = df['Date'].min() if not df.empty else None
max_date = df['Date'].max() if not df.empty else None
date_range = st.sidebar.date_input("Date range", [min_date, max_date] if min_date and max_date else [datetime(2000,1,1), datetime.today()])

filtered_df = df[
    (df['Country'].isin(selected_country)) &
    (df['Interconnector'].isin(selected_interconnector)) &
    (df['Date'] >= pd.to_datetime(date_range[0])) &
    (df['Date'] <= pd.to_datetime(date_range[1]))
] if not df.empty else df

# Map
m = folium.Map(location=[47, 20], zoom_start=6, tiles="CartoDB Positron")

def popup_html(row):
    return f"""
    <b>{row['Country']} - {row['Interconnector']}</b><br>
    Date: {row['Date'].strftime('%Y-%m-%d') if pd.notnull(row['Date']) else ''}<br>
    Info: {row['Info']}<br>
    <a href="/?edit={row['ID']}" target="_self">Edit</a>
    """

# Add markers for interconnectors
for _, row in filtered_df.iterrows():
    folium.Marker(
        location=[row["Lat"], row["Lon"]],
        tooltip=f"{row['Interconnector']} ({row['Country']})",
        popup=folium.Popup(popup_html(row), max_width=250),
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

# Add country midpoint markers
for country, coords in middle_points.items():
    folium.CircleMarker(
        location=coords,
        radius=6,
        color="black",
        fill=True,
        fill_opacity=0.8,
        popup=country
    ).add_to(m)

st_folium(m, width=1000, height=600)

# Show/Add/Edit info
st.header("Add or Edit Info")

# For editing
edit_id = st.query_params.get('edit')
edit_row = df[df['ID'] == int(edit_id)].iloc[0] if edit_id and not df.empty and int(edit_id) in df['ID'].values else None

with st.form("info_form", clear_on_submit=True):
    country = st.selectbox("Country", countries, index=countries.index(edit_row['Country']) if edit_row is not None else 0)
    interconnector = st.text_input("Interconnector", edit_row['Interconnector'] if edit_row is not None else "")
    date = st.date_input("Date", edit_row['Date'] if edit_row is not None else datetime.today())
    info = st.text_area("Info", edit_row['Info'] if edit_row is not None else "")
    lat = st.number_input("Latitude", value=edit_row['Lat'] if edit_row is not None else 47.0, format="%.6f")
    lon = st.number_input("Longitude", value=edit_row['Lon'] if edit_row is not None else 20.0, format="%.6f")
    submitted = st.form_submit_button("Save Info")

    if submitted:
        if edit_row is not None:
            # Update
            df.loc[df['ID'] == edit_row['ID'], ["Country", "Interconnector", "Date", "Info", "Lat", "Lon"]] = [
                country, interconnector, date, info, lat, lon
            ]
            save_data(df)
            st.success("Info updated!")
        else:
            # Add new
            new_id = (df['ID'].max() + 1) if not df.empty else 1
            new_row = pd.DataFrame([{
                "ID": new_id,
                "Country": country,
                "Interconnector": interconnector,
                "Date": date,
                "Info": info,
                "Lat": lat,
                "Lon": lon
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.success("New info added!")

        st.experimental_rerun()

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO
import numpy as np

# --- Google Sheets Setup ---
SHEET_NAME = "MarketIntelligenceGAS"  # Your actual sheet name
EXCEL_LINK = "https://docs.google.com/spreadsheets/d/12jH5gmwMopM9j5uTWOtc6wEafscgf5SvT8gDmoAFawE/edit?gid=0#gid=0"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gs_client():
    gcp_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(gcp_info, scopes=SCOPES)
    return gspread.authorize(credentials)

def get_gs_sheet():
    gc = get_gs_client()
    return gc.open(SHEET_NAME).sheet1

def load_data():
    sheet = get_gs_sheet()
    df = pd.DataFrame(sheet.get_all_records())
    return df

def save_data(df):
    sheet = get_gs_sheet()
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- App UI ---
st.set_page_config(page_title="Gas Map", layout="wide")
st.title("🗺️ CEE Gas Market Intelligence Map")

# --- Button for Sheet Link ---
st.markdown(
    f'<a href="{EXCEL_LINK}" target="_blank"><button style="background-color:#4CAF50;color:white;padding:10px 20px;border:none;border-radius:4px;cursor:pointer;font-size:16px;">Open historical data</button></a>',
    unsafe_allow_html=True
)

# --- Load Data ---
try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data from Google Sheets: {e}")
    st.stop()

# Define interconnector endpoints
interconnectors_data = [
    {"name": "Turkey-Bulgaria", "from": "Turkey", "to": "Bulgaria", "lat": 41.7, "lon": 27.0},
    {"name": "Bulgaria-Romania", "from": "Bulgaria", "to": "Romania", "lat": 43.8, "lon": 28.6},
    {"name": "Bulgaria-Serbia", "from": "Bulgaria", "to": "Serbia", "lat": 43.5, "lon": 22.5},
    {"name": "Greece-Bulgaria", "from": "Greece", "to": "Bulgaria", "lat": 41.4, "lon": 23.3},
    {"name": "Kiskundorozsma", "from": "Serbia", "to": "Hungary", "lat": 46.1, "lon": 19.9},
    {"name": "Serbia-Romania", "from": "Serbia", "to": "Romania", "lat": 45.3, "lon": 21.0},
    {"name": "Drávaszerdahely", "from": "Croatia", "to": "Hungary", "lat": 45.9, "lon": 17.8},
    {"name": "Croatia-Slovenia", "from": "Croatia", "to": "Slovenia", "lat": 45.5, "lon": 15.6},
    {"name": "HAG", "from": "Austria", "to": "Hungary", "lat": 47.8, "lon": 16.6},
    {"name": "Austria-Slovakia", "from": "Austria", "to": "Slovakia", "lat": 48.2, "lon": 16.9},
    {"name": "Balassagyarmat", "from": "Hungary", "to": "Slovakia", "lat": 47.9, "lon": 18.0},
    {"name": "Csanádpalota", "from": "Hungary", "to": "Romania", "lat": 46.3, "lon": 21.3},
    {"name": "Bereg", "from": "Hungary", "to": "Ukraine", "lat": 48.2, "lon": 22.6},
    {"name": "Romania-Moldova", "from": "Romania", "to": "Moldova", "lat": 47.2, "lon": 27.0},
    {"name": "Romania-Ukraine", "from": "Romania", "to": "Ukraine", "lat": 45.3, "lon": 28.3},
    {"name": "Slovakia-Ukraine", "from": "Slovakia", "to": "Ukraine", "lat": 48.6, "lon": 21.9},
]

df = pd.DataFrame(interconnectors_data)

# --- Country Midpoints renamed by gas point ---
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

# --- Filtering ---
countries = sorted(middle_points.keys())
interconnectors = sorted(df['Interconnector'].dropna().unique()) if not df.empty else []
selected_country = st.sidebar.multiselect("Country", countries, default=countries)
selected_interconnector = st.sidebar.multiselect("Interconnector", interconnectors, default=interconnectors)
min_date = pd.to_datetime(df['Date']).min() if not df.empty else datetime(2000,1,1)
max_date = pd.to_datetime(df['Date']).max() if not df.empty else datetime.today()
date_range = st.sidebar.date_input("Date range", [min_date, max_date])

if not df.empty:
    filtered_df = df[
        (df['Country'].isin(selected_country)) &
        (df['Interconnector'].isin(selected_interconnector)) &
        (pd.to_datetime(df['Date']) >= pd.to_datetime(date_range[0])) &
        (pd.to_datetime(df['Date']) <= pd.to_datetime(date_range[1]))
    ]
else:
    filtered_df = df

# --- Map Visualization ---
m = folium.Map(location=[47, 20], zoom_start=6, tiles="CartoDB Positron")

# Draw country midpoint circles
for country, coords in middle_points.items():
    folium.CircleMarker(
        location=coords,
        radius=6,
        color="black",
        fill=True,
        fill_opacity=0.8,
        popup=country
    ).add_to(m)

# Draw lines between connected midpoints (ENTSOG-style)
for _, row in filtered_df.iterrows():
    if pd.notna(row.get("From Node")) and pd.notna(row.get("To Node")):
        from_node = row["From Node"]
        to_node = row["To Node"]
        from_coords = middle_points.get(from_node)
        to_coords = middle_points.get(to_node)
        if from_coords and to_coords:
            folium.PolyLine(
                locations=[from_coords, to_coords],
                color="purple",
                weight=3,
                opacity=0.7,
                tooltip=f"{from_node} → {to_node}"
            ).add_to(m)

st_data = st_folium(m, width=1000, height=600)

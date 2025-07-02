import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO

# --- Google Sheets Setup ---
SHEET_NAME = "MarketIntelligenceGAS"
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

# --- Interconnector endpoints (static for lines on map) ---
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

# --- App UI ---
st.set_page_config(page_title="Gas Map", layout="wide")
st.title("CEE Gas Market Intelligence Map")

# --- Button for Sheet Link ---
st.markdown(
    f'<a href="{EXCEL_LINK}" target="_blank"><button style="background-color:#4CAF50;color:white;padding:10px 20px;border:none;border-radius:4px;cursor:pointer;font-size:16px;">Go to Google Sheet</button></a>',
    unsafe_allow_html=True
)

# --- Load Data ---
try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data from Google Sheets: {e}")
    st.stop()

# --- Country Midpoints ---
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
m = folium.Map(location=[47, 20], zoom_start=5, tiles="CartoDB Positron")

# Draw markers for each interconnector entry from Google Sheet
for _, row in filtered_df.iterrows():
    popup_html = f"""
    <b>{row['Country']} - {row['Interconnector']}</b><br>
    Date: {row['Date']}<br>
    Info: {row['Info']}
    """
    folium.Marker(
        location=[row["Lat"], row["Lon"]],
        tooltip=f"{row['Interconnector']} ({row['Country']})",
        popup=folium.Popup(popup_html, max_width=100),
        icon=folium.Icon(color="red", icon="triangle")
    ).add_to(m)

# Draw static interconnector lines and markers
for ic in interconnectors_data:
    from_mid = middle_points.get(ic["from"])
    to_mid = middle_points.get(ic["to"])
    if from_mid and to_mid:
        folium.PolyLine(
            locations=[from_mid, [ic["lat"], ic["lon"]], to_mid],
            color="grey",
            weight=1,
            opacity=1,
            dash_array="10,10"
        ).add_to(m)
    folium.Marker(
        location=[ic["lat"], ic["lon"]],
        tooltip=f"{ic['name']} ({ic['from']} → {ic['to']})",
        icon=folium.Icon(color="grey", icon="pipe")
    ).add_to(m)

# Draw country midpoint circles
for country, coords in middle_points.items():
    folium.CircleMarker(
        location=coords,
        radius=2,
        color="black",
        fill=True,
        fill_opacity=0.8,
        popup=country
    ).add_to(m)

st_data = st_folium(m, width=1000, height=600)

# --- Editable Table / Add/Edit Info ---
st.header("Add or Edit Interconnector Info")
with st.form("add_edit_form", clear_on_submit=True):
    id_val = st.number_input("ID (for new, pick a new number)", value=int(df['ID'].max()+1) if not df.empty else 1, step=1)
    country = st.selectbox("Country", countries)
    interconnector = st.text_input("Interconnector")
    date = st.date_input("Date", datetime.today())
    info = st.text_area("Info")
    lat = st.number_input("Latitude", value=47.0, format="%.6f")
    lon = st.number_input("Longitude", value=20.0, format="%.6f")
    submitted = st.form_submit_button("Save")
    if submitted:
        new_row = {
            "ID": id_val,
            "Country": country,
            "Interconnector": interconnector,
            "Date": date.strftime("%Y-%m-%d"),
            "Info": info,
            "Lat": lat,
            "Lon": lon
        }
        exists = not df.empty and (df['ID'] == id_val).any()
        if exists:
            df.loc[df['ID'] == id_val, :] = pd.Series(new_row)
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(df)
        st.success("Information saved to Google Sheet!")
        st.experimental_rerun()

# --- Data Download ---
st.header("Download Data")
to_download = BytesIO()
df.to_excel(to_download, index=False)
to_download.seek(0)
st.download_button("Download Excel", to_download, file_name="interconnectors_data.xlsx")


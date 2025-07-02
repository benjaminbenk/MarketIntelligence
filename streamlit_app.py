import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO

# --- Google Sheets Setup ---
SHEET_NAME = "YOUR_SHEET_NAME_HERE"  # e.g., "Interconnectors"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gs_client():
    # Pull credentials from Streamlit secrets
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
st.set_page_config(page_title="Gas Interconnector Map", layout="wide")
st.title("🗺️ CEE Gas Interconnector Market Intelligence Map")

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
m = folium.Map(location=[47, 20], zoom_start=6, tiles="CartoDB Positron")

for _, row in filtered_df.iterrows():
    popup_html = f"""
    <b>{row['Country']} - {row['Interconnector']}</b><br>
    Date: {row['Date']}<br>
    Info: {row['Info']}
    """
    folium.Marker(
        location=[row["Lat"], row["Lon"]],
        tooltip=f"{row['Interconnector']} ({row['Country']})",
        popup=folium.Popup(popup_html, max_width=250),
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

for country, coords in middle_points.items():
    folium.CircleMarker(
        location=coords,
        radius=6,
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

# --- Data Import ---
st.header("Import Data")
uploaded = st.file_uploader("Import Excel file", type=["xlsx"])
if uploaded:
    df_new = pd.read_excel(uploaded)
    save_data(df_new)
    st.success("File imported and saved to Google Sheet! Please reload the page.")

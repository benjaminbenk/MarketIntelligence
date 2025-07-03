import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
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
    with st.spinner("Loading data from Google Sheets..."):
        sheet = get_gs_sheet()
        df = pd.DataFrame(sheet.get_all_records())
        return df

def save_data(df):
    with st.spinner("Saving data to Google Sheets..."):
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
st.title("🗺️ CEE Gas Market Intelligence Map")

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

# Interconnector selection for highlight
interconnector_labels = [
    f"{ic['name']} ({ic['from']} → {ic['to']})" for ic in interconnectors_data
]
selected_ic_label = st.sidebar.selectbox("Highlight Static Interconnector", ["None"] + interconnector_labels)
highlight_ic = None
if selected_ic_label != "None":
    highlight_ic = next(ic for ic in interconnectors_data if f"{ic['name']} ({ic['from']} → {ic['to']})" == selected_ic_label)

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

# --- Marker Clusters for dynamic (Google Sheet) points ---
dynamic_cluster = MarkerCluster(name="Dynamic Entries").add_to(m)

# Draw dynamic markers (from Google Sheet)
for _, row in filtered_df.iterrows():
    popup_html = f"""
    <table style='font-size:90%;'>
      <tr><th>Country</th><td>{row['Country']}</td></tr>
      <tr><th>Interconnector</th><td>{row['Interconnector']}</td></tr>
      <tr><th>Date</th><td>{row['Date']}</td></tr>
      <tr><th>Info</th><td>{row['Info']}</td></tr>
      <tr><th>Lat/Lon</th><td>{row['Lat']:.4f}, {row['Lon']:.4f}</td></tr>
    </table>
    """
    folium.Marker(
        location=[row["Lat"], row["Lon"]],
        tooltip=f"{row['Interconnector']} ({row['Country']})",
        popup=folium.Popup(popup_html, max_width=320),
        icon=folium.Icon(color="red", icon="landmark")
    ).add_to(dynamic_cluster)

# --- Static Interconnector lines and markers ---
static_cluster = MarkerCluster(name="Static Interconnectors").add_to(m)
for ic in interconnectors_data:
    from_mid = middle_points.get(ic["from"])
    to_mid = middle_points.get(ic["to"])
    is_highlight = (highlight_ic is not None and ic['name'] == highlight_ic['name'])
    # Highlight the selected interconnector in blue, others in grey
    line_color = "blue" if is_highlight else "grey"
    marker_color = "blue" if is_highlight else "grey"
    marker_icon = "star" if is_highlight else "pipe-valve"
    marker_opacity = 1 if is_highlight else 0.7
    if from_mid and to_mid:
        folium.PolyLine(
            locations=[from_mid, [ic["lat"], ic["lon"]], to_mid],
            color=line_color,
            weight=6 if is_highlight else 2,
            opacity=0.8 if is_highlight else 0.5,
            dash_array=None if is_highlight else "10,10"
        ).add_to(m)
    # Improved popup as HTML table
    popup_html = f"""
    <table style='font-size:90%;'>
      <tr><th>Name</th><td>{ic['name']}</td></tr>
      <tr><th>From</th><td>{ic['from']}</td></tr>
      <tr><th>To</th><td>{ic['to']}</td></tr>
      <tr><th>Lat/Lon</th><td>{ic['lat']:.4f}, {ic['lon']:.4f}</td></tr>
    </table>
    """
    folium.Marker(
        location=[ic["lat"], ic["lon"]],
        tooltip=f"{ic['name']} ({ic['from']} → {ic['to']})",
        popup=folium.Popup(popup_html, max_width=320),
        icon=folium.Icon(color=marker_color, icon=marker_icon),
        opacity=marker_opacity
    ).add_to(static_cluster)

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

# --- Add Legend ---
legend_html = """
<div style="
     position: fixed;
     bottom: 50px;
     left: 50px;
     width: 230px;
     height: 120px;
     z-index:9999;
     font-size:14px;
     background: rgba(255,255,255,0.92);
     border:2px solid #444;
     border-radius: 8px;
     padding: 10px 18px;">
<b>Legend</b><br>
<i class="fa fa-landmark fa-2x" style="color:red"></i> Dynamic (user) entry<br>
<i class="fa fa-pipe-valve fa-2x" style="color:grey"></i> Static interconnector<br>
<i class="fa fa-star fa-2x" style="color:blue"></i> Highlighted interconnector<br>
<span style="display:inline-block;width:22px;height:5px;background:blue;margin:0 6px 0 4px;vertical-align:middle"></span> Highlighted line<br>
<span style="display:inline-block;width:22px;height:5px;background:grey;margin:0 6px 0 4px;vertical-align:middle"></span> Static line<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st_data = st_folium(m, width=2000, height=600)

# --- Editable Table / Add/Edit Info ---
st.header("Add or Edit Interconnector Info")
with st.form("add_edit_form", clear_on_submit=True):
    # --- Validate unique ID: provide 'Auto' mode ---
    id_mode = st.radio("ID assignment", ["Auto", "Manual"], horizontal=True)
    if id_mode == "Manual":
        id_val = st.number_input(
            "ID (choose a unique number)", 
            value=int(df['ID'].max()+1) if not df.empty else 1, 
            step=1, 
            min_value=1
        )
        # Check for duplicate ID warning
        if not df.empty and (df['ID'] == id_val).any():
            st.warning("This ID already exists! Please choose a unique number or select Auto.")
    else:
        id_val = int(df['ID'].max()+1) if not df.empty else 1

    # --- Interconnector dropdown: combine with country info ---
    interconnector_labels = [
        f"{ic['name']} ({ic['from']} → {ic['to']})" for ic in interconnectors_data
    ]
    selected_ic_label = st.selectbox("Interconnector", ["Custom/Other"] + interconnector_labels)

    if selected_ic_label != "Custom/Other":
        # Find the selected interconnector details
        selected_ic = next(ic for ic in interconnectors_data if f"{ic['name']} ({ic['from']} → {ic['to']})" == selected_ic_label)
        country_from = selected_ic["from"]
        country_to = selected_ic["to"]
        interconnector = selected_ic["name"]
        lat, lon = selected_ic["lat"], selected_ic["lon"]
        st.text_input("From Country", value=country_from, disabled=True)
        st.text_input("To Country", value=country_to, disabled=True)
        st.text_input("Latitude", value=str(lat), disabled=True)
        st.text_input("Longitude", value=str(lon), disabled=True)
    else:
        # Restrict country options to known ones (no typos)
        country_from = st.selectbox("From Country", countries)
        country_to = st.selectbox("To Country", countries)
        interconnector = st.text_input("Interconnector")
        lat = st.number_input("Latitude", value=47.0, format="%.6f")
        lon = st.number_input("Longitude", value=20.0, format="%.6f")

    date = st.date_input("Date", datetime.today())
    info = st.text_area("Info")

    submitted = st.form_submit_button("Save")
    if submitted:
        # Prevent duplicate ID on save (for manual mode)
        if id_mode == "Manual" and not df.empty and (df['ID'] == id_val).any():
            st.error("Duplicate ID! Entry not saved.")
            st.stop()
        new_row = {
            "ID": id_val,
            "Country": country_from,
            "Interconnector": interconnector,
            "Date": date.strftime("%Y-%m-%d"),
            "Info": info,
            "Lat": lat,
            "Lon": lon
        }
        exists = not df.empty and (df['ID'] == new_row["ID"]).any()
        with st.spinner("Saving data to Google Sheets..."):
            if exists:
                df.loc[df['ID'] == new_row["ID"], :] = pd.Series(new_row)
            else:
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
        st.success("Information saved to Google Sheet!")
        st.rerun()
        
# --- Data Download ---
st.header("Download Data")
to_download = BytesIO()
df.to_excel(to_download, index=False)
to_download.seek(0)
st.download_button("Download Excel", to_download, file_name="interconnectors_data.xlsx")

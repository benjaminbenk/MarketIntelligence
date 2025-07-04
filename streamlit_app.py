import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO
import json

# --- Google Sheets Setup ---
SHEET_NAME = "MarketIntelligenceGAS"
HISTORY_SHEET_NAME = "History"
EXCEL_LINK = "https://docs.google.com/spreadsheets/d/12jH5gmwMopM9j5uTWOtc6wEafscgf5SvT8gDmoAFawE/edit?gid=0#gid=0"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gs_client():
    gcp_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(gcp_info, scopes=SCOPES)
    return gspread.authorize(credentials)

def get_gs_sheet(sheet_name=SHEET_NAME):
    gc = get_gs_client()
    return gc.open(SHEET_NAME).worksheet(sheet_name)

def load_data():
    with st.spinner("Loading data from Google Sheets..."):
        sheet = get_gs_sheet()
        df = pd.DataFrame(sheet.get_all_records())
        if "Comments" not in df.columns:
            df["Comments"] = ""
        if "Created By" not in df.columns:
            df["Created By"] = ""
        return df

def save_data(df):
    with st.spinner("Saving data to Google Sheets..."):
        sheet = get_gs_sheet()
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())

def append_history(action, row_data, old_data=None, comment=None, username=None):
    history_sheet = get_gs_sheet(HISTORY_SHEET_NAME)
    record = {
        "Timestamp": datetime.utcnow().isoformat(),
        "Action": action,
        "ID": row_data.get("ID", ""),
        "Interconnector": row_data.get("Interconnector", ""),
        "Data": json.dumps(row_data),
        "Old Data": json.dumps(old_data) if old_data else "",
        "Comment": comment or "",
        "User": username or st.session_state.get("username", "anonymous")
    }
    history_sheet.append_row(list(record.values()))

def get_history_for_interconnector(interconnector):
    try:
        history_sheet = get_gs_sheet(HISTORY_SHEET_NAME)
        rows = history_sheet.get_all_records()
        return [row for row in rows if row["Interconnector"] == interconnector]
    except Exception:
        return []

# --- Interconnector endpoints (static for lines on map) ---
interconnectors_data = [
    {"name": "Turkey-Bulgaria", "from": "Turkey", "to": "Bulgaria", "lat": 41.88, "lon": 26.3},
    {"name": "Bulgaria-Romania", "from": "Bulgaria", "to": "Romania", "lat": 44.03, "lon": 27.23},
    {"name": "Bulgaria-Serbia", "from": "Bulgaria", "to": "Serbia", "lat": 43.87, "lon": 22.63},
    {"name": "Greece-Bulgaria", "from": "Greece", "to": "Bulgaria", "lat": 41.3, "lon": 23.15},
    {"name": "Kiskundorozsma", "from": "Serbia", "to": "Hungary", "lat": 46.22, "lon": 19.91},
    {"name": "Serbia-Romania", "from": "Serbia", "to": "Romania", "lat": 45.16, "lon": 21.3},
    {"name": "Drávaszerdahely", "from": "Croatia", "to": "Hungary", "lat": 45.78, "lon": 17.77},
    {"name": "Croatia-Slovenia", "from": "Croatia", "to": "Slovenia", "lat": 45.7, "lon": 15.63},
    {"name": "Mosonmagyaróvár", "from": "Austria", "to": "Hungary", "lat": 47.95, "lon": 16.68},
    {"name": "Austria-Slovakia", "from": "Austria", "to": "Slovakia", "lat": 48.12, "lon": 17.02},
    {"name": "Balassagyarmat", "from": "Hungary", "to": "Slovakia", "lat": 48.07, "lon": 19.31},
    {"name": "Csanádpalota", "from": "Hungary", "to": "Romania", "lat": 46.3, "lon": 21.3},
    {"name": "Bereg", "from": "Hungary", "to": "Ukraine", "lat": 48.2, "lon": 22.6},
    {"name": "Romania-Moldova", "from": "Romania", "to": "Moldova", "lat": 47.21, "lon": 27.54},
    {"name": "Romania-Ukraine", "from": "Romania", "to": "Ukraine", "lat": 45.18, "lon": 28.29},
    {"name": "Slovakia-Ukraine", "from": "Slovakia", "to": "Ukraine", "lat": 48.65, "lon": 22.18}
]


# --- App UI ---
st.set_page_config(page_title="Gas Map", layout="centered")
st.title("🗺️ CEE Gas Market Intelligence Map")

# --- Button for Sheet Link & Backup ---
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
    "Turkey": [39.9208, 32.8541],       # Ankara
    "Bulgaria": [42.6975, 23.3242],     # Sofia
    "Romania": [44.4268, 26.1025],      # Bucharest
    "Greece": [37.9838, 23.7275],       # Athens
    "Serbia": [44.7866, 20.4489],       # Belgrade
    "Hungary": [47.4979, 19.0402],      # Budapest
    "Croatia": [45.8150, 15.9819],      # Zagreb
    "Slovenia": [46.0569, 14.5058],     # Ljubljana
    "Austria": [48.2082, 16.3738],      # Vienna
    "Slovakia": [48.1486, 17.1077],     # Bratislava
    "Ukraine": [50.4501, 30.5234],      # Kyiv
    "Moldova": [47.0105, 28.8638]       # Chișinău
}


# --- Filtering & Search ---
countries = sorted(middle_points.keys())
interconnectors = sorted(df['Interconnector'].dropna().unique()) if not df.empty else []
search_query = st.sidebar.text_input("🔍 Search info/comments")
selected_country = st.sidebar.multiselect("Country", countries, default=countries)
selected_interconnector = st.sidebar.multiselect("Interconnector", interconnectors, default=interconnectors)
min_date = pd.to_datetime(df['Date']).min() if not df.empty else datetime(2000,1,1)
max_date = pd.to_datetime(df['Date']).max() if not df.empty else datetime.today()
date_range = st.sidebar.date_input("Date range", [min_date, max_date])

interconnector_labels = [
    f"{ic['name']} ({ic['from']} → {ic['to']})" for ic in interconnectors_data
]
selected_ic_label = st.sidebar.selectbox("Highlight Static Interconnector", ["None"] + interconnector_labels)
highlight_ic = None
if selected_ic_label != "None":
    highlight_ic = next(ic for ic in interconnectors_data if f"{ic['name']} ({ic['from']} → {ic['to']})" == selected_ic_label)

filtered_df = df.copy()
if not df.empty:
    filtered_df = filtered_df[
        (filtered_df['Country'].isin(selected_country)) &
        (filtered_df['Interconnector'].isin(selected_interconnector)) &
        (pd.to_datetime(filtered_df['Date']) >= pd.to_datetime(date_range[0])) &
        (pd.to_datetime(filtered_df['Date']) <= pd.to_datetime(date_range[1]))
    ]
    if search_query:
        filtered_df = filtered_df[
            filtered_df["Info"].str.contains(search_query, case=False, na=False) |
            filtered_df["Comments"].str.contains(search_query, case=False, na=False)
        ]

# --- Map Visualization (mobile/tablet optimized) ---
m = folium.Map(location=[47, 20], zoom_start=5, tiles="CartoDB Positron")
dynamic_cluster = MarkerCluster(name="Dynamic Entries").add_to(m)
for _, row in filtered_df.iterrows():
    popup_html = f"""
    <table style='font-size:90%;'>
      <tr><th>Country</th><td>{row['Country']}</td></tr>
      <tr><th>Interconnector</th><td>{row['Interconnector']}</td></tr>
      <tr><th>Date</th><td>{row['Date']}</td></tr>
      <tr><th>Info</th><td>{row['Info']}</td></tr>
      <tr><th>Comment</th><td>{row.get('Comments','')}</td></tr>
      <tr><th>Created By</th><td>{row.get('Created By','')}</td></tr>
      <tr><th>Lat/Lon</th><td>{row['Lat']:.4f}, {row['Lon']:.4f}</td></tr>
    </table>
    """
    folium.Marker(
        location=[row["Lat"], row["Lon"]],
        tooltip=f"{row['Interconnector']} ({row['Country']})",
        popup=folium.Popup(popup_html, max_width=320),
        icon=folium.Icon(color="red", icon="landmark")
    ).add_to(dynamic_cluster)
static_cluster = MarkerCluster(name="Static Interconnectors").add_to(m)
for ic in interconnectors_data:
    from_mid = middle_points.get(ic["from"])
    to_mid = middle_points.get(ic["to"])
    is_highlight = (highlight_ic is not None and ic['name'] == highlight_ic['name'])
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
for country, coords in middle_points.items():
    folium.CircleMarker(
        location=coords,
        radius=2,
        color="black",
        fill=True,
        fill_opacity=0.8,
        popup=country
    ).add_to(m)
st_data = st_folium(m, width=None, height=400)

# --- Editable Table / Add/Edit/Delete/Comment Info ---
st.header("Add, Edit, Delete or Comment on Interconnector Info")
username = st.session_state.get("username", "benjaminbenk")
action_mode = st.radio("Mode", ["Add New", "Edit Existing", "Delete", "Add Comment/Annotation"])
if action_mode == "Add New":
    with st.form("add_edit_form", clear_on_submit=True):
        id_mode = st.radio("ID assignment", ["Auto", "Manual"], horizontal=True)
        if id_mode == "Manual":
            id_val = st.number_input(
                "ID (choose a unique number)", 
                value=int(df['ID'].max()+1) if not df.empty else 1, 
                step=1, 
                min_value=1
            )
            if not df.empty and (df['ID'] == id_val).any():
                st.warning("This ID already exists! Please choose a unique number or select Auto.")
        else:
            id_val = int(df['ID'].max()+1) if not df.empty else 1

        # --- Select 1 country of interest ---
        selected_country = st.selectbox("Select Country (to see related interconnectors)", countries)

        # --- Filter all interconnectors that involve the selected country ---
        filtered_ics = [
            ic for ic in interconnectors_data
            if selected_country in (ic['from'], ic['to'])
        ]
        interconnector_labels = [
            f"{ic['name']} ({ic['from']} → {ic['to']})" for ic in filtered_ics
        ]
        selected_ic_label = st.selectbox("Interconnector", ["Custom/Other"] + interconnector_labels)

        if selected_ic_label != "Custom/Other":
            selected_ic = next(ic for ic in filtered_ics if f"{ic['name']} ({ic['from']} → {ic['to']})" == selected_ic_label)
            interconnector = selected_ic["name"]
            country_from = selected_ic["from"]
            country_to = selected_ic["to"]
            lat, lon = selected_ic["lat"], selected_ic["lon"]
        else:
            country_from = st.selectbox("From Country", countries)
            country_to = st.selectbox("To Country", [c for c in countries if c != country_from])
            interconnector = st.text_input("Custom Interconnector Name")
            lat, lon = float('nan'), float('nan')

        date = st.date_input("Date", datetime.today())
        info = st.text_area("Info")
        comments = st.text_area("Comments/Annotations")

        submitted = st.form_submit_button("Save")
        if submitted:
            if id_mode == "Manual" and not df.empty and (df['ID'] == id_val).any():
                st.error("Duplicate ID! Entry not saved.")
                st.stop()

            # Prevent user from entering same country for both directions
            if selected_ic_label == "Custom/Other" and country_from == country_to:
                st.error("From Country and To Country cannot be the same.")
                st.stop()

            new_row = {
                "ID": id_val,
                "Country": selected_country,
                "Interconnector": interconnector,
                "Date": date.strftime("%Y-%m-%d"),
                "Info": info,
                "Lat": lat,
                "Lon": lon,
                "Comments": comments,
                "Created By": username
            }

            exists = not df.empty and (df['ID'] == new_row["ID"]).any()
            with st.spinner("Saving data to Google Sheets..."):
                if exists:
                    old_row = df[df['ID'] == new_row["ID"]].iloc[0].to_dict()
                    df.loc[df['ID'] == new_row["ID"], :] = pd.Series(new_row)
                    append_history("edit", new_row, old_row=old_row, username=username)
                else:
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    append_history("create", new_row, username=username)
                save_data(df)
            st.success("Information saved to Google Sheet!")
            st.rerun()

elif action_mode == "Edit Existing":
    if df.empty:
        st.info("No data to edit.")
    else:
        editable_row = st.selectbox("Select entry to edit (by ID)", df["ID"])
        row = df[df["ID"] == editable_row].iloc[0]
        with st.form("edit_existing_form"):
            info = st.text_area("Info", value=row["Info"])
            comments = st.text_area("Comments/Annotations", value=row["Comments"])
            submitted = st.form_submit_button("Update")
            if submitted:
                updated_row = row.copy()
                updated_row["Info"] = info
                updated_row["Comments"] = comments
                df.loc[df["ID"] == editable_row, ["Info", "Comments"]] = info, comments
                append_history("edit", updated_row.to_dict(), old_data=row.to_dict(), username=username)
                save_data(df)
                st.success("Entry updated.")
                st.rerun()
elif action_mode == "Delete":
    if df.empty:
        st.info("No data to delete.")
    else:
        delete_row_id = st.selectbox("Select entry to delete (by ID)", df["ID"])
        row = df[df["ID"] == delete_row_id].iloc[0]
        st.warning(f"Are you sure you want to delete entry ID {delete_row_id}? This action cannot be undone.")
        if st.button("Confirm Delete"):
            append_history("delete", {}, old_data=row.to_dict(), username=username)
            df = df[df["ID"] != delete_row_id]
            save_data(df)
            st.success(f"Entry {delete_row_id} deleted.")
            st.rerun()
elif action_mode == "Add Comment/Annotation":
    if df.empty:
        st.info("No entries to comment on.")
    else:
        comment_row_id = st.selectbox("Select entry to comment/annotate (by ID)", df["ID"])
        row = df[df["ID"] == comment_row_id].iloc[0]
        new_comment = st.text_area("Add your comment/annotation here")
        if st.button("Add Comment"):
            updated_comments = (row["Comments"] or "") + f"\n[{datetime.utcnow().isoformat()} by {username}]: {new_comment}"
            df.loc[df["ID"] == comment_row_id, "Comments"] = updated_comments
            append_history("comment", row.to_dict(), comment=new_comment, username=username)
            save_data(df)
            st.success("Comment/annotation added.")
            st.rerun()

# --- Show Change Log / History for Interconnector ---
st.header("Change Log / History for Interconnector")
if len(interconnectors) > 0:
    selected_log_ic = st.selectbox("Select interconnector to view history", interconnectors)
    history = get_history_for_interconnector(selected_log_ic)
    if history:
        for h in history:
            with st.expander(f"{h['Timestamp']} | {h['Action']} | {h['User']}"):
                st.json(h)
    else:
        st.info("No history found for this interconnector.")

# --- Data Download (Backup) ---
st.header("Download Data Snapshot / Backup")
to_download = BytesIO()
df.to_excel(to_download, index=False)
to_download.seek(0)
st.download_button("Backup Data", to_download, file_name=f"gas_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

# --- Optimize for mobile/tablet ---
st.markdown("""
<style>
@media (max-width: 800px) {
    .block-container {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    .css-1kyxreq {
        width: 100vw !important;
        min-width: 100vw !important;
    }
}
</style>
""", unsafe_allow_html=True)

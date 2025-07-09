# Streamlit App with Decision Tree Logic for Gas Market Intelligence

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO
import json

# --- Google Sheets Setup ---
SHEET_NAME = "MarketIntelligenceGAS"
HISTORY_SHEET_NAME = "History"
EXCEL_LINK = "https://docs.google.com/spreadsheets/d/12jH5gmwMopm9j5uTWOtc6wEafscgf5SvT8gDmoAFawE/edit?gid=0#gid=0"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

REQUIRED_COLUMNS = [
    "Name", "Counterparty", "Country", "Point Type", "Point Name", "Date", "Info", "Tags"
]

COUNTRIES_LIST = [
    "Turkey", "Bulgaria", "Romania", "Greece", "Serbia", "Hungary",
    "Croatia", "Slovenia", "Austria", "Slovakia", "Ukraine", "Moldova"
]

POINT_TYPES = ["Virtual Point", "Crossborder Point", "Storage", "Entire Country"]
VIRTUAL_POINTS = ["MGP", "VTP"]
STORAGE_POINTS = ["Moson", "Szőreg"]
PREDEFINED_TAGS = ["outage", "maintenance", "regulatory", "forecast"]

# --- Functions ---
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
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df

def save_data(df):
    with st.spinner("Saving data to Google Sheets..."):
        sheet = get_gs_sheet()
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())

def append_history(action, row_data, old_data=None, comment=None, name=None):
    history_sheet = get_gs_sheet(HISTORY_SHEET_NAME)
    record = {
        "Timestamp": datetime.utcnow().isoformat(),
        "Action": action,
        "Name": row_data.get("Name", ""),
        "Point Name": row_data.get("Point Name", ""),
        "Data": json.dumps(row_data),
        "Old Data": json.dumps(old_data) if old_data else "",
        "Comment": comment or "",
        "User": name or ""
    }
    history_sheet.append_row(list(record.values()))

# --- UI ---
st.set_page_config(page_title="Gas Market Intelligence", layout="wide")
st.title("CEE Gas Market Intelligence")
st.markdown(
    f'<a href="{EXCEL_LINK}" target="_blank"><button style="background-color:#4CAF50;color:white;padding:10px 20px;border:none;border-radius:4px;cursor:pointer;font-size:16px;">Go to data</button></a>',
    unsafe_allow_html=True
)

try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data from Google Sheets: {e}")
    st.stop()

for col in REQUIRED_COLUMNS:
    if col not in df.columns:
        df[col] = ""

existing_tags = set()
for tags_str in df["Tags"].dropna():
    for tag in [t.strip() for t in tags_str.split(",") if t.strip()]:
        existing_tags.add(tag)
all_tags = sorted(set(PREDEFINED_TAGS + list(existing_tags)))

st.header("Add, Edit, Delete Info")
action_mode = st.radio("Mode", ["Add New", "Edit Existing", "Delete"])

if action_mode == "Add New":
    with st.form("add_form", clear_on_submit=True):
        counterparty = st.text_input("Counterparty")
        point_type = st.selectbox("Network Point Type", POINT_TYPES)

        if point_type == "Crossborder Point":
            point_name = st.text_input("Crossborder Point")
        elif point_type == "Virtual Point":
            point_name = st.selectbox("Virtual Point", VIRTUAL_POINTS + ["Other..."])
            if point_name == "Other...":
                point_name = st.text_input("Enter new Virtual Point")
        elif point_type == "Storage":
            point_name = st.selectbox("Storage Point", STORAGE_POINTS + ["Other..."])
            if point_name == "Other...":
                point_name = st.text_input("Enter new Storage Point")
        else:
            point_name = "Entire Country"

        country = st.selectbox("Country", COUNTRIES_LIST)
        date = st.date_input("Date", datetime.today())
        info = st.text_area("Info")
        selected_tags = st.multiselect("Select existing tags", options=all_tags)
        custom_tags = st.text_input("Or add custom tags (comma separated)")
        all_selected_tags = selected_tags + [t.strip() for t in custom_tags.split(",") if t.strip()]
        tags_value = ", ".join(sorted(set(all_selected_tags)))
        name = st.text_input("Name (who did the change)")

        submitted = st.form_submit_button("Save")
        if submitted:
            if not name or not country or not point_name or not info:
                st.error("Please complete all required fields (Name, Country, Point Name, Info).")
                st.stop()
            if not df.empty and (df['Name'] == name).any():
                st.error("This Name already exists! Please choose a unique Name.")
                st.stop()

            new_row = {
                "Name": name,
                "Counterparty": counterparty,
                "Country": country,
                "Point Type": point_type,
                "Point Name": point_name,
                "Date": date.strftime("%Y-%m-%d"),
                "Info": info,
                "Tags": tags_value
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            append_history("create", new_row, name=name)
            save_data(df)
            st.success("Information saved to Google Sheet!")
            st.rerun()


# --- Data Download (Backup) ---
st.header("Download Data Snapshot / Backup")
to_download = BytesIO()
df.to_excel(to_download, index=False)
to_download.seek(0)
st.download_button("Backup Data", to_download, file_name=f"gas_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

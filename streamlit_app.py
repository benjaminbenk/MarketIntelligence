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
    "Name", "Counterparty", "Country", "Interconnector", "Date", "Info", "Tags"
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
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = ""
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
        "Name": row_data.get("Name", ""),
        "Interconnector": row_data.get("Interconnector", ""),
        "Data": json.dumps(row_data),
        "Old Data": json.dumps(old_data) if old_data else "",
        "Comment": comment or "",
        "User": username or ""
    }
    history_sheet.append_row(list(record.values()))

def get_history_for_interconnector(interconnector):
    try:
        history_sheet = get_gs_sheet(HISTORY_SHEET_NAME)
        rows = history_sheet.get_all_records()
        return [row for row in rows if row["Interconnector"] == interconnector]
    except Exception:
        return []

# --- App UI ---
st.set_page_config(page_title="Gas Market Intelligence", layout="wide")
st.title("CEE Gas Market Intelligence")

# --- Button for Sheet Link & Backup ---
st.markdown(
    f'<a href="{EXCEL_LINK}" target="_blank"><button style="background-color:#4CAF50;color:white;padding:10px 20px;border:none;border-radius:4px;cursor:pointer;font-size:16px;">Go to data</button></a>',
    unsafe_allow_html=True
)

# --- Load Data ---
try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data from Google Sheets: {e}")
    st.stop()

# --- Ensure required columns exist ---
for col in REQUIRED_COLUMNS:
    if col not in df.columns:
        df[col] = ""

# --- Filtering & Search ---
countries = sorted(df['Country'].dropna().unique()) if not df.empty else []
interconnectors = sorted(df['Interconnector'].dropna().unique()) if not df.empty else []
search_query = st.sidebar.text_input("🔍 Search info/tags")
if not df.empty and (df['Date'] != "").any():
    min_date = pd.to_datetime(df[df['Date'] != ""]['Date']).min()
    max_date = pd.to_datetime(df[df['Date'] != ""]['Date']).max()
else:
    min_date = datetime(2000,1,1)
    max_date = datetime.today()
date_range = st.sidebar.date_input("Date range", [min_date, max_date])

selected_country = st.sidebar.multiselect("Country", countries, default=countries)
selected_interconnector = st.sidebar.multiselect("Interconnector", interconnectors, default=interconnectors)

filtered_df = df.copy()
if not df.empty:
    filtered_df = filtered_df[
        (filtered_df['Country'].isin(selected_country)) &
        (filtered_df['Interconnector'].isin(selected_interconnector)) &
        (pd.to_datetime(filtered_df['Date'], errors="coerce") >= pd.to_datetime(date_range[0])) &
        (pd.to_datetime(filtered_df['Date'], errors="coerce") <= pd.to_datetime(date_range[1]))
    ]
    if search_query:
        filtered_df = filtered_df[
            filtered_df["Info"].str.contains(search_query, case=False, na=False) |
            filtered_df["Tags"].str.contains(search_query, case=False, na=False)
        ]

# --- Show Filtered Table ---
st.header("Entries")
if filtered_df.empty:
    st.info("No entries match the filters.")
else:
    st.dataframe(filtered_df.sort_values("Date", ascending=False), use_container_width=True)

# --- Editable Table / Add/Edit/Delete Info ---
st.header("Add, Edit, Delete Info")
action_mode = st.radio("Mode", ["Add New", "Edit Existing", "Delete"])

if action_mode == "Add New":
    with st.form("add_form", clear_on_submit=True):
        # Use Name as identifier, ask user to provide
        name = st.text_input("Name")
        country = st.selectbox("Country", sorted(df['Country'].dropna().unique()) if not df.empty else [])
        related_ics = sorted(df[df['Country'] == country]['Interconnector'].dropna().unique()) if not df.empty and country else []
        interconnector = st.selectbox("Interconnector", related_ics) if related_ics else st.text_input("Interconnector")
        date = st.date_input("Date", datetime.today())
        counterparty = st.text_input("Counterparty")
        info = st.text_area("Info")
        tags = st.text_input("Tags (comma separated)")
        username = st.text_input("Your Name (who did the change)")

        submitted = st.form_submit_button("Save")
        if submitted:
            if not name or not country or not interconnector or not info or not username:
                st.error("Please complete all required fields (Name, Country, Interconnector, Info, Your Name).")
                st.stop()
            # Check for duplicate Name (as unique identifier)
            if not df.empty and (df['Name'] == name).any():
                st.error("This Name already exists! Please choose a unique Name.")
                st.stop()
            new_row = {
                "Name": name,
                "Counterparty": counterparty,
                "Country": country,
                "Interconnector": interconnector,
                "Date": date.strftime("%Y-%m-%d"),
                "Info": info,
                "Tags": tags
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            append_history("create", new_row, username=username)
            save_data(df)
            st.success("Information saved to Google Sheet!")
            st.rerun()

elif action_mode == "Edit Existing":
    if df.empty:
        st.info("No data to edit.")
    else:
        editable_row = st.selectbox("Select entry to edit (by Name)", df["Name"])
        row = df[df["Name"] == editable_row].iloc[0]
        with st.form("edit_form"):
            country = st.selectbox("Country", sorted(df['Country'].dropna().unique()), index=sorted(df['Country'].dropna().unique()).index(row["Country"]) if row["Country"] in list(sorted(df['Country'].dropna().unique())) else 0)
            related_ics = sorted(df[df['Country'] == country]['Interconnector'].dropna().unique()) if not df.empty and country else []
            interconnector = st.selectbox("Interconnector", related_ics, index=related_ics.index(row["Interconnector"]) if row["Interconnector"] in related_ics else 0) if related_ics else st.text_input("Interconnector", value=row["Interconnector"])
            date = st.date_input("Date", pd.to_datetime(row["Date"], errors="coerce") if row["Date"] else datetime.today())
            counterparty = st.text_input("Counterparty", value=row["Counterparty"])
            info = st.text_area("Info", value=row["Info"])
            tags = st.text_input("Tags (comma separated)", value=row["Tags"])
            username = st.text_input("Your Name (who did the change)")
            submitted = st.form_submit_button("Update")
            if submitted:
                if not username:
                    st.error("Please enter your name for the change.")
                    st.stop()
                updated_row = {
                    "Name": editable_row,
                    "Counterparty": counterparty,
                    "Country": country,
                    "Interconnector": interconnector,
                    "Date": date.strftime("%Y-%m-%d"),
                    "Info": info,
                    "Tags": tags
                }
                old_row = row.to_dict()
                for key in updated_row:
                    df.loc[df["Name"] == editable_row, key] = updated_row[key]
                append_history("edit", updated_row, old_data=old_row, username=username)
                save_data(df)
                st.success("Entry updated.")
                st.rerun()

elif action_mode == "Delete":
    if df.empty:
        st.info("No data to delete.")
    else:
        delete_row_name = st.selectbox("Select entry to delete (by Name)", df["Name"])
        row = df[df["Name"] == delete_row_name].iloc[0]
        username = st.text_input("Your Name (who did the change)")
        st.warning(f"Are you sure you want to delete entry Name '{delete_row_name}'? This action cannot be undone.")
        if st.button("Confirm Delete"):
            if not username:
                st.error("Please enter your name for the change.")
                st.stop()
            append_history("delete", row.to_dict(), username=username)
            df = df[df["Name"] != delete_row_name]
            save_data(df)
            st.success(f"Entry '{delete_row_name}' deleted.")
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

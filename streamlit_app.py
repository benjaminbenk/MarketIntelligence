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
        for col in ["Comments", "Created By", "Tags"]:
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

# --- Filtering & Search ---
countries = sorted(df['Country'].dropna().unique()) if not df.empty else []
interconnectors = sorted(df['Interconnector'].dropna().unique()) if not df.empty else []
search_query = st.sidebar.text_input("🔍 Search info/comments")
selected_country = st.sidebar.multiselect("Country", countries, default=countries)
selected_interconnector = st.sidebar.multiselect("Interconnector", interconnectors, default=interconnectors)
min_date = pd.to_datetime(df['Date']).min() if not df.empty else datetime(2000,1,1)
max_date = pd.to_datetime(df['Date']).max() if not df.empty else datetime.today()
date_range = st.sidebar.date_input("Date range", [min_date, max_date])

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

# --- Show Filtered Table ---
st.header("Entries")
if filtered_df.empty:
    st.info("No entries match the filters.")
else:
    st.dataframe(filtered_df.sort_values("Date", ascending=False), use_container_width=True)

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

        country_options = sorted(df['Country'].dropna().unique()) if not df.empty else []
        selected_country = st.selectbox("Select Country", country_options)
        related_ics = sorted(df[df['Country'] == selected_country]['Interconnector'].dropna().unique()) if not df.empty else []

        if related_ics:
            interconnector = st.selectbox("Interconnector", related_ics)
        else:
            st.info("No interconnectors available for this country.")
            interconnector = None

        date = st.date_input("Date", datetime.today())
        info = st.text_area("Info")
        comments = st.text_area("Comments/Annotations")

        submitted = st.form_submit_button("Save")
        if submitted:
            if not interconnector:
                st.error("No interconnector selected. Cannot save.")
                st.stop()
            if id_mode == "Manual" and not df.empty and (df['ID'] == id_val).any():
                st.error("Duplicate ID! Entry not saved.")
                st.stop()

            new_row = {
                "ID": id_val,
                "Country": selected_country,
                "Interconnector": interconnector,
                "Date": date.strftime("%Y-%m-%d"),
                "Info": info,
                "Comments": comments,
                "Created By": username
            }

            exists = not df.empty and (df['ID'] == new_row["ID"]).any()
            with st.spinner("Saving data to Google Sheets..."):
                if exists:
                    old_row = df[df['ID'] == new_row["ID"]].iloc[0].to_dict()
                    df.loc[df['ID'] == new_row["ID"], :] = pd.Series(new_row)
                    append_history("edit", new_row, old_data=old_row, username=username)
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

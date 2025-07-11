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
EXCEL_LINK = "https://docs.google.com/spreadsheets/d/12jH5gmwMopM9j5uTWOtc6wEafscgf5SvT8gDmoAFawE/edit?gid=0#gid=0"
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
VIRTUAL_POINTS = ["MGP", "AT-VTP"]
STORAGE_POINTS = ["MMBF", "HEXUM"]
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

def generate_summary(row):
    main_tag = row["Tags"].split(",")[0].strip() if row["Tags"] else "unspecified"
    return f"🔹 {row['Info']} at **{row['Point Name']}** ({row['Point Type']}) from **{row['Counterparty']}** on **{row['Date']}** — tag: _{main_tag}_"


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

# --- Hierarchical Filter Panel ---
st.sidebar.header("🔍 Filter Data")
counterparty_list = sorted(df["Counterparty"].dropna().unique())
selected_counterparty = st.sidebar.selectbox("Select Counterparty", counterparty_list)

filtered_df = df[df["Counterparty"] == selected_counterparty]

point_types = filtered_df["Point Type"].dropna().unique().tolist()
selected_point_type = st.sidebar.selectbox("Select Point Type", ["All"] + point_types)
if selected_point_type != "All":
    filtered_df = filtered_df[filtered_df["Point Type"] == selected_point_type]

point_names = filtered_df["Point Name"].dropna().unique().tolist()
selected_point_name = st.sidebar.selectbox("Select Point Name", ["All"] + point_names)
if selected_point_name != "All":
    filtered_df = filtered_df[filtered_df["Point Name"] == selected_point_name]

tags_available = sorted(set(tag.strip() for tags in filtered_df["Tags"].dropna() for tag in tags.split(",")))
selected_tags = st.sidebar.multiselect("Filter by Tag", options=tags_available)
if selected_tags:
    filtered_df = filtered_df[
        filtered_df["Tags"].apply(lambda x: any(tag in x for tag in selected_tags))
    ]

st.subheader(f"Filtered Results for: {selected_counterparty}")
st.dataframe(filtered_df, use_container_width=True)

group_option = st.selectbox("🗂 Group Summaries By", ["None", "Point Name", "Date"])

if group_option == "None":
    grouped = {"All Entries": filtered_df.itertuples()}
elif group_option == "Point Name":
    grouped = filtered_df.groupby("Point Name")
elif group_option == "Date":
    grouped = filtered_df.groupby("Date")

with st.expander(f"📝 Summary of Entries for {selected_counterparty}"):
    if filtered_df.empty:
        st.info("No entries found for this selection.")
    else:
        for group_key, group_rows in grouped.items() if group_option != "None" else grouped.items():
            with st.expander(f"📍 {group_option}: {group_key}", expanded=True):
                for row in group_rows:
                    with st.chat_message("info"):
                        st.markdown(generate_summary(row))


st.header("Add, Edit, Delete Info")
action_mode = st.radio("Mode", ["Add New", "Edit Existing", "Delete"])

if action_mode == "Add New":
    st.subheader("Add New Entry")

    counterparty = st.text_input("Counterparty")
    point_type = st.selectbox("Network Point Type", POINT_TYPES, key="point_type")

    # --- Dynamic selection of point name based on type ---
    point_name = ""
    if point_type == "Crossborder Point":
        point_name = st.text_input("Crossborder Point Name")
    elif point_type == "Virtual Point":
        selected_vp = st.selectbox("Select Virtual Point", VIRTUAL_POINTS + ["Other..."], key="vp_select")
        if selected_vp == "Other...":
            point_name = st.text_input("Enter new Virtual Point", key="vp_custom")
        else:
            point_name = selected_vp
    elif point_type == "Storage":
        selected_sp = st.selectbox("Select Storage Point", STORAGE_POINTS + ["Other..."], key="sp_select")
        if selected_sp == "Other...":
            point_name = st.text_input("Enter new Storage Point", key="sp_custom")
        else:
            point_name = selected_sp
    else:
        point_name = "Entire Country"

    country = st.selectbox("Country", COUNTRIES_LIST)

    date_mode = st.radio("Select Time Mode", ["Single Day", "Date Range", "Predefined Code"])
    
    if date_mode == "Single Day":
        date = st.date_input("Date", datetime.today())
        date_repr = date.strftime("%Y-%m-%d")
    
    elif date_mode == "Date Range":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.today())
        with col2:
            end_date = st.date_input("End Date", datetime.today())
        date_repr = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    
    else:
        current_year = datetime.today().year
        predefined_options = sorted([
            f"{month.upper()[:3]}{str(year)[-2:]}" for year in range(current_year, current_year + 3) for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ] + [
            f"{str(year)[-2:]}Q{q}" for year in range(current_year, current_year + 3) for q in range(1, 5)
        ] + [
            f"{str(year)[-2:]}WIN" for year in range(current_year, current_year + 3)
        ] + [
            f"{str(year)[-2:]}SUM" for year in range(current_year, current_year + 3)
        ] + [
            f"CAL{str(year)[-2:]}" for year in range(current_year, current_year + 3)
        ] + [
            f"GY{str(year)[-2:]}" for year in range(current_year, current_year + 3)
        ] + [
            f"SY{str(year)[-2:]}" for year in range(current_year, current_year + 3)
        ])
        date_code = st.selectbox("Select Period Code", predefined_options)
        custom_code = st.text_input("Or enter custom period code (e.g. CUSTOM_BLOCK1)", "")
        date_repr = custom_code if custom_code else date_code

    info = st.text_area("Info")
    from rapidfuzz import fuzz, process
    selected_tags = st.multiselect("Select existing tags", options=all_tags)
    custom_input = st.text_input("Or add custom tags (comma separated)")
    typed_tags = [t.strip() for t in custom_input.split(",") if t.strip()]
    # Suggest similar tags for each typed tag
    for tag in typed_tags:
        matches = process.extract(tag, all_tags, scorer=fuzz.ratio, limit=3)
        close_matches = []
    for tag in typed_tags:
        matches = process.extract(tag, all_tags, scorer=fuzz.ratio, limit=3)
        close_matches = [m[0] for m in matches if m[1] > 70]
        if close_matches:
            st.caption(f"Suggestions for '{tag}': {', '.join(close_matches)}")
    all_selected_tags = selected_tags + typed_tags
    tags_value = ", ".join(sorted(set(all_selected_tags)))
    name = st.text_input("Name (who did the change)")

# --- Automatic summary generation function ---
def generate_summary(info, point_name, counterparty, date):
    return f"{info} at {point_name} from {counterparty} for {date}"

if st.button("Save Entry"):
    if not df.empty and ((df['Point Name'] == point_name) & (df['Date'] == date_repr) & (df['Counterparty'] == counterparty)).any():
        st.warning("Looks like this entry already exists.")
        
        summary = generate_summary(info, point_name, counterparty, date_repr)
        st.markdown(f"📝 **Generated Summary:** {summary}")
    
    else:
        new_row = {
            "Name": name,
            "Counterparty": counterparty,
            "Country": country,
            "Point Type": point_type,
            "Point Name": point_name,
            "Date": date_repr,
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

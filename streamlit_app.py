# Streamlit App with Decision Tree Logic for Gas Market Intelligence

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from io import BytesIO
import json
import streamlit.components.v1 as components
from urllib.parse import urlencode

# --- Google Sheets Setup ---
SHEET_NAME = "MarketIntelligenceGAS"
HISTORY_SHEET_NAME = "History"
EXCEL_LINK = "https://docs.google.com/spreadsheets/d/12jH5gmwMopM9j5uTWOtc6wEafscgf5SvT8gDmoAFawE/edit?gid=0#gid=0"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

REQUIRED_COLUMNS = [
    "Timestamp","Name", "Counterparty", "Country", "Point Type", "Point Name", "Date", "Info", "Capacity Value", "Capacity Unit", "Volume Value", "Volume Unit","Tags"
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
        df.columns = df.columns.str.strip()  # ✅ Strip whitespace from column names
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

def generate_summary_row(row):
    tags_value = getattr(row, "Tags", "") if hasattr(row, "Tags") else row.get("Tags", "")
    main_tag = tags_value.split(",")[0].strip() if tags_value else "unspecified"

    point_name = getattr(row, "Point Name", "") if hasattr(row, "Point Name") else row.get("Point Name", "")
    point_type = getattr(row, "Point Type", "") if hasattr(row, "Point Type") else row.get("Point Type", "")
    counterparty = getattr(row, "Counterparty", "") if hasattr(row, "Counterparty") else row.get("Counterparty", "")
    date = getattr(row, "Date", "") if hasattr(row, "Date") else row.get("Date", "")
    info = getattr(row, "Info", "") if hasattr(row, "Info") else row.get("Info", "")
    name = getattr(row, "Name", "") if hasattr(row, "Name") else row.get("Name", "")
    timestamp = getattr(row, "Timestamp", "") if hasattr(row, "Timestamp") else row.get("Timestamp", "")
    return f"🕒 {timestamp} — {info} at **{point_name}** ({point_type}) from **{counterparty}** on **{date}** — source: _{name}_"

def clear_all_filters():
    for key in [
        "selected_counterparty",
        "selected_point_type",
        "selected_point_name",
        "selected_tags",
        "unified_search",
        "show_entry_modal",
        "modal_row"
    ]:
        st.session_state.pop(key, None)

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

params = st.query_params
if params.get("close_modal") == ["1"]:
    st.session_state.show_entry_modal = False
    # strip close_modal from the URL, keep other filters
    new_params = {k: v for k, v in params.items() if k != "close_modal"}
    # flatten lists for urlencode
    flat = {k: (v if isinstance(v, str) else v[0]) for k, v in new_params.items()}
    st.set_query_params(**flat)

# --- Hierarchical Filter Panel ---
st.sidebar.header("🔍 Filter Data")

# Counterparty Filter
counterparty_list = sorted(df["Counterparty"].dropna().unique().tolist())
selected_counterparty = st.sidebar.selectbox(
    "Select Counterparty",
    ["All"] + counterparty_list,
    key="selected_counterparty"
)

# Point Type Filter
# (apply the counterparty filter first so the list updates)
filtered_df = df.copy()
if st.session_state.selected_counterparty != "All":
    filtered_df = filtered_df[filtered_df["Counterparty"] == st.session_state.selected_counterparty]

point_types = sorted(filtered_df["Point Type"].dropna().unique().tolist())
selected_point_type = st.sidebar.selectbox(
    "Select Point Type",
    ["All"] + point_types,
    key="selected_point_type"
)
if st.session_state.selected_point_type != "All":
    filtered_df = filtered_df[filtered_df["Point Type"] == st.session_state.selected_point_type]

# Point Name Filter
point_names = sorted(filtered_df["Point Name"].dropna().unique().tolist())
selected_point_name = st.sidebar.selectbox(
    "Select Point Name",
    ["All"] + point_names,
    key="selected_point_name"
)
if st.session_state.selected_point_name != "All":
    filtered_df = filtered_df[filtered_df["Point Name"] == st.session_state.selected_point_name]

# Tags Filter
tags_available = sorted({
    tag.strip()
    for tags in filtered_df["Tags"].dropna()
    for tag in tags.split(",")
})
selected_tags = st.sidebar.multiselect(
    "Filter by Tag",
    options=tags_available,
    key="selected_tags"
)
if st.session_state.selected_tags:
    filtered_df = filtered_df[
        filtered_df["Tags"].apply(lambda x: any(tag in x for tag in st.session_state.selected_tags))
    ]

# --- Time Horizon Filter ---
time_horizon_input = st.sidebar.text_input("Search Date / Period (exact or partial match)", key="time_horizon_input")
if time_horizon_input:
    filtered_df = filtered_df[
        filtered_df["Date"].astype(str).str.contains(time_horizon_input.strip(), case=False, na=False)
    ]

# Universal Search Box
unified_search = st.sidebar.text_input(
    "Search All Fields",
    key="unified_search"
)
if st.session_state.unified_search:
    search_lower = st.session_state.unified_search.lower()

    def row_matches_any_field(row):
        fields = [
            str(row.get("Info","")),
            str(row.get("Country","")),
            str(row.get("Point Name","")),
            str(row.get("Point Type","")),
            str(row.get("Counterparty","")),
            str(row.get("Date","")),
            str(row.get("Tags",""))
        ]
        return any(search_lower in field.lower() for field in fields)

    filtered_df = filtered_df[filtered_df.apply(row_matches_any_field, axis=1)]

st.sidebar.button(
    "Clear Selection",
    on_click=clear_all_filters
)

# --- Sorting Options ---
st.sidebar.header("↕️ Sort Options")
sort_column = st.sidebar.selectbox("Sort by Column", options=filtered_df.columns.tolist())
sort_order = st.sidebar.radio("Sort Order", ["Ascending", "Descending"], horizontal=True)

# Apply sorting
filtered_df = filtered_df.sort_values(
    by=sort_column,
    ascending=(sort_order == "Ascending"),
    na_position="last"
)


st.subheader(f"Filtered Results for: {selected_counterparty}")
    
if st.session_state.get("show_entry_modal", False):
    row = st.session_state.modal_row

    # build close_href that keeps existing filters + close_modal=1
    close_params = {**st.query_params, "close_modal": "1"}
    flat_close = {k: (v if isinstance(v, str) else v[0]) for k, v in close_params.items()}
    close_href = "?" + urlencode(flat_close)

    modal_html = f"""
    <style>
      .modal-overlay {{
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.6);
        z-index: 9998;
      }}
      .modal-content {{
        position: fixed;
        top: 10%;
        left: 50%;
        transform: translateX(-50%);
        background: #fff;
        color: black;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        max-width: 500px; width: 90%;
        z-index: 9999;
      }}
      .modal-content h3 {{ margin-top: 0; }}
      .modal-content p {{ margin: 0.5rem 0; }}
      .modal-close {{
        display: inline-block;
        margin-top: 1rem;
        padding: 0.5rem 1rem;
        background: #eee;
        border-radius: 4px;
        color: black;
        text-decoration: none;
        font-weight: bold;
      }}
    </style>

    <div class="modal-overlay"></div>
    <div class="modal-content">
      <h3>🔎 Information Details – {row.get('Point Name','N/A')}</h3>
      <p><strong>Timestamp:</strong> {row.get('Timestamp','N/A')}</p>
      <p><strong>Counterparty:</strong> {row.get('Counterparty','N/A')}</p>
      <p><strong>Time Horizon:</strong> {row.get('Date','N/A')}</p>
      <p><strong>Country:</strong> {row.get('Country','N/A')}</p>
      <p><strong>Info:</strong> {row.get('Info','N/A')}</p>
      <p><strong>Capacity:</strong> {row.get('Capacity Value','N/A')} {row.get('Capacity Unit','')}</p>
      <p><strong>Volume:</strong> {row.get('Volume Value','N/A')} {row.get('Volume Unit','')}</p>
      <p><strong>Source:</strong> {row.get('Name','N/A')}</p>
      <!-- real link that reloads with close_modal=1 -->
      <a href="{close_href}" class="modal-close" target="_top">
          X
      </a>
    </div>
    """

    st.markdown(modal_html, unsafe_allow_html=True)
    
with st.expander(f"📊 Interactive Summary Table for {selected_counterparty}", expanded=True):
    if filtered_df.empty:
        st.info("No entries found for this selection.")
    else:
        all_columns = list(filtered_df.columns)

        selected_cols = st.multiselect(
            "Select columns to show",
            options=["All"] + all_columns,
            default=REQUIRED_COLUMNS
        )

        # ✅ NEVER use selected_cols directly – sanitize first
        if "All" in selected_cols:
            cols_to_display = all_columns
        else:
            # Filter out any unknown columns
            cols_to_display = [col for col in selected_cols if col in all_columns]

        # Fallback to prevent KeyError
        if not cols_to_display:
            st.warning("No valid columns selected. Showing all columns.")
            cols_to_display = all_columns

        # ✅ Use sanitized column list
        display_df = filtered_df[cols_to_display].copy()

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

                    
st.header("Add, Edit, Delete Info")
action_mode = st.radio("Mode", ["Add New", "Edit Existing", "Delete"])

if action_mode == "Add New":
    st.subheader("Add New Entry")

    name = st.text_input("Name (who did the change)")
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

   # --- Optional Capacity Input ---
    use_capacity = st.checkbox("Add Capacity?", value=False)
    if use_capacity:
        col1, col2 = st.columns([2, 1])
        with col1:
            capacity_value = st.number_input("Capacity", key="capacity_value_input")
        with col2:
            capacity_unit = st.selectbox("Capacity Unit", ["kWh/h", "MWh/h", "GWh/h", "m³/h"], key="capacity_unit_input")
    else:
        capacity_value = ""
        capacity_unit = ""
    
    # --- Optional Volume Input ---
    use_volume = st.checkbox("Add Volume?", value=False)
    if use_volume:
        col3, col4 = st.columns([2, 1])
        with col3:
            volume_value = st.number_input("Volume", key="volume_value_input")
        with col4:
            volume_unit = st.selectbox("Volume Unit", ["MW", "MWh", "GW", "GWh"], key="volume_unit_input")
    else:
        volume_value = ""
        volume_unit = ""


    all_selected_tags = selected_tags + typed_tags
    tags_value = ", ".join(sorted(set(all_selected_tags)))

# --- Automatic summary generation function ---
def generate_summary(info, point_name, counterparty, date):
    return f"{info} at {point_name} from {counterparty} for {date}"

if st.button("Save Entry"):
    if not df.empty and ((df['Point Name'] == point_name) & (df['Date'] == date_repr) & (df['Counterparty'] == counterparty)).any():
        st.warning("Looks like this entry already exists.")
        
        summary = generate_summary(info, point_name, counterparty, date_repr)
        st.markdown(f"**Generated Summary:** {summary}")
    
    else:
        new_row = {
            "Timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "Name": name,
            "Counterparty": counterparty,
            "Country": country,
            "Point Type": point_type,
            "Point Name": point_name,
            "Date": date_repr,
            "Info": info,
            "Capacity Value": capacity_value,
            "Capacity Unit": capacity_unit,
            "Volume Value": volume_value,
            "Volume Unit": volume_unit,
            "Tags": tags_value
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        append_history("create", new_row, name=name)
        save_data(df)
        st.success("Information saved to Google Sheet!")
        st.rerun()

elif action_mode == "Edit Existing":
    st.subheader("Edit Existing Entry")

    if df.empty:
        st.warning("No data available to edit.")
    else:
        # Step 1: Select entry
        unique_keys = df.apply(lambda row: f"{row['Counterparty']} | {row['Point Name']} | {row['Date']}", axis=1)
        selected_key = st.selectbox("Select Entry to Edit", unique_keys)

        # Find matching row
        selected_index = unique_keys[unique_keys == selected_key].index[0]
        row_to_edit = df.loc[selected_index]

        # Step 2: Editable fields (pre-populated)
        new_info = st.text_area("Info", value=row_to_edit["Info"])
        new_country = st.selectbox("Country", COUNTRIES_LIST, index=COUNTRIES_LIST.index(row_to_edit["Country"]))
        new_point_type = st.selectbox("Network Point Type", POINT_TYPES, index=POINT_TYPES.index(row_to_edit["Point Type"]))

        # Point Name (conditional logic based on Point Type)
        if new_point_type == "Crossborder Point":
            new_point_name = st.text_input("Crossborder Point Name", value=row_to_edit["Point Name"])
        elif new_point_type == "Virtual Point":
            selected_vp = st.selectbox("Select Virtual Point", VIRTUAL_POINTS + ["Other..."], index=VIRTUAL_POINTS.index(row_to_edit["Point Name"]) if row_to_edit["Point Name"] in VIRTUAL_POINTS else len(VIRTUAL_POINTS))
            new_point_name = st.text_input("Enter new Virtual Point") if selected_vp == "Other..." else selected_vp
        elif new_point_type == "Storage":
            selected_sp = st.selectbox("Select Storage Point", STORAGE_POINTS + ["Other..."], index=STORAGE_POINTS.index(row_to_edit["Point Name"]) if row_to_edit["Point Name"] in STORAGE_POINTS else len(STORAGE_POINTS))
            new_point_name = st.text_input("Enter new Storage Point") if selected_sp == "Other..." else selected_sp
        else:
            new_point_name = "Entire Country"

        new_date = st.text_input("Date", value=row_to_edit["Date"])
        new_counterparty = st.text_input("Counterparty", value=row_to_edit["Counterparty"])

       # Safely coerce the old values, defaulting to 0.0 if they’re non‑numeric
        raw_capacity = row_to_edit.get("Capacity Value", "")
        try:
            initial_capacity = float(raw_capacity)
        except (ValueError, TypeError):
            initial_capacity = 0.0
    
        raw_volume = row_to_edit.get("Volume Value", "")
        try:
            initial_volume = float(raw_volume)
        except (ValueError, TypeError):
            initial_volume = 0.0
    
        # --- Capacity (no min/max/step restrictions) ---
        col1, col2 = st.columns([2, 1])
        with col1:
            new_capacity_value = st.number_input(
                "Capacity",
                value=initial_capacity,
                format="%.3f",        # optional: control decimal places
                key="new_capacity_value"
            )
        with col2:
            unit_options = ["kWh/h", "MWh/h", "GWh/h", "m³/h"]
            old_cap_unit = row_to_edit.get("Capacity Unit", "")
            default_idx = unit_options.index(old_cap_unit) if old_cap_unit in unit_options else 0
            new_capacity_unit = st.selectbox(
                "Unit",
                unit_options,
                index=default_idx,
                key="new_capacity_unit"
            )
    
        # --- Volume (no min/max/step restrictions) ---
        col3, col4 = st.columns([2, 1])
        with col3:
            new_volume_value = st.number_input(
                "Volume",
                value=initial_volume,
                format="%.3f",
                key="new_volume_value"
            )
        with col4:
            vol_options = ["MW", "MWh", "GW", "GWh"]
            old_vol_unit = row_to_edit.get("Volume Unit", "")
            default_vol_idx = vol_options.index(old_vol_unit) if old_vol_unit in vol_options else 0
            new_volume_unit = st.selectbox(
                "Unit",
                vol_options,
                index=default_vol_idx,
                key="new_volume_unit"
            )

        existing_tag_list = [t.strip() for t in row_to_edit["Tags"].split(",")] if row_to_edit["Tags"] else []
        selected_tags = st.multiselect("Select existing tags", options=all_tags, default=existing_tag_list)
        custom_tag_input = st.text_input("Add custom tags (comma separated)")
        custom_tags = [t.strip() for t in custom_tag_input.split(",") if t.strip()]
        tags_value = ", ".join(sorted(set(selected_tags + custom_tags)))

        name = st.text_input("Name (who did the change)", value=row_to_edit["Name"])

        if st.button("Save Changes"):
            old_row = row_to_edit.to_dict()
            df.at[selected_index, "Info"] = new_info
            df.at[selected_index, "Country"] = new_country
            df.at[selected_index, "Point Type"] = new_point_type
            df.at[selected_index, "Point Name"] = new_point_name
            df.at[selected_index, "Date"] = new_date
            df.at[selected_index, "Counterparty"] = new_counterparty
            df.at[selected_index, "Capacity Value"] = new_capacity_value
            df.at[selected_index, "Capacity Unit"] = new_capacity_unit
            df.at[selected_index, "Volume Value"] = new_volume_value
            df.at[selected_index, "Volume Unit"] = new_volume_unit
            df.at[selected_index, "Tags"] = tags_value
            df.at[selected_index, "Name"] = name

            append_history("edit", df.loc[selected_index].to_dict(), old_data=old_row, name=name)
            save_data(df)
            st.success("Entry updated successfully.")
            st.rerun()

elif action_mode == "Delete":
    st.subheader("Delete Existing Entry")

    if df.empty:
        st.warning("No data available to delete.")
    else:
        # Step 1: Select entry
        unique_keys = df.apply(lambda row: f"{row['Counterparty']} | {row['Point Name']} | {row['Date']}", axis=1)
        selected_key = st.selectbox("Select Entry to Delete", unique_keys)

        # Find the row index to delete
        selected_index = unique_keys[unique_keys == selected_key].index[0]
        row_to_delete = df.loc[selected_index]

        # Step 2: Show confirmation and delete
        with st.expander("Selected Entry Details", expanded=True):
            st.markdown(f"**Original Timestamp:** {row_to_edit.get('Timestamp', 'N/A')}")
            st.markdown(f"**Counterparty**: {row_to_delete['Counterparty']}")
            st.markdown(f"**Point Name**: {row_to_delete['Point Name']}")
            st.markdown(f"**Date**: {row_to_delete['Date']}")
            st.markdown(f"**Point Type**: {row_to_delete['Point Type']}")
            st.markdown(f"**Country**: {row_to_delete['Country']}")
            st.markdown(f"**Info**: {row_to_delete['Info']}")
            st.markdown(f"**Capacity**: {row_to_delete.get('Capacity Value', '')} {row_to_delete.get('Capacity Unit', '')}")
            st.markdown(f"**Volume**: {row_to_delete.get('Volume Value', '')} {row_to_delete.get('Volume Unit', '')}")
            st.markdown(f"**Tags**: {row_to_delete['Tags']}")

        confirm = st.checkbox("Yes, I want to delete this entry.")
        name = st.text_input("Name (who is deleting the entry)")

        if confirm and st.button("Delete Entry"):
            deleted_data = row_to_delete.to_dict()
            df.drop(index=selected_index, inplace=True)
            df.reset_index(drop=True, inplace=True)

            append_history("delete", deleted_data, name=name)
            save_data(df)
            st.success("Entry deleted successfully.")
            st.rerun()


# --- Data Download (Backup) ---
st.header("Download Data Snapshot / Backup")
to_download = BytesIO()
df.to_excel(to_download, index=False)
to_download.seek(0)
st.download_button("Backup Data", to_download, file_name=f"gas_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

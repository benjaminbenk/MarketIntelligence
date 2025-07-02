import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
from io import BytesIO

EXCEL_PATH = https://metenergy-my.sharepoint.com/:x:/r/personal/benjamin_benko_met_com/Documents/MarketIntelligence_GAS.xlsx?d=wc7f0adde05f747bc9f55ff79cfee3662&csf=1&web=1&e=b7k4aP

# Multi-user: get username
username = st.text_input("Your name", value=st.session_state.get("username", "User"))
st.session_state["username"] = username

# Ensure Excel file exists
if not os.path.isfile(EXCEL_PATH):
    pd.DataFrame(columns=[
        "ID", "Country", "Interconnector", "Date", "Info", "Lat", "Lon", "LockedBy", "LastEdited"
    ]).to_excel(EXCEL_PATH, index=False)

# Load data
@st.cache_data(ttl=10)
def load_data():
    return pd.read_excel(EXCEL_PATH)

def save_data(df):
    df.to_excel(EXCEL_PATH, index=False)

df = load_data()

# Data import
uploaded = st.sidebar.file_uploader("Import Excel", type=["xlsx"])
if uploaded:
    df = pd.read_excel(uploaded)
    save_data(df)
    st.success("File imported! Refreshing data...")
    st.experimental_rerun()

# Data export
to_download = BytesIO()
df.to_excel(to_download, index=False)
to_download.seek(0)
st.sidebar.download_button("Download Excel", to_download, file_name="interconnectors_data.xlsx")

# Map and filtering...
# (Same as before—see previous responses for details)

# When marker is clicked, open a modal for editing (pseudo-code)
clicked_id = st.session_state.get("clicked_id")
if clicked_id is not None:
    # Check for lock
    row = df[df['ID'] == clicked_id].iloc[0]
    is_locked = pd.notnull(row.get('LockedBy')) and row['LockedBy'] != username
    with st.modal(f"Edit: {row['Country']} - {row['Interconnector']}"):
        if is_locked:
            st.warning(f"Locked by {row['LockedBy']}. You can only view, not edit.")
        # Show editable fields...
        if not is_locked:
            # On submit: update row, set LockedBy to username, update LastEdited
            pass  # Save logic here

# To lock, update 'LockedBy', to unlock, clear 'LockedBy' after save.

# For cloud Excel integration:
# - Use msal to authenticate
# - Use requests or the Microsoft Graph API Python SDK to read/write your Excel file on OneDrive/SharePoint

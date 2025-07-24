import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from datetime import datetime

# Connect to Google Sheet
gc = gspread.service_account(filename='credentials.json')
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1luzRe9um2-RVWCvChbzQI91LZm1oq_yc2d08gaOuYBg/edit")
worksheet = sheet.worksheet("For Dashboard")



# --- Function to format time ---
def format_timedelta(td):
    if pd.isnull(td):
        return "00:00:00.00"
    total_seconds = td.total_seconds()
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02}:{int(minutes):02}:{seconds:05.2f}"

def safe_time_average(series):
    valid = series[(series.notna()) & (series.dt.total_seconds() > 0)]
    return format_timedelta(valid.mean()) if not valid.empty else "00:00:00.00"

@st.cache_data(ttl=600)
def load_data():
    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df = df[~df.applymap(lambda x: isinstance(x, str) and '#REF!' in x)].copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    time_cols = ['Total Kitchen Time', 'Total Pickup Time', 'Total Delivery Time',
                 'Total Rider Return Time', 'Total Cycle Time']
    for col in time_cols:
        df[col] = pd.to_timedelta(df[col].astype(str), errors='coerce')

    df['80/160'] = pd.to_numeric(df['80/160'], errors='coerce').fillna(0).astype(int)
    df['Total Amount'] = pd.to_numeric(df['Total Amount'], errors='coerce').fillna(0).astype(int)
    return df, datetime.now()
# Page setup
st.set_page_config(page_title="Rider Delivery Dashboard", layout="wide")
st.sidebar.header("🔍 Search Filters")

if st.sidebar.button("🔄 Reload Sheet"):
    st.cache_data.clear()

df, last_updated = load_data()

# Date Range
start_date, end_date = st.sidebar.date_input("Select Date Range", [df['Date'].min(), df['Date'].max()])

# Rider Filter
rider_options = sorted(df['Rider Name/Code'].dropna().unique())
selected_riders = st.sidebar.multiselect("Select Rider(s)", rider_options, default=rider_options)

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Select All Riders"):
        selected_riders = rider_options
with col2:
    if st.button("Clear All Riders"):
        selected_riders = []

# Invoice Type Filter
invoice_type_options = sorted(df['Invoice Type'].dropna().unique())
selected_invoice_type = st.sidebar.multiselect("Select Invoice Type(s)", invoice_type_options, default=invoice_type_options)

# Shift Type Filter
shift_options = sorted(df['Shift Type'].dropna().unique())
selected_shifts = st.sidebar.multiselect("Select Shift(s)", shift_options, default=shift_options)

# Apply filters with fallbacks
filtered_df = df[
    (df['Date'] >= pd.to_datetime(start_date)) &
    (df['Date'] <= pd.to_datetime(end_date)) &
    (df['Invoice Type'].isin(selected_invoice_type)) &
    ((df['Rider Name/Code'].isin(selected_riders)) if selected_riders else True) &
    ((df['Shift Type'].isin(selected_shifts)) if selected_shifts else True)
]

# --- Consolidated Overview (Unfiltered except by Date & Shift) ---
st.markdown("## 📦 Consolidated Overview (By Date & Shift)", unsafe_allow_html=True)

if selected_shifts:
    consolidated_df = df[
        (df['Date'] >= pd.to_datetime(start_date)) &
        (df['Date'] <= pd.to_datetime(end_date)) &
        (df['Shift Type'].isin(selected_shifts))
    ]
else:
    consolidated_df = df[
        (df['Date'] >= pd.to_datetime(start_date)) &
        (df['Date'] <= pd.to_datetime(end_date))
    ]

# ✅ Keep only rows with a valid Invoice Number
consolidated_df = consolidated_df[consolidated_df['Invoice Number'].notna()]



consolidated_metrics = {
    "Total Orders": len(consolidated_df),
    "Completed Orders": (consolidated_df['Order Status'].str.lower() == 'completed').sum(),
    "Cancelled Orders": (consolidated_df['Order Status'].str.lower() == 'cancel order').sum(),
    "Rider Reading Payouts": f"{consolidated_df['80/160'].sum()} PKR",
    "Total Revenue": f"Rs {consolidated_df['Total Amount'].sum():,}",
    "Avg Kitchen Time": safe_time_average(consolidated_df['Total Kitchen Time']),
    "Avg Pickup Time": safe_time_average(consolidated_df['Total Pickup Time']),
    "Avg Delivery Time": safe_time_average(consolidated_df['Total Delivery Time']),
    "Avg Rider Return Time": safe_time_average(consolidated_df['Total Rider Return Time']),
    "Avg Cycle Time": safe_time_average(consolidated_df['Total Cycle Time']),

}


for label, value in consolidated_metrics.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

st.markdown("---")

# --- Header for filtered metrics ---
st.title("🛵 Rider Delivery Dashboard")
st.markdown(
    f"📅 **{start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}** &nbsp;&nbsp;&nbsp;"
    f"🧍 **{', '.join(selected_riders) if selected_riders else 'All'}** &nbsp;&nbsp;&nbsp;"
    f"📄 **{', '.join(selected_invoice_type)}** &nbsp;&nbsp;&nbsp;"
    f"🕑 **{', '.join(selected_shifts) if selected_shifts else 'All'}**",
    unsafe_allow_html=True
)
st.markdown("---")

# --- Grouped Metrics (Filtered) ---
basic_metrics = {
    "Total Orders": len(filtered_df),
    "In Progress": (filtered_df['Order Status'].str.lower() == 'in progress').sum(),
    "Completed": (filtered_df['Order Status'].str.lower() == 'completed').sum(),
    "Cancelled": (filtered_df['Order Status'].str.lower() == 'cancel order').sum(),
}

sos_metrics = {
    "Avg Kitchen Time": format_timedelta(filtered_df['Total Kitchen Time'].mean()),
    "Avg Pickup Time": format_timedelta(filtered_df['Total Pickup Time'].mean()),
    "Avg Delivery Time": format_timedelta(filtered_df['Total Delivery Time'].mean()),
    "Avg Rider Return Time": format_timedelta(filtered_df['Total Rider Return Time'].mean()),
    "Avg Cycle Time": format_timedelta(filtered_df['Total Cycle Time'].mean()),
}

# 📊 Basic Metrics
st.markdown("<h3 style='margin-bottom: 0.5em;'>📊 Basic Information</h3>", unsafe_allow_html=True)
for label, value in basic_metrics.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# ⏱️ SOS Metrics
st.markdown("<h3 style='margin-top: 1.5em;'>⏱️ SOS Time Metrics</h3>", unsafe_allow_html=True)
for label, value in sos_metrics.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# 🛠️ Delay Reasons
st.markdown("<h3 style='margin-top: 1.5em;'>🛠️ Delay Reasons </h3>", unsafe_allow_html=True)
for reason in filtered_df['Delay Reason'].dropna().unique():
    count = (filtered_df['Delay Reason'] == reason).sum()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:16px'>- {reason}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:16px; font-weight:bold'>{count}</div>", unsafe_allow_html=True)

# 📢 Complaints
st.markdown("<h3 style='margin-top: 1.5em;'>📢 Customer Complaints </h3>", unsafe_allow_html=True)
for complaint in filtered_df['Customer Complaint'].dropna().unique():
    count = (filtered_df['Customer Complaint'] == complaint).sum()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:16px'>- {complaint}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:16px; font-weight:bold'>{count}</div>", unsafe_allow_html=True)

# 🎯 Compensation Summary
st.markdown("<h3 style='margin-top: 1.5em;'>🎯 Rider Reading Payouts </h3>", unsafe_allow_html=True)
filtered_df['80/160'] = pd.to_numeric(filtered_df['80/160'], errors='coerce')
count_80 = (filtered_df['80/160'] == 80).sum()
count_160 = (filtered_df['80/160'] == 160).sum()
total_comp = filtered_df['80/160'].sum()

labels = {
    "80-PKR entries": count_80,
    "160-PKR entries": count_160,
    "Rider Reading Payouts": f"{total_comp} PKR"
}
for label, value in labels.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# Breakdown by Invoice Type
st.markdown("<h4 style='margin-top: 1em;'>Compensation by Invoice Type:</h4>", unsafe_allow_html=True)
comp_group = filtered_df.groupby('Invoice Type')['80/160'].sum()
for inv_type, val in comp_group.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:16px'>- {inv_type}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:16px; font-weight:bold'>{val} PKR</div>", unsafe_allow_html=True)

# 💰 Invoice Summary with Deductions
st.markdown("<h3 style='margin-top: 1.5em;'>💰 Invoice Summary</h3>", unsafe_allow_html=True)
total_invoices = len(filtered_df)
total_amount = filtered_df['Total Amount'].sum()
cancelled_amount = filtered_df[filtered_df['Order Status'].str.lower() == 'cancel order']['Total Amount'].sum()
net_amount = total_amount - cancelled_amount

invoice_summary = {
    "Total Invoices": total_invoices,
    "Total Amount": f"Rs {total_amount:,.0f}",
    "Cancelled Order Amount": f"- Rs {cancelled_amount:,.0f}",
    "Net Revenue": f"Rs {net_amount:,.0f}"
}
for label, value in invoice_summary.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# View Raw Data
with st.expander("📄 View Raw Data"):
    st.dataframe(filtered_df.reset_index(drop=True))

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe
from datetime import datetime


# Define required scopes
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Load credentials from Streamlit secrets
creds_dict = st.secrets["gcp_service_account"]

# Create credentials with proper scopes
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

# Authorize with gspread
gc = gspread.authorize(credentials)

# Open spreadsheet and worksheet
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
    df = get_as_dataframe(
        worksheet,
        evaluate_formulas=True,
        include_tailing_empty=False,
        default_blank=""
    )
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df = df[~df.applymap(lambda x: isinstance(x, str) and '#REF!' in x)].copy()

    df.columns = df.columns.str.strip()  # ✅ add this line

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
# Initialize selected riders in session state if not present
if 'selected_riders' not in st.session_state:
    st.session_state.selected_riders = rider_options

# Buttons to modify session state
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Select All Riders"):
        st.session_state.selected_riders = rider_options
with col2:
    if st.button("Clear All Riders"):
        st.session_state.selected_riders = []

# Rider multiselect using session state
selected_riders = st.sidebar.multiselect(
    "Select Rider(s)", rider_options, default=st.session_state.selected_riders, key="rider_multiselect"
)
st.session_state.selected_riders = selected_riders

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

# # --- Consolidated Overview (Unfiltered except by Date & Shift) ---
# st.markdown("## 📦 Consolidated Overview (By Date & Shift)", unsafe_allow_html=True)

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
#consolidated_df = consolidated_df[consolidated_df['Invoice Number'].notna()]


# consolidated_metrics = {
#     "Total Orders": len(consolidated_df),
#     "Completed Orders": (consolidated_df['Order Status'].str.lower() == 'completed').sum(),
#     "Cancelled Orders": (consolidated_df['Order Status'].str.lower() == 'cancel order').sum(),
#     "Rider Reading Payouts": f"{consolidated_df['80/160'].sum()} PKR",
#     "Total Revenue": f"Rs {consolidated_df['Total Amount'].sum():,}",
#     "Avg Kitchen Time": safe_time_average(consolidated_df['Total Kitchen Time']),
#     "Avg Pickup Time": safe_time_average(consolidated_df['Total Pickup Time']),
#     "Avg Delivery Time": safe_time_average(consolidated_df['Total Delivery Time']),
#     "Avg Rider Return Time": safe_time_average(consolidated_df['Total Rider Return Time']),
#     "Avg Cycle Time": safe_time_average(consolidated_df['Total Cycle Time']),

# }


# for label, value in consolidated_metrics.items():
#     col1, col2 = st.columns([3, 1])
#     with col1:
#         st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
#     with col2:
#         st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# st.markdown("---")

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

comp_summary = (
    filtered_df.groupby('Invoice Type')
    .agg(Order_Count=('Invoice Type', 'count'), Payout=('80/160', 'sum'))
    .sort_values('Payout', ascending=False)
)

for inv_type, row in comp_summary.iterrows():
    label = f"{inv_type} (Count: {row['Order_Count']})"
    value = f"{row['Payout']} PKR"
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# 💰 Invoice Summary with Deductions, Payment Type Breakdown, and Complaint Orders
# 💰 Invoice Summary with Deductions, Payment Type Breakdown, and Complaint Orders
st.markdown("<h3 style='margin-top: 1.5em;'>💰 Invoice Summary</h3>", unsafe_allow_html=True)

# --- Complaint Order Details ---
complaint_df = filtered_df[filtered_df['Invoice Type'].str.lower() == 'complaint order']
num_complaints = len(complaint_df)
complaint_amount = complaint_df['Total Amount'].sum()

# --- Staff Tab Order Details ---
staff_tab_df = filtered_df[filtered_df['Invoice Type'].str.lower() == 'staff tab']
num_staff_tab = len(staff_tab_df)
staff_tab_amount = staff_tab_df['Total Amount'].sum()

# --- Valid Invoices (exclude Complaint and Staff Tab)
filtered_df_valid = filtered_df[
    ~filtered_df['Invoice Type'].str.lower().isin(['complaint order', 'staff tab'])
]

total_invoices = len(filtered_df_valid)
total_amount = filtered_df_valid['Total Amount'].sum()

# --- Cancelled Orders ---
cancelled_df = filtered_df[filtered_df['Order Status'].str.lower() == 'cancel order']
cancelled_amount = cancelled_df['Total Amount'].sum()

# --- Cancelled by Invoice Type Breakdown ---
cancelled_by_invoice_type = (
    cancelled_df.groupby('Invoice Type')['Total Amount']
    .agg(['count', 'sum'])
    .reset_index()
)



# --- Rider Payouts and Cash Submissions ---
rider_payouts = filtered_df['80/160'].sum()
rider_cash_submitted = pd.to_numeric(filtered_df['Rider Cash Submission to DFPL'], errors='coerce').sum()

# --- Payment Type Breakdown (valid only) ---
cod_total = filtered_df_valid[filtered_df_valid['Invoice Type'].str.lower().str.contains('cod')]['Total Amount'].sum()
card_total = filtered_df_valid[filtered_df_valid['Invoice Type'].str.lower().str.contains('card')]['Total Amount'].sum()

# --- Zeeshan Logic ---
zeeshanvalue = cod_total - rider_payouts 
#- rider_cash_submitted

# --- Final Net Collection Calculation ---
net_after_cancel = total_amount - cancelled_amount
final_net_collection = net_after_cancel - complaint_amount - staff_tab_amount - zeeshanvalue 
#- rider_cash_submitted

# --- Summary Dictionary ---
invoice_summary = {
    #"Total Valid Invoices": total_invoices,
    "Total Amount (Excl. Complaints & Staff Tab)": f"Rs {total_amount:,.0f}",
    "Card Total Amount": f"Rs {card_total:,.0f}",
    "COD Total Amount": f"Rs {cod_total:,.0f}",
    "Cancelled Order Amount": f"- Rs {cancelled_amount:,.0f}",
    "Complaint Order Amount": f"- Rs {complaint_amount:,.0f}",
    "Staff Tab Order Amount": f"- Rs {staff_tab_amount:,.0f}",
    "Rider Reading Payouts": f"- Rs {rider_payouts:,.0f}",    
    "Rider Cash Submitted to DFPL": f"- Rs {rider_cash_submitted:,.0f}",
    "Final Net Collection (COD Amount - Rider Payout)":f"{zeeshanvalue}",
    "Final Net Collection (Card Verification)": f"Rs {card_total:,.0f}"
}

# --- Display Summary ---
for label, value in invoice_summary.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<span style='font-size:18px; font-weight:600'>{label}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)

# --- Cancelled Orders Breakdown by Invoice Type ---
if not cancelled_by_invoice_type.empty:
    st.markdown("<h4 style='margin-top: 1em;'>🚫 Cancelled Orders by Invoice Type</h4>", unsafe_allow_html=True)
    for _, row in cancelled_by_invoice_type.iterrows():
        label = f"{row['Invoice Type']} (Orders: {row['count']})"
        value = f"- Rs {row['sum']:,.0f}"
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<span style='font-size:16px'>{label}</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='text-align:right; font-size:16px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)


# View Raw Data
with st.expander("📄 View Raw Data"):
    st.dataframe(filtered_df.reset_index(drop=True))
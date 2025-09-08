import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe
from datetime import datetime, timedelta
import altair as alt

# =========================
# ---------- AUTH ----------
# =========================
IDLE_TIMEOUT_MIN = 45    # auto-logout after X minutes of inactivity (set None to disable)

# 🔒 Fixed username/passwords (all keys must be lowercase)
USERS = {
    "p6": "123",
    "emp": "emp123",
    "zeeshan": "p6-view",
    "cc": "CC123",
    "ck": "CK123",
    "jt": "JT123",
    "bt": "BT123",
    "admin": "6969",   # 🔑 Admin login
}


# 📊 Data sources mapped to usernames (lowercase) or "default"
DATA_SOURCES = {
    "emp": {  # Emporium branch
        "sheet_url": "https://docs.google.com/spreadsheets/d/1I2sIaAJxrNQIRHAmRTXthqtG1DH6Zep7Hnsa42UZmkk/edit#gid=1740157752",
        "worksheet": "For Dashboard",
        "phase": "Emporium",
        "title": "🛵 Rider Delivery Dashboard – Emporium",
        "brand": "Johnny & Jugnu",
    },
    "admin": {
        "sheet_url": None,   # placeholder, admin loads ALL branches
        "worksheet": None,
        "phase": "Admin",
        "title": "🛡️ Riders Dashboard – Admin View",
        "brand": "Johnny & Jugnu",
    },
    "cc": {  # CC branch
        "sheet_url": "https://docs.google.com/spreadsheets/d/1TlEwALII0nPjj5oWlmEHOiC85S60R9T3IOcUkK-bLV0/edit#gid=1740157752",
        "worksheet": "For Dashboard",
        "phase": "CC",
        "title": "🛵 Rider Delivery Dashboard – CC",
        "brand": "Johnny & Jugnu",
    },
    "ck": {  # CK branch
        "sheet_url": "https://docs.google.com/spreadsheets/d/19PfaI5sxWiSncOrsTeJtL9sjnwfoR_6XUu7Q0Z5X748/edit?gid=1037783061",
        "worksheet": "For Dashboard",
        "phase": "CK",
        "title": "🛵 Rider Delivery Dashboard – CK",
        "brand": "Johnny & Jugnu",
    },
    "jt": {  # JT branch
        "sheet_url": "https://docs.google.com/spreadsheets/d/1qLqGFoPu10xbBEnJe_QJj7dyYrX16a25e8kFDNf-NDQ/edit?gid=1037783061",
        "worksheet": "For Dashboard",
        "phase": "JT",
        "title": "🛵 Rider Delivery Dashboard – JT",
        "brand": "Johnny & Jugnu",
    },
    "bt": {  # BT branch
        "sheet_url": "https://docs.google.com/spreadsheets/d/1F4XQw804ET_SMC_ihsjDo6zFGcid0hqVU3-ODU5VWKQ/edit?gid=1037783061",
        "worksheet": "For Dashboard",
        "phase": "BT",
        "title": "🛵 Rider Delivery Dashboard – BT",
        "brand": "Johnny & Jugnu",
    },
    "default": {  # Default (Phase 6) branch
        "sheet_url": "https://docs.google.com/spreadsheets/d/1luzRe9um2-RVWCvChbzQI91LZm1oq_yc2d08gaOuYBg/edit",
        "worksheet": "For Dashboard",
        "phase": "Phase 6",
        "title": "🛵 Rider Delivery Dashboard – P6",
        "brand": "Johnny & Jugnu",
    },
}

def _resolve_profile(username: str) -> dict:
    u = (username or "").strip().lower()
    return DATA_SOURCES.get(u, DATA_SOURCES["default"])

def _authed() -> bool:
    if not st.session_state.get("authed", False):
        return False
    if IDLE_TIMEOUT_MIN is None:
        return True
    last = st.session_state.get("last_activity")
    if last is None:
        return False
    if datetime.utcnow() - last > timedelta(minutes=IDLE_TIMEOUT_MIN):
        st.session_state.clear()
        return False
    st.session_state["last_activity"] = datetime.utcnow()
    return True

def _login_ui():
    default_title = DATA_SOURCES["default"]["title"]
    st.markdown(
        f"""
        <div style="text-align:center;margin-top:6vh">
          <h1 style="margin-bottom:0.5em">🛡️ Riders Dashboard Access</h1>
          <p style="color:#666">Enter your credentials to view: <b>{default_title}</b> or the Emporium dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login_form", clear_on_submit=False):
        username_in = st.text_input("Username", value="", autocomplete="username")
        password_in = st.text_input("Password", type="password", value="", autocomplete="current-password")
        submit = st.form_submit_button("Login")

    if submit:
        u = username_in.strip().lower()
        p = password_in
        user_ok = u in USERS
        pass_ok = USERS.get(u, None) == p
        if user_ok and pass_ok:
            prof = _resolve_profile(u)
            st.session_state["authed"] = True
            st.session_state["username"] = u
            st.session_state["last_activity"] = datetime.utcnow()
            st.session_state["sheet_url"] = prof["sheet_url"]
            st.session_state["worksheet"] = prof["worksheet"]
            st.session_state["phase"] = prof["phase"]
            st.session_state["title"] = prof["title"]
            st.session_state["brand"] = prof["brand"]
            st.cache_data.clear()   # clear cached data from any prior user/sheet
            st.success("Authenticated. Loading dashboard…")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")

# Gate everything below this point
if not _authed():
    _login_ui()
    st.stop()



# Sidebar session header + logout
phase_label = st.session_state.get("phase", _resolve_profile("default")["phase"])
with st.sidebar:
    st.caption(f"Signed in as **{st.session_state.get('username','(user)')}** · {phase_label}")
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
# =========================
# ------- /AUTH -----------
# =========================


# -----------------------------
# Google Sheets / Data Loading
# -----------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds_dict = st.secrets["gcp_service_account"]
credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Use the logged-in user's source
SHEET_URL = st.session_state.get("sheet_url", DATA_SOURCES["default"]["sheet_url"])
WORKSHEET_NAME = st.session_state.get("worksheet", DATA_SOURCES["default"]["worksheet"])
def format_timedelta(td):
    if pd.isnull(td):
        return "00:00:00"
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def safe_time_average(series):
    valid = series[(series.notna()) & (series.dt.total_seconds() > 0)]
    return format_timedelta(valid.mean()) if not valid.empty else "00:00:00"

# cache by strings (sheet_url, worksheet_name) so each user/source has its own cache
@st.cache_data(ttl=600)
def load_data(sheet_url: str, worksheet_name: str):
    sheet = gc.open_by_url(sheet_url)
    ws = sheet.worksheet(worksheet_name)
    df = get_as_dataframe(
        ws,
        evaluate_formulas=True,
        include_tailing_empty=False,
        default_blank=""
    )
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df = df[~df.applymap(lambda x: isinstance(x, str) and '#REF!' in x)].copy()
    df.columns = df.columns.str.strip()

    expected_columns = [
        "Date", "Rider Name/Code", "Invoice Type", "Shift Type", "Invoice Number",
        "Total Amount", "80/160", "Total Kitchen Time", "Total Pickup Time",
        "Total Delivery Time", "Total Rider Return Time", "Total Cycle Time",
        "Delay Reason", "Customer Complaint", "Order Status",
        "Rider Cash Submission to DFPL", "Closing Status", "Total Promised Time",
        "Invoice Time", "Trade Area", "50/10"   # <- include 50/10 for Emporium adjustment
    ]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    for col in ['Total Kitchen Time','Total Pickup Time','Total Delivery Time',
                'Total Rider Return Time','Total Cycle Time','Total Promised Time']:
        df[col] = pd.to_timedelta(df[col].astype(str), errors='coerce')

    df['80/160'] = pd.to_numeric(df['80/160'], errors='coerce').fillna(0).astype(int)
    df['Total Amount'] = pd.to_numeric(df['Total Amount'], errors='coerce').fillna(0).astype(int)
    df['Rider Cash Submission to DFPL'] = pd.to_numeric(df['Rider Cash Submission to DFPL'], errors='coerce').fillna(0).astype(int)

    # "50/10" may be per-order numeric; make numeric
    df['50/10'] = pd.to_numeric(df['50/10'], errors='coerce').fillna(0)

    df['Invoice Time'] = pd.to_datetime(df['Invoice Time'], format="%I:%M:%S %p", errors='coerce')
    df['Hour'] = df['Invoice Time'].dt.hour

    return df, datetime.now()
# -----------------------------
# Data loading (admin vs normal)
# -----------------------------
if st.session_state.get("username") == "admin":
    branch_options = [k for k in DATA_SOURCES.keys() if k not in ["admin"]]
    selected_branches = st.sidebar.multiselect(
        "Select Branches",
        options=branch_options,
        default=branch_options,
    )

    all_dfs = []
    for branch in selected_branches:
        src = DATA_SOURCES[branch]
        if not src["sheet_url"]:
            continue
        df_branch, _ = load_data(src["sheet_url"], src["worksheet"])
        df_branch["Branch"] = src["phase"]
        all_dfs.append(df_branch)

    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
        last_updated = datetime.now()
    else:
        st.warning("Please select at least one branch to view data.")
        st.stop()

else:
    SHEET_URL = st.session_state.get("sheet_url", DATA_SOURCES["default"]["sheet_url"])
    WORKSHEET_NAME = st.session_state.get("worksheet", DATA_SOURCES["default"]["worksheet"])
    df, last_updated = load_data(SHEET_URL, WORKSHEET_NAME)
    df["Branch"] = st.session_state.get("phase")

# ----------------
# Page setup / UI (with red card styling)
# ----------------
page_title = st.session_state.get("title", DATA_SOURCES["default"]["title"])
brand_name = st.session_state.get("brand", DATA_SOURCES["default"]["brand"])

st.markdown(f"""
    <h1 style='text-align: center; color: #c62828; font-size: 42px; font-weight: bold; margin-bottom: 1em;'>
        {page_title}
    </h1>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        .card {
            background-color: #c62828; /* strong red */
            padding: 1.2em;
            margin-bottom: 1.2em;
            border-radius: 12px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            color: white;
        }
        .card h3, .card h4 {
            color: white;
            margin-top: 0;
        }
        .card-metric {
            font-size: 18px;
            font-weight: 600;
            margin: 0.2em 0;
        }
        .card-metric-value {
            text-align: right;
            font-weight: bold;
        }
        .card-metric span { color: white; }
        @keyframes flash { 0% {opacity:1;} 50% {opacity:0.2;} 100% {opacity:1;} }
        .flash { animation: flash 1.5s infinite; color: #4CAF50; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown(
    f"""
    <div style="text-align: center; margin-bottom: 1em;">
        <img src="https://raw.githubusercontent.com/arbazmubasher1/RidersDashboard/main/logo%20JJ%20....png" width="180">
        <p style="color: grey; font-size: 14px; margin-top: 0.5em;">{brand_name}</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.header("🔍 Search Filters")
if st.sidebar.button("🔄 Reload Sheet"):
    st.cache_data.clear()

# Load data for the active sheet/profile
#df, last_updated = load_data(SHEET_URL, WORKSHEET_NAME)

# Helpful test hint
st.sidebar.caption(f"Source: {'Emporium' if st.session_state.get('phase')=='Emporium' else 'P6'}")
st.sidebar.caption(f"Worksheet: {WORKSHEET_NAME}")

# -----------------------------
# Cascading sidebar filters (safe)
# -----------------------------
min_date = pd.to_datetime(df['Date'].min())
max_date = pd.to_datetime(df['Date'].max())
start_date, end_date = st.sidebar.date_input("Select Date Range", [min_date, max_date])

base = df[
    (df['Date'] >= pd.to_datetime(start_date)) &
    (df['Date'] <= pd.to_datetime(end_date))
].copy()

# --- Invoice Type ---
invoice_type_options = (
    sorted(base['Invoice Type'].dropna().unique().tolist())
    if 'Invoice Type' in base.columns and not base['Invoice Type'].dropna().empty
    else []
)

if 'selected_invoice_type' not in st.session_state:
    st.session_state.selected_invoice_type = invoice_type_options

selected_invoice_type = st.sidebar.multiselect(
    "Select Invoice Type(s)",
    options=invoice_type_options,
    default=st.session_state.selected_invoice_type if st.session_state.selected_invoice_type else invoice_type_options,
    key="invoice_multiselect"
)
st.session_state.selected_invoice_type = selected_invoice_type or invoice_type_options

lvl1 = base[base['Invoice Type'].isin(st.session_state.selected_invoice_type)] if st.session_state.selected_invoice_type else base

# --- Shift Type ---
shift_options = (
    sorted(lvl1['Shift Type'].dropna().unique().tolist())
    if 'Shift Type' in lvl1.columns and not lvl1['Shift Type'].dropna().empty
    else []
)

if 'selected_shifts' not in st.session_state:
    st.session_state.selected_shifts = shift_options

selected_shifts = st.sidebar.multiselect(
    "Select Shift(s)",
    options=shift_options,
    default=st.session_state.selected_shifts if st.session_state.selected_shifts else shift_options,
    key="shift_multiselect"
)
st.session_state.selected_shifts = selected_shifts or shift_options

lvl2 = lvl1[lvl1['Shift Type'].isin(st.session_state.selected_shifts)] if st.session_state.selected_shifts else lvl1

# --- Rider Name/Code ---
rider_options = (
    sorted(lvl2['Rider Name/Code'].dropna().unique().tolist())
    if 'Rider Name/Code' in lvl2.columns and not lvl2['Rider Name/Code'].dropna().empty
    else []
)

if 'selected_riders' not in st.session_state:
    st.session_state.selected_riders = rider_options

c1, c2 = st.sidebar.columns(2)
with c1:
    if st.button("Select All Riders"):
        st.session_state.selected_riders = rider_options
with c2:
    if st.button("Clear All Riders"):
        st.session_state.selected_riders = []

selected_riders = st.sidebar.multiselect(
    "Select Rider(s)",
    options=rider_options,
    default=st.session_state.selected_riders if set(st.session_state.selected_riders) <= set(rider_options) else rider_options,
    key="rider_multiselect"
)
st.session_state.selected_riders = selected_riders

# --- Final filtered dataframe ---
filtered_df = df[
    (df['Date'] >= pd.to_datetime(start_date)) &
    (df['Date'] <= pd.to_datetime(end_date)) &
    (df['Invoice Type'].isin(st.session_state.selected_invoice_type) if invoice_type_options else True) &
    (df['Shift Type'].isin(st.session_state.selected_shifts) if shift_options else True) &
    (df['Rider Name/Code'].isin(st.session_state.selected_riders) if rider_options else True)
]

# -----------------------------
# 📌 Selection summary band
# -----------------------------
if selected_riders or selected_invoice_type or selected_shifts:
    st.markdown(
        f"""
        <div class='card'>
            <h3 style="margin:0 0 8px 0;">📌 Current Filters</h3>
            <div class='card-metric'>📅 {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}</div>
            <div class='card-metric'>🧍 {len(selected_riders)} rider(s) selected</div>
            <div class='card-metric'>📄 {', '.join(selected_invoice_type)}</div>
            <div class='card-metric'>🕑 {', '.join(selected_shifts) if selected_shifts else 'None'}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# 📈 Order Volume by Trade Area
# -----------------------------
st.markdown("<div class='card'><h3>📦 Order Volume by Trade Area</h3>", unsafe_allow_html=True)

filtered_df_chart = filtered_df.dropna(subset=['Trade Area', 'Hour'])
available_hours = sorted(filtered_df_chart['Hour'].dropna().unique())
selected_hour = st.selectbox("⏱️ Filter by Hour", options=["All"] + list(available_hours))

if selected_hour != "All":
    df_for_chart = filtered_df_chart[filtered_df_chart['Hour'] == selected_hour]
    title_suffix = f" at {selected_hour}:00"
else:
    df_for_chart = filtered_df_chart.copy()
    title_suffix = " (All Hours Combined)"

trade_area_orders = (
    df_for_chart.groupby("Trade Area")
    .size()
    .reset_index(name="Order Count")
    .sort_values("Order Count", ascending=False)
)

st.markdown(f"**Showing**: {title_suffix}", unsafe_allow_html=True)

if not trade_area_orders.empty:
    bar_chart = alt.Chart(trade_area_orders).mark_bar(color="#c62828").encode(
        x=alt.X("Trade Area:N", sort='-y', title="Trade Area"),
        y=alt.Y("Order Count:Q", title="Number of Orders"),
        tooltip=["Trade Area", "Order Count"]
    ).properties(width=700, height=400).configure_axis(labelFontSize=12, titleFontSize=14)
    st.altair_chart(bar_chart, use_container_width=True)
else:
    st.info("No orders available for the selected hour or filters.")
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 📢 Rider Closing Status
# -----------------------------
st.markdown("<div class='card'><h3>📢 Rider Closing Status</h3>", unsafe_allow_html=True)
closing_status_counts = filtered_df['Closing Status'].dropna().value_counts()
for label, value in closing_status_counts.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<div class='card-metric'>{label}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card-metric-value'>{value}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 📊 Basic Information
# -----------------------------
basic_metrics = {
    "Total Orders": len(filtered_df),
    "In Progress": (filtered_df['Order Status'].str.lower() == 'in progress').sum(),
    "Completed": (filtered_df['Order Status'].str.lower() == 'completed').sum(),
    "Cancelled": (filtered_df['Order Status'].str.lower() == 'cancel order').sum(),
}
st.markdown("<div class='card'><h3>📊 Basic Information</h3>", unsafe_allow_html=True)
for label, value in basic_metrics.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<div class='card-metric'>{label}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card-metric-value'>{value}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# ⏱️ SOS Time Metrics
# -----------------------------
sos_metrics = {
    "Avg Kitchen Time": format_timedelta(filtered_df['Total Kitchen Time'].mean()),
    "Avg Pickup Time": format_timedelta(filtered_df['Total Pickup Time'].mean()),
    "Avg Delivery Time": format_timedelta(filtered_df['Total Delivery Time'].mean()),
    "Avg Rider Return Time": format_timedelta(filtered_df['Total Rider Return Time'].mean()),
    "Avg Cycle Time": format_timedelta(filtered_df['Total Cycle Time'].mean()),
    "Avg Promised Time": format_timedelta(filtered_df['Total Promised Time'].mean()),
}
st.markdown("<div class='card'><h3>⏱️ SOS Time Metrics</h3>", unsafe_allow_html=True)
for label, value in sos_metrics.items():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<div class='card-metric'>{label}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card-metric-value'>{value}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 🛠️ Delay Reasons
# -----------------------------
st.markdown("<div class='card'><h3>🛠️ Delay Reasons</h3>", unsafe_allow_html=True)
for reason in filtered_df['Delay Reason'].dropna().unique():
    count = (filtered_df['Delay Reason'] == reason).sum()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<div class='card-metric'>{reason}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card-metric-value'>{count}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 📢 Customer Complaints
# -----------------------------
st.markdown("<div class='card'><h3>📢 Customer Complaints</h3>", unsafe_allow_html=True)
for complaint in filtered_df['Customer Complaint'].dropna().unique():
    count = (filtered_df['Customer Complaint'] == complaint).sum()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<div class='card-metric'>{complaint}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card-metric-value'>{count}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 💸 Rider Reading Payouts
# -----------------------------
st.markdown("<div class='card'><h3>💸 Rider Reading Payouts</h3>", unsafe_allow_html=True)
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
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 💰 Invoice Summary (with Emporium 50/10 adjustment)
# -----------------------------

# Complaint/Staff/PR Tab amounts
complaint_df = filtered_df[filtered_df['Invoice Type'].str.lower() == 'complaint order']
complaint_amount = complaint_df['Total Amount'].sum()

staff_tab_df = filtered_df[
    filtered_df['Invoice Type'].str.strip().str.lower().str.contains('staff tab', na=False)
]
staff_tab_amount = staff_tab_df['Total Amount'].sum()

pr_tab_df = filtered_df[
    filtered_df['Invoice Type'].str.strip().str.lower().str.contains('pr tab', na=False)
]
pr_tab_amount = pr_tab_df['Total Amount'].sum()


filtered_df_valid = filtered_df[~filtered_df['Invoice Type'].str.lower().isin(['complaint order', 'staff tab'])]
#total_amount = filtered_df_valid['Total Amount'].sum()

total_amount=filtered_df['Total Amount'].sum()
cancelled_df = filtered_df[filtered_df['Order Status'].str.lower() == 'cancel order']
cancelled_by_invoice_type = cancelled_df.groupby('Invoice Type')['Total Amount'].agg(['count','sum']).reset_index()

rider_payouts = filtered_df['80/160'].sum()
rider_cash_submitted = pd.to_numeric(filtered_df['Rider Cash Submission to DFPL'], errors='coerce').sum()

cancelled_cod_amount = cancelled_df[cancelled_df['Invoice Type'].str.lower().str.contains('cod')]['Total Amount'].sum()
cancelled_card_amount = cancelled_df[cancelled_df['Invoice Type'].str.lower().str.contains('card')]['Total Amount'].sum()

cod_total = filtered_df_valid[filtered_df_valid['Invoice Type'].str.lower().str.contains('cod')]['Total Amount'].sum() 
#- cancelled_cod_amount
card_total = filtered_df_valid[filtered_df_valid['Invoice Type'].str.lower().str.contains('card')]['Total Amount'].sum() 
#- cancelled_card_amount

# 🔻 Emporium-only adjustment: subtract "50/10"
fifty_ten_total = 0.0
if st.session_state.get("username", "").lower() == "emp":
    fifty_ten_total = pd.to_numeric(filtered_df["50/10"], errors="coerce").fillna(0).sum()
    cod_total -= fifty_ten_total

# Final net
net_after_cancel = total_amount - cancelled_cod_amount - cancelled_card_amount
if st.session_state.get("username", "").lower() == "emp":
    final_net_collection = net_after_cancel - complaint_amount - staff_tab_amount - rider_cash_submitted - rider_payouts - pr_tab_amount-card_total-fifty_ten_total
else:
    final_net_collection = net_after_cancel - complaint_amount - staff_tab_amount - rider_cash_submitted - rider_payouts - pr_tab_amount-card_total

dum=cod_total+pr_tab_amount+staff_tab_amount+complaint_amount

st.markdown("<div class='card'><h3>💰 Invoice Summary</h3>", unsafe_allow_html=True)

invoice_summary = {
    "Total Amount": f"Rs {total_amount:,.0f}",
    "Card Total Amount ": f"Rs {card_total:,.0f}",
    "Cancelled CARD Amount": f"- Rs {cancelled_card_amount:,.0f}",
    "Final Net Collection (Card Verification)": f"Rs {card_total-cancelled_card_amount:,.0f}",

    
}

if st.session_state.get("username", "").lower() == "emp":
    #invoice_summary["50/10 Adjustment (Emporium)"] = f"- Rs {fifty_ten_total:,.0f}"
    invoice_summary["COD Total Amount "] = f"Rs {dum+fifty_ten_total:,.0f}"
else:
    invoice_summary["COD Total Amount "] = f"Rs {dum:,.0f}"

invoice_summary.update({
    "PR Tab Order Amount": f"- Rs {pr_tab_amount:,.0f}",
    "Staff Tab Order Amount": f"- Rs {staff_tab_amount:,.0f}",
    "Complaint Order Amount": f"- Rs {complaint_amount:,.0f}",
    "Cancelled COD Amount": f"- Rs {cancelled_cod_amount:,.0f}",
    "Parking Fee" : f"- Rs {fifty_ten_total:,.0f}",
    "Rider Reading Payouts": f"- Rs {rider_payouts:,.0f}",
    "Rider Cash Submitted to DFPL": f"- Rs {rider_cash_submitted:,.0f}",
    "Final Net Collection (COD)": f"Rs {dum-pr_tab_amount-staff_tab_amount-complaint_amount-cancelled_cod_amount-rider_payouts-rider_cash_submitted:,.0f}",
})

for label, value in invoice_summary.items():
    flash_class = ""
    if "Final Net Collection (COD)" in label or "Final Net Collection (Card Verification)" in label:
        flash_class = " flash"

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"<div class='card-metric{flash_class}'>{label}</div>", 
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"<div class='card-metric-value{flash_class}'>{value}</div>", 
            unsafe_allow_html=True
        )

st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 📢 Cancelled Orders by Invoice Type
# -----------------------------
if not cancelled_by_invoice_type.empty:
    st.markdown("<div class='card'><h3>📢 Cancelled Orders by Invoice Types</h3>", unsafe_allow_html=True)
    for _, row in cancelled_by_invoice_type.iterrows():
        label = f"{row['Invoice Type']} (Orders: {row['count']})"
        value = f"- Rs {row['sum']:,.0f}"
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<span style='font-size:16px'>{label}</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='text-align:right; font-size:16px; font-weight:bold'>{value}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# 📄 Raw Data
# -----------------------------
with st.expander("📄 View Raw Data"):
    st.dataframe(filtered_df.reset_index(drop=True))

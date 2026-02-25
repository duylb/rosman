import streamlit as st
import pandas as pd
from datetime import timedelta
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from st_aggrid.shared import ColumnsAutoSizeMode

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="RosMan – Roster Dashboard",
)

# ─────────────────────────────────────────────
# THEME COLORS
# ─────────────────────────────────────────────
BG_PAGE   = "#0e1117"
BG_CARD   = "#151826"
BG_TABLE  = "#1a1d27"
BG_HEADER = "#22263a"
BORDER    = "#2f344d"
TEXT_MAIN = "#e6e9f2"
TEXT_DIM  = "#8b90a8"

SHIFT_BG = {"Q": "#1b4f8a", "S": "#1a5c30", "C": "#6b5000", "B": "#7a2800"}
SHIFT_FG = "#ffffff"

CELL_SZ = 42
ROW_HEIGHT = 42
HDR_H = 38
GRP_H = 28

# ─────────────────────────────────────────────
# GLOBAL STYLING
# ─────────────────────────────────────────────
st.markdown(f"""
<style>
.stApp {{
    background-color: {BG_PAGE};
}}

.block-container {{
    padding-top: 1rem;
}}

.card {{
    background-color: {BG_CARD};
    padding: 18px;
    border-radius: 14px;
    border: 1px solid {BORDER};
}}

h1,h2,h3,h4,p,label {{
    color: {TEXT_MAIN};
}}

.small-text {{
    color: {TEXT_DIM};
    font-size: 13px;
}}

.stButton > button {{
    background: #2a3050;
    color: white;
    border-radius: 8px;
    border: 1px solid {BORDER};
}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("## 🗓 RosMan – Roster Dashboard")
st.markdown('<div class="small-text">Modern shift scheduling system</div>', unsafe_allow_html=True)
st.markdown("---")

# ─────────────────────────────────────────────
# SIDEBAR – CONTROLS
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙ Controls")

    uploaded_file = st.file_uploader("Upload DSNhanVien.csv", type=["csv"])

    date_range = st.date_input(
        "Select date range",
        value=None
    )

    search_name = st.text_input("Search employee")
    compact_mode = st.toggle("Compact mode")

# ─────────────────────────────────────────────
# FILE CHECK
# ─────────────────────────────────────────────
if not uploaded_file:
    st.info("Upload DSNhanVien.csv to begin.")
    st.stop()

df = pd.read_csv(uploaded_file)
df.columns = df.columns.str.strip()

if "FullName" not in df.columns or "Position" not in df.columns:
    st.error("CSV must contain: FullName and Position")
    st.stop()

if not date_range or len(date_range) != 2:
    st.warning("Please select a valid date range.")
    st.stop()

start_date, end_date = date_range

# ─────────────────────────────────────────────
# FILTERING
# ─────────────────────────────────────────────
employees = df[["FullName", "Position"]].copy()

if search_name:
    employees = employees[
        employees["FullName"].str.contains(search_name, case=False)
    ]

# ─────────────────────────────────────────────
# DATE LIST
# ─────────────────────────────────────────────
dates = []
cur = start_date
while cur <= end_date:
    dates.append(cur)
    cur += timedelta(days=1)

# ─────────────────────────────────────────────
# KPI SUMMARY BAR
# ─────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

col1.metric("Employees", len(employees))
col2.metric("Total Days", len(dates))
col3.metric("Total Shift Slots", len(employees) * len(dates) * 2)

st.markdown("---")

# ─────────────────────────────────────────────
# BUILD ROSTER DF
# ─────────────────────────────────────────────
roster_df = employees.copy()

for d in dates:
    lbl = d.strftime("%d-%m")
    roster_df[f"{lbl}_M"] = ""
    roster_df[f"{lbl}_C"] = ""

ROW_HEIGHT = 34 if compact_mode else 42

# ─────────────────────────────────────────────
# JS CELL STYLE
# ─────────────────────────────────────────────
cell_style_js = JsCode(f"""
function(params) {{
    const v = (params.value || '').trim();
    const p = v.charAt(0).toUpperCase();
    const bgMap = {SHIFT_BG};
    const bg = bgMap[p];
    return {{
        backgroundColor: bg || 'transparent',
        color: bg ? '{SHIFT_FG}' : '{TEXT_DIM}',
        fontWeight: bg ? '700' : '400',
        display:'flex',
        alignItems:'center',
        justifyContent:'center'
    }};
}}
""")

# ─────────────────────────────────────────────
# GRID BUILDER
# ─────────────────────────────────────────────
gb = GridOptionsBuilder.from_dataframe(roster_df)

gb.configure_default_column(
    editable=False,
    resizable=False,
    sortable=False,
    width=CELL_SZ,
)

gb.configure_column("FullName", pinned="left", width=180)
gb.configure_column("Position", pinned="left", width=140)

for d in dates:
    lbl = d.strftime("%d-%m")
    gb.configure_column(f"{lbl}_M", header_name="☀", cellStyle=cell_style_js)
    gb.configure_column(f"{lbl}_C", header_name="🌙", cellStyle=cell_style_js)

gb.configure_grid_options(
    rowHeight=ROW_HEIGHT,
    headerHeight=HDR_H,
    groupHeaderHeight=GRP_H,
    suppressMovableColumns=True,
)

grid_options = gb.build()

# ─────────────────────────────────────────────
# RENDER GRID
# ─────────────────────────────────────────────
st.markdown("### 📋 Roster Table")

grid_response = AgGrid(
    roster_df,
    gridOptions=grid_options,
    height=650,
    theme="balham-dark",
    update_on=["cellValueChanged"],
    allow_unsafe_jscode=True,
    columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE,
)

updated_df = grid_response["data"]

# ─────────────────────────────────────────────
# LEGEND
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🎨 Shift Legend")

legend_cols = st.columns(4)
legend_cols[0].markdown("🔵 **Q** – Manager")
legend_cols[1].markdown("🟢 **S** – Service")
legend_cols[2].markdown("🟡 **C** – Afternoon")
legend_cols[3].markdown("🔴 **B** – Kitchen")

# ─────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────
st.markdown("---")

export_rows = []
for _, row in updated_df.iterrows():
    rec = {"FullName": row["FullName"], "Position": row["Position"]}
    for d in dates:
        lbl = d.strftime("%d-%m")
        m = str(row.get(f"{lbl}_M", "")).strip()
        c = str(row.get(f"{lbl}_C", "")).strip()
        rec[lbl] = f"{m} {c}".strip()
    export_rows.append(rec)

export_df = pd.DataFrame(export_rows)

output = BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    export_df.to_excel(writer, index=False, sheet_name="Roster")

st.download_button(
    label="📥 Download LichLamViec.xlsx",
    data=output.getvalue(),
    file_name="LichLamViec.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.success("Ready to export ✔")
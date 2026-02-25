import streamlit as st
import pandas as pd
from datetime import timedelta
from io import BytesIO

from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from st_aggrid.shared import ColumnsAutoSizeMode

st.set_page_config(layout="wide", page_title="RosMan – Roster Manager")

# ── Constants ─────────────────────────────────────────────────────────────────
CELL_SZ    = 44
ROW_HEIGHT = CELL_SZ
HDR_H      = 36
GRP_H      = 28

BG_PAGE   = "#0e1117"
BG_TABLE  = "#1a1d27"
BG_HEADER = "#22263a"
BG_PINNED = "#1e2133"
BORDER    = "#3a3f5c"
BORDER_HD = "#5a6090"
TEXT_MAIN = "#e0e4f0"
TEXT_DIM  = "#888eaa"

SHIFT_BG = {"Q": "#1b4f8a", "S": "#1a5c30", "C": "#6b5000", "B": "#7a2800"}
SHIFT_FG = "#ffffff"

# ── Page CSS ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  .stApp {{ background-color: {BG_PAGE} !important; }}
  .block-container {{ padding-top: 1rem; padding-bottom: 0.5rem; }}
  h1, h2, h3, p, label, .stMarkdown {{ color: {TEXT_MAIN} !important; }}
  .stButton > button {{
      background: #2e3454; color: {TEXT_MAIN};
      border: 1px solid {BORDER}; border-radius: 6px;
  }}
  .stButton > button:hover {{ background: #3a4168; }}
</style>
""", unsafe_allow_html=True)

# ── AgGrid CSS ────────────────────────────────────────────────────────────────
AGGRID_CSS = {
    ".ag-root-wrapper": {"background-color": f"{BG_TABLE} !important", "border": f"1px solid {BORDER} !important"},
    ".ag-root": {"background-color": f"{BG_TABLE} !important"},
    ".ag-body-viewport": {"background-color": f"{BG_TABLE} !important"},
    ".ag-center-cols-container": {"background-color": f"{BG_TABLE} !important"},
    ".ag-center-cols-clipper": {"background-color": f"{BG_TABLE} !important"},
    ".ag-body": {"background-color": f"{BG_TABLE} !important"},
    ".ag-header": {
        "background-color": f"{BG_HEADER} !important",
        "border-bottom": f"2px solid {BORDER_HD} !important",
    },
    ".ag-header-row": {"background-color": f"{BG_HEADER} !important"},
    ".ag-header-cell": {
        "background-color": f"{BG_HEADER} !important",
        "color": f"{TEXT_MAIN} !important",
        "border-right": f"1px solid {BORDER_HD} !important",
        "font-size": "11px !important",
        "font-weight": "600 !important",
    },
    ".ag-header-group-cell": {
        "background-color": f"{BG_HEADER} !important",
        "color": f"{TEXT_MAIN} !important",
        "border-right": f"2px solid {BORDER_HD} !important",
        "border-left": f"2px solid {BORDER_HD} !important",
        "font-size": "12px !important",
        "font-weight": "700 !important",
    },
    ".ag-header-cell-label": {"justify-content": "center !important"},
    ".ag-header-group-cell-label": {"justify-content": "center !important"},
    ".ag-pinned-left-header": {
        "background-color": f"{BG_PINNED} !important",
        "border-right": f"3px solid {BORDER_HD} !important",
    },
    ".ag-pinned-left-cols-container": {
        "background-color": f"{BG_PINNED} !important",
        "border-right": f"3px solid {BORDER_HD} !important",
    },
    ".ag-row": {
        "background-color": f"{BG_TABLE} !important",
        "border-color": f"{BORDER} !important",
        "color": f"{TEXT_MAIN} !important",
    },
    ".ag-row-hover": {"background-color": "#1f2438 !important"},
    ".ag-row-odd": {"background-color": "#1d2030 !important"},
    ".ag-cell": {
        "border-color": f"{BORDER} !important",
        "display": "flex !important",
        "align-items": "center !important",
        "justify-content": "center !important",
        "padding": "0 !important",
        "font-size": "12px !important",
        "color": f"{TEXT_MAIN} !important",
    },
    # Dropdown
    ".ag-select-list": {
        "background-color": "#22263a !important",
        "color": f"{TEXT_MAIN} !important",
        "border": f"1px solid {BORDER_HD} !important",
    },
    ".ag-select-list-item": {
        "color": f"{TEXT_MAIN} !important",
        "padding": "5px 10px !important",
        "font-size": "12px !important",
    },
    ".ag-select-list-item:hover": {"background-color": "#2e3454 !important"},
    ".ag-select-list-item.ag-active-item": {
        "background-color": "#1b4f8a !important",
        "color": "#fff !important",
    },
    ".ag-popup-editor": {
        "background-color": "#22263a !important",
        "border": f"1px solid {BORDER_HD} !important",
    },
    "::-webkit-scrollbar": {"width": "6px", "height": "6px"},
    "::-webkit-scrollbar-track": {"background": BG_TABLE},
    "::-webkit-scrollbar-thumb": {"background": "#3a3f5c", "border-radius": "3px"},
    "::-webkit-scrollbar-thumb:hover": {"background": "#4a5070"},
}

st.title("RosMan – Roster Manager")

# ── Upload ────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader("📂 Upload DSNhanVien.csv", type=["csv"])
if not uploaded_file:
    st.info("Hãy upload file CSV có cột **FullName** và **Position** để bắt đầu.")
    st.stop()

df = pd.read_csv(uploaded_file)
df.columns = df.columns.str.strip()
if "FullName" not in df.columns or "Position" not in df.columns:
    st.error("CSV phải có cột: **FullName** và **Position**")
    st.stop()

employees = df[["FullName", "Position"]].copy()

# ── Dates ─────────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    start_date = st.date_input("📅 Start Date")
with c2:
    end_date = st.date_input("📅 End Date")

if not (start_date and end_date and start_date <= end_date):
    st.warning("Vui lòng chọn khoảng ngày hợp lệ.")
    st.stop()

dates = []
cur = start_date
while cur <= end_date:
    dates.append(cur)
    cur += timedelta(days=1)

# ── DataFrame ─────────────────────────────────────────────────────────────────
roster_df = employees.copy()
for d in dates:
    lbl = d.strftime("%d-%m")
    roster_df[f"{lbl}_M"] = ""
    roster_df[f"{lbl}_C"] = ""

# ── Widths ────────────────────────────────────────────────────────────────────
max_name_len = int(employees["FullName"].str.len().max()) if len(employees) else 15
max_pos_len  = int(employees["Position"].str.len().max()) if len(employees) else 10
NAME_W = min(max(max_name_len * 8 + 24, 140), 250)
POS_W  = min(max(max_pos_len  * 8 + 24, 100), 200)

# ── JsCode: cell style (shift highlight) ─────────────────────────────────────
cell_style_js = JsCode(f"""
function(params) {{
    const v = (params.value || '').trim();
    const p = v.charAt(0).toUpperCase();
    const bgMap = {{
        'Q': '{SHIFT_BG["Q"]}',
        'S': '{SHIFT_BG["S"]}',
        'C': '{SHIFT_BG["C"]}',
        'B': '{SHIFT_BG["B"]}',
    }};
    const bg = bgMap[p];
    return {{
        backgroundColor: bg || 'transparent',
        color:           bg ? '{SHIFT_FG}' : '{TEXT_DIM}',
        fontWeight:      bg ? '700' : '400',
        display:         'flex',
        alignItems:      'center',
        justifyContent:  'center',
        fontSize:        '12px',
        padding:         '0',
    }};
}}
""")

text_style_js = JsCode(f"""
function(params) {{
    return {{
        color: '{TEXT_MAIN}', fontSize: '13px', padding: '0 10px',
        display: 'flex', alignItems: 'center',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
    }};
}}
""")

# ── JsCode: editable cho cột chiều (manager không edit) ──────────────────────
afternoon_editable_js = JsCode("""
function(params) {
    return !(params.data.Position || '').includes('Quản');
}
""")

# ── Build grid với GridOptionsBuilder (đảm bảo JsCode được register đúng) ────
gb = GridOptionsBuilder.from_dataframe(roster_df)

gb.configure_default_column(
    resizable=False, sortable=False, filter=False,
    suppressMenu=True, suppressMovable=True,
    width=CELL_SZ, minWidth=CELL_SZ, maxWidth=CELL_SZ,
    suppressSizeToFit=True,
    cellStyle=cell_style_js,
)

# Pinned cols — dùng configure_column để JsCode cellStyle được serialize đúng
gb.configure_column("FullName", header_name="Họ và Tên",
    pinned="left", width=NAME_W, minWidth=NAME_W, maxWidth=NAME_W,
    suppressSizeToFit=True, lockPinned=True, lockPosition=True,
    editable=False, cellStyle=text_style_js,
)
gb.configure_column("Position", header_name="Vị trí",
    pinned="left", width=POS_W, minWidth=POS_W, maxWidth=POS_W,
    suppressSizeToFit=True, lockPinned=True, lockPosition=True,
    editable=False, cellStyle=text_style_js,
)

# Date cols — configure từng cột qua builder để JsCode được xử lý đúng
for d in dates:
    lbl = d.strftime("%d-%m")

    # Cột sáng — dropdown options theo Position
    # Dùng values đầy đủ rồi filter bằng cellEditorParams JsCode
    morning_params = JsCode(f"""
    function(params) {{
        const pos = params.data.Position || '';
        if (pos.includes('Quản')) return {{ values: ['', 'Q1', 'Q2', 'Q3'] }};
        if (pos.includes('Phục')) return {{ values: ['', 'S1', 'S2', 'S3'] }};
        return {{ values: ['', 'B1', 'B2', 'B3'] }};
    }}
    """)

    afternoon_params = JsCode(f"""
    function(params) {{
        const pos = params.data.Position || '';
        if (pos.includes('Quản')) return {{ values: [''] }};
        if (pos.includes('Phục')) return {{ values: ['', 'C1', 'C2', 'C3'] }};
        return {{ values: ['', 'B4', 'B5', 'B6'] }};
    }}
    """)

    gb.configure_column(f"{lbl}_M",
        header_name=f"{lbl} ☀",
        width=CELL_SZ, minWidth=CELL_SZ, maxWidth=CELL_SZ,
        suppressSizeToFit=True,
        editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams=morning_params,
        cellStyle=cell_style_js,
    )
    gb.configure_column(f"{lbl}_C",
        header_name=f"{lbl} 🌙",
        width=CELL_SZ, minWidth=CELL_SZ, maxWidth=CELL_SZ,
        suppressSizeToFit=True,
        editable=afternoon_editable_js,
        cellEditor="agSelectCellEditor",
        cellEditorParams=afternoon_params,
        cellStyle=cell_style_js,
    )

gb.configure_grid_options(
    rowHeight=ROW_HEIGHT,
    headerHeight=HDR_H,
    domLayout="normal",
    suppressColumnVirtualisation=True,
    suppressAutoSize=True,
    suppressSizeColumnsToFit=True,
    suppressHorizontalScroll=False,
    suppressContextMenu=True,
    enableRangeSelection=True,
    stopEditingWhenCellsLoseFocus=True,
)

grid_options = gb.build()

# ── Inject column groups SAU KHI build ───────────────────────────────────────
# gb đã serialize JsCode đúng trong columnDefs dạng phẳng.
# Bây giờ ta wrap chúng vào group structure để có group header ngày.

built_defs = grid_options["columnDefs"]

# Tách pinned cols
pinned_defs = [c for c in built_defs if c.get("pinned") == "left"]

# Tách date cols thành dict để lookup nhanh
date_col_map = {}
for c in built_defs:
    f = c.get("field", "")
    if "_M" in f or "_C" in f:
        date_col_map[f] = c

# Tạo group defs — children lấy từ đã-serialized defs (JsCode đã đúng)
date_groups = []
for d in dates:
    lbl = d.strftime("%d-%m")
    child_m = date_col_map.get(f"{lbl}_M", {})
    child_c = date_col_map.get(f"{lbl}_C", {})
    # Đổi header của child thành chỉ icon (bỏ "dd-mm" vì group header đã có)
    child_m = dict(child_m); child_m["headerName"] = "☀"
    child_c = dict(child_c); child_c["headerName"] = "🌙"
    date_groups.append({
        "headerName": lbl,
        "marryChildren": True,
        "suppressMenu": True,
        "children": [child_m, child_c],
    })

# Pinned cols cũng cần được wrap vào group để 2-row header align đều
pinned_group = {
    "headerName": "",
    "marryChildren": True,
    "children": pinned_defs,
}

grid_options["columnDefs"] = [pinned_group] + date_groups

# ── Render ────────────────────────────────────────────────────────────────────
st.subheader("📋 Roster")
table_height = GRP_H + HDR_H + len(roster_df) * ROW_HEIGHT + 24

grid_response = AgGrid(
    roster_df,
    gridOptions=grid_options,
    height=table_height,
    theme="balham-dark",
    custom_css=AGGRID_CSS,
    update_on=["cellValueChanged"],
    allow_unsafe_jscode=True,
    columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE,
    fit_columns_on_grid_load=False,
)

updated_df: pd.DataFrame = grid_response["data"]

# ── Export ────────────────────────────────────────────────────────────────────
st.markdown("---")
col_exp1, col_exp2 = st.columns([1, 4])

with col_exp1:
    if st.button("📥 Export to Excel"):
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
        st.session_state["excel_ready"] = output.getvalue()

if "excel_ready" in st.session_state:
    with col_exp2:
        st.download_button(
            label="⬇️ Download LichLamViec.xlsx",
            data=st.session_state["excel_ready"],
            file_name="LichLamViec.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
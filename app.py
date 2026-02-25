import streamlit as st
import pandas as pd
from datetime import timedelta
from io import BytesIO

from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from st_aggrid.shared import ColumnsAutoSizeMode

st.set_page_config(layout="wide", page_title="RosMan – Roster Manager")

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
    # ── canh giữa header labels ──
    ".ag-header-cell-label": {
        "justify-content": "center !important",
        "padding": "0 !important",
    },
    ".ag-header-group-cell-label": {
        "justify-content": "center !important",
        "padding": "0 !important",
    },
    ".ag-header-cell-text": {"text-align": "center !important"},
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
    # Dropdown popup
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

uploaded_file = st.file_uploader("📂 Upload DSNhanVien.csv", type=["csv"])
if not uploaded_file:
    st.info("Hãy upload file DSNhanVien.csv  để bắt đầu.")
    st.stop()

df = pd.read_csv(uploaded_file)
df.columns = df.columns.str.strip()
if "FullName" not in df.columns or "Position" not in df.columns:
    st.error("CSV phải có cột: **FullName** và **Position**")
    st.stop()

employees = df[["FullName", "Position"]].copy()

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

roster_df = employees.copy()
for d in dates:
    lbl = d.strftime("%d-%m")
    roster_df[f"{lbl}_M"] = ""
    roster_df[f"{lbl}_C"] = ""

max_name_len = int(employees["FullName"].str.len().max()) if len(employees) else 15
max_pos_len  = int(employees["Position"].str.len().max()) if len(employees) else 10
NAME_W = min(max(max_name_len * 8 + 24, 140), 250)
POS_W  = min(max(max_pos_len  * 8 + 24, 100), 200)

# ── JsCode ────────────────────────────────────────────────────────────────────

# Cell style: highlight ca + canh giữa
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

# Cell style pinned cols: canh giữa cả chiều ngang lẫn dọc
center_style_js = JsCode(f"""
function(params) {{
    return {{
        color:          '{TEXT_MAIN}',
        fontSize:       '13px',
        padding:        '0',
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'center',
        textAlign:      'center',
        whiteSpace:     'nowrap',
        overflow:       'hidden',
        textOverflow:   'ellipsis',
    }};
}}
""")

morning_renderer_js = JsCode("""
class MorningRenderer {
    init(params) {
        const pos = (params.data && params.data.Position) ? params.data.Position : '';
        const normPos = pos
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
        const bgMap = {Q:'#1b4f8a', S:'#1a5c30', C:'#6b5000', B:'#7a2800'};
        let options;
        if      (normPos.includes('quan')) options = ['', 'Q1', 'Q2', 'Q3'];
        else if (normPos.includes('phuc')) options = ['', 'S1', 'S2', 'S3'];
        else                           options = ['', 'B1', 'B2', 'B3'];

        const current = params.value || '';
        const p = current.trim().charAt(0).toUpperCase();
        const bg = bgMap[p] || '#1a1d27';
        const fg = bgMap[p] ? '#fff' : '#e0e4f0';

        this.select = document.createElement('select');
        this.select.style.cssText =
            'width:100%;height:100%;border:none;outline:none;' +
            'font-size:12px;font-weight:600;text-align:center;' +
            'cursor:pointer;padding:0;' +
            'background:' + bg + ';color:' + fg + ';';

        options.forEach(function(opt) {
            const o = document.createElement('option');
            o.value = opt; o.text = opt;
            if (opt === current) o.selected = true;
            this.select.appendChild(o);
        }, this);

        this.select.addEventListener('change', function() {
            const newVal = this.select.value;
            params.node.setDataValue(params.column.getId(), newVal);
            const bg2 = bgMap[newVal.trim().charAt(0).toUpperCase()];
            this.select.style.background = bg2 || '#1a1d27';
            this.select.style.color = bg2 ? '#fff' : '#e0e4f0';
        }.bind(this));

        this.select.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    getGui() { return this.select; }
    refresh(params) {
        const bgMap = {Q:'#1b4f8a', S:'#1a5c30', C:'#6b5000', B:'#7a2800'};
        const v = params.value || '';
        this.select.value = v;
        const bg = bgMap[v.trim().charAt(0).toUpperCase()];
        this.select.style.background = bg || '#1a1d27';
        this.select.style.color = bg ? '#fff' : '#e0e4f0';
        return true;
    }
    destroy() {}
}
""")

afternoon_renderer_js = JsCode("""
class AfternoonRenderer {
    init(params) {
        const pos = (params.data && params.data.Position) ? params.data.Position : '';
        const normPos = pos
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase();
        const bgMap = {Q:'#1b4f8a', S:'#1a5c30', C:'#6b5000', B:'#7a2800'};

        // Manager: ô chiều hiển thị nền tối, không cho chọn
        if (normPos.includes('quan')) {
            this.el = document.createElement('div');
            this.el.style.cssText = 'width:100%;height:100%;background:#12151f;';
            return;
        }

        let options;
        if (normPos.includes('phuc')) options = ['', 'C1', 'C2', 'C3'];
        else                       options = ['', 'B4', 'B5', 'B6'];

        const current = params.value || '';
        const p = current.trim().charAt(0).toUpperCase();
        const bg = bgMap[p] || '#1a1d27';
        const fg = bgMap[p] ? '#fff' : '#e0e4f0';

        this.el = document.createElement('select');
        this.el.style.cssText =
            'width:100%;height:100%;border:none;outline:none;' +
            'font-size:12px;font-weight:600;text-align:center;' +
            'cursor:pointer;padding:0;' +
            'background:' + bg + ';color:' + fg + ';';

        options.forEach(function(opt) {
            const o = document.createElement('option');
            o.value = opt; o.text = opt;
            if (opt === current) o.selected = true;
            this.el.appendChild(o);
        }, this);

        this.el.addEventListener('change', function() {
            const newVal = this.el.value;
            params.node.setDataValue(params.column.getId(), newVal);
            const bg2 = bgMap[newVal.trim().charAt(0).toUpperCase()];
            this.el.style.background = bg2 || '#1a1d27';
            this.el.style.color = bg2 ? '#fff' : '#e0e4f0';
        }.bind(this));

        this.el.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    getGui() { return this.el; }
    refresh(params) {
        if (!this.el || this.el.tagName !== 'SELECT') return true;
        const bgMap = {Q:'#1b4f8a', S:'#1a5c30', C:'#6b5000', B:'#7a2800'};
        const v = params.value || '';
        this.el.value = v;
        const bg = bgMap[v.trim().charAt(0).toUpperCase()];
        this.el.style.background = bg || '#1a1d27';
        this.el.style.color = bg ? '#fff' : '#e0e4f0';
        return true;
    }
    destroy() {}
}
""")

# ── GridOptionsBuilder ────────────────────────────────────────────────────────
gb = GridOptionsBuilder.from_dataframe(roster_df)

gb.configure_default_column(
    resizable=False, sortable=False, filter=False,
    suppressMenu=True, suppressMovable=True,
    width=CELL_SZ, minWidth=CELL_SZ, maxWidth=CELL_SZ,
    suppressSizeToFit=True,
    editable=False,   # tất cả mặc định không edit, select dùng renderer
)

gb.configure_column("FullName", header_name="Họ và Tên",
    pinned="left", width=NAME_W, minWidth=NAME_W, maxWidth=NAME_W,
    suppressSizeToFit=True, lockPinned=True, lockPosition=True,
    editable=False, cellStyle=center_style_js,
)
gb.configure_column("Position", header_name="Vị trí",
    pinned="left", width=POS_W, minWidth=POS_W, maxWidth=POS_W,
    suppressSizeToFit=True, lockPinned=True, lockPosition=True,
    editable=False, cellStyle=center_style_js,
)

for d in dates:
    lbl = d.strftime("%d-%m")
    gb.configure_column(f"{lbl}_M",
        header_name="☀",
        width=CELL_SZ, minWidth=CELL_SZ, maxWidth=CELL_SZ,
        suppressSizeToFit=True,
        editable=False,
        cellRenderer=morning_renderer_js,
        cellStyle=cell_style_js,
    )
    gb.configure_column(f"{lbl}_C",
        header_name="🌙",
        width=CELL_SZ, minWidth=CELL_SZ, maxWidth=CELL_SZ,
        suppressSizeToFit=True,
        editable=False,
        cellRenderer=afternoon_renderer_js,
        cellStyle=cell_style_js,
    )

gb.configure_grid_options(
    rowHeight=ROW_HEIGHT,
    headerHeight=HDR_H,
    groupHeaderHeight=GRP_H,
    domLayout="normal",
    suppressColumnVirtualisation=True,
    suppressAutoSize=True,
    suppressSizeColumnsToFit=True,
    suppressHorizontalScroll=False,
    suppressContextMenu=True,
    stopEditingWhenCellsLoseFocus=True,
)

grid_options = gb.build()

# ── Patch: wrap vào group structure ──────────────────────────────────────────
built_defs = grid_options["columnDefs"]
pinned_defs = [c for c in built_defs if c.get("pinned") == "left"]
date_col_map = {
    c["field"]: c
    for c in built_defs
    if any(c.get("field", "").endswith(s) for s in ["_M", "_C"])
}

date_groups = []
for d in dates:
    lbl = d.strftime("%d-%m")
    cm = dict(date_col_map.get(f"{lbl}_M", {}))
    cc = dict(date_col_map.get(f"{lbl}_C", {}))
    date_groups.append({
        "headerName": lbl,
        "marryChildren": True,
        "suppressMenu": True,
        "children": [cm, cc],
    })

pinned_group = {
    "headerName": "",
    "marryChildren": True,
    "children": pinned_defs,
}

grid_options["columnDefs"] = [pinned_group] + date_groups

# ── Render ────────────────────────────────────────────────────────────────────
st.subheader("📋 Roster")
MAX_TABLE_HEIGHT = 760
table_height = min(GRP_H + HDR_H + len(roster_df) * ROW_HEIGHT + 24, MAX_TABLE_HEIGHT)

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

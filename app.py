from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "roster.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-in-production"
LOGIN_USERNAME = "duylb"
LOGIN_PASSWORD = "2026"
SUPPORTED_LANGS = {"en", "vi"}
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "RosMan - Rostering Management",
        "brand_sub": "Rostering Management",
        "nav_dashboard": "Dashboard",
        "nav_staff": "Staff",
        "nav_shifts": "Shifts",
        "nav_availability": "Availability",
        "nav_roster": "Roster",
        "nav_data_io": "Data I/O",
        "logout": "Logout",
        "workspace": "Workspace",
        "page_dashboard": "Dashboard",
        "page_staff": "Staff",
        "page_shifts": "Shifts",
        "page_availability": "Availability",
        "page_roster": "Roster",
        "page_data": "Data Import / Export",
        "lang_toggle": "Tiếng Việt",
        "login_title": "Login",
        "login_hint": "Enter your credentials to access the roster management app.",
        "username": "Username",
        "password": "Password",
        "btn_login": "Login",
        "today": "Today",
        "active_staff": "Active Staff",
        "shift_templates": "Shift Templates",
        "assignments_today": "Assignments Today",
        "unavailable_today": "Unavailable Today",
        "add_staff": "Add Staff",
        "name": "Name",
        "role": "Role",
        "email": "Email",
        "add": "Add",
        "import_staff_csv": "Import Staff CSV",
        "import_staff_hint": "Format: skip header, column A = staff name, B = role, C = email.",
        "csv_file": "CSV File",
        "import": "Import",
        "staff_list": "Staff List",
        "status": "Status",
        "action": "Action",
        "active": "Active",
        "inactive": "Inactive",
        "edit": "Edit",
        "disable": "Disable",
        "enable": "Enable",
        "edit_staff": "Edit Staff",
        "save": "Save",
        "cancel": "Cancel",
        "add_shift_template": "Add Shift Template",
        "shift_name": "Shift Name",
        "start_time": "Start Time",
        "end_time": "End Time",
        "required_staff": "Required Staff",
        "time": "Time",
        "add_leave_availability": "Add Leave / Availability",
        "staff": "Staff",
        "select_staff": "Select staff",
        "start_date": "Start Date",
        "end_date": "End Date",
        "leave": "Leave",
        "unavailable": "Unavailable",
        "notes": "Notes",
        "add_entry": "Add Entry",
        "add_preferred_shifts": "Add Preferred Shifts (Date Range)",
        "preferred_shifts_multi": "Preferred Shifts (hold Ctrl/Cmd to select multiple)",
        "add_preferences": "Add Preferences",
        "preferred_shift_entries": "Preferred Shift Entries",
        "preferred_shift": "Preferred Shift",
        "date_range": "Date Range",
        "remove": "Remove",
        "no_shift_preferences": "No shift preferences yet.",
        "availability_entries": "Availability Entries",
        "no_availability_entries": "No availability entries yet.",
        "to": "to",
        "roster": "Roster",
        "date": "Date",
        "load": "Load",
        "shift": "Shift",
        "select_shift": "Select shift",
        "assign": "Assign",
        "weekly_auto_scheduling": "Weekly Auto-Scheduling",
        "week_start_monday": "Week Start (Monday)",
        "generate_week": "Generate Week",
        "auto_schedule_rule": "Rule: fills each shift's required headcount using active staff, prioritizes preferred shifts for that date, skips leave/unavailable entries, then balances by least assignments.",
        "assignments_for": "Assignments for",
        "no_assignments_for_date": "No assignments for this date.",
        "csv_export": "CSV Export",
        "export_one_dataset": "Export one dataset at a time.",
        "export_staff": "Export Staff",
        "export_shifts": "Export Shifts",
        "export_roster": "Export Roster",
        "export_availability": "Export Availability",
        "csv_import": "CSV Import",
        "import_headers_hint": "Required headers depend on dataset. Keep date format as YYYY-MM-DD.",
        "dataset": "Dataset",
        "assignments": "Assignments",
        "availability": "Availability",
        "mode": "Mode",
        "append_mode": "Append to existing data",
        "replace_mode": "Replace existing dataset",
        "import_csv": "Import CSV",
        "invalid_login": "Invalid username or password.",
    },
    "vi": {
        "app_title": "RosMan - Quản Lý Phân Ca",
        "brand_sub": "Quản Lý Phân Ca",
        "nav_dashboard": "Bảng Điều Khiển",
        "nav_staff": "Nhân Sự",
        "nav_shifts": "Ca Làm",
        "nav_availability": "Lịch Trực",
        "nav_roster": "Lịch Phân Ca",
        "nav_data_io": "Nhập/Xuất Dữ Liệu",
        "logout": "Đăng Xuất",
        "workspace": "Không Gian Làm Việc",
        "page_dashboard": "Bảng Điều Khiển",
        "page_staff": "Nhân Sự",
        "page_shifts": "Ca Làm",
        "page_availability": "Lịch Trực",
        "page_roster": "Lịch Phân Ca",
        "page_data": "Nhập / Xuất Dữ Liệu",
        "lang_toggle": "English",
        "login_title": "Đăng Nhập",
        "login_hint": "Nhập thông tin đăng nhập để truy cập ứng dụng quản lý phân ca.",
        "username": "Tên Đăng Nhập",
        "password": "Mật Khẩu",
        "btn_login": "Đăng Nhập",
        "today": "Hôm Nay",
        "active_staff": "Nhân Sự Đang Hoạt Động",
        "shift_templates": "Mẫu Ca",
        "assignments_today": "Phân Ca Hôm Nay",
        "unavailable_today": "Không Sẵn Sàng Hôm Nay",
        "add_staff": "Thêm Nhân Sự",
        "name": "Tên",
        "role": "Vai Trò",
        "email": "Email",
        "add": "Thêm",
        "import_staff_csv": "Nhập CSV Nhân Sự",
        "import_staff_hint": "Định dạng: bỏ qua header, cột A = tên, B = vai trò, C = email.",
        "csv_file": "Tệp CSV",
        "import": "Nhập",
        "staff_list": "Danh Sách Nhân Sự",
        "status": "Trạng Thái",
        "action": "Thao Tác",
        "active": "Hoạt Động",
        "inactive": "Ngừng Hoạt Động",
        "edit": "Sửa",
        "disable": "Tắt",
        "enable": "Bật",
        "edit_staff": "Sửa Nhân Sự",
        "save": "Lưu",
        "cancel": "Hủy",
        "add_shift_template": "Thêm Mẫu Ca",
        "shift_name": "Tên Ca",
        "start_time": "Giờ Bắt Đầu",
        "end_time": "Giờ Kết Thúc",
        "required_staff": "Số Nhân Sự Cần",
        "time": "Thời Gian",
        "add_leave_availability": "Thêm Nghỉ / Khả Năng Làm Việc",
        "staff": "Nhân Sự",
        "select_staff": "Chọn nhân sự",
        "start_date": "Ngày Bắt Đầu",
        "end_date": "Ngày Kết Thúc",
        "leave": "Nghỉ",
        "unavailable": "Không Sẵn Sàng",
        "notes": "Ghi Chú",
        "add_entry": "Thêm",
        "add_preferred_shifts": "Thêm Ca Ưu Tiên (Theo Khoảng Ngày)",
        "preferred_shifts_multi": "Ca Ưu Tiên (giữ Ctrl/Cmd để chọn nhiều)",
        "add_preferences": "Thêm Ưu Tiên",
        "preferred_shift_entries": "Danh Sách Ca Ưu Tiên",
        "preferred_shift": "Ca Ưu Tiên",
        "date_range": "Khoảng Ngày",
        "remove": "Xóa",
        "no_shift_preferences": "Chưa có ca ưu tiên.",
        "availability_entries": "Danh Sách Khả Năng Làm Việc",
        "no_availability_entries": "Chưa có dữ liệu khả năng làm việc.",
        "to": "đến",
        "roster": "Lịch Phân Ca",
        "date": "Ngày",
        "load": "Tải",
        "shift": "Ca",
        "select_shift": "Chọn ca",
        "assign": "Phân Ca",
        "weekly_auto_scheduling": "Tự Động Phân Ca Theo Tuần",
        "week_start_monday": "Ngày Bắt Đầu Tuần (Thứ Hai)",
        "generate_week": "Tạo Lịch Tuần",
        "auto_schedule_rule": "Quy tắc: điền đủ số lượng cho mỗi ca bằng nhân sự đang hoạt động, ưu tiên ca mong muốn theo ngày, bỏ qua nhân sự nghỉ/không sẵn sàng, sau đó cân bằng theo số ca thấp nhất.",
        "assignments_for": "Phân Ca Cho",
        "no_assignments_for_date": "Không có phân ca cho ngày này.",
        "csv_export": "Xuất CSV",
        "export_one_dataset": "Xuất từng bộ dữ liệu một.",
        "export_staff": "Xuất Nhân Sự",
        "export_shifts": "Xuất Ca Làm",
        "export_roster": "Xuất Lịch Phân Ca",
        "export_availability": "Xuất Khả Năng Làm Việc",
        "csv_import": "Nhập CSV",
        "import_headers_hint": "Header bắt buộc tùy theo bộ dữ liệu. Giữ định dạng ngày YYYY-MM-DD.",
        "dataset": "Bộ Dữ Liệu",
        "assignments": "Phân Ca",
        "availability": "Khả Năng Làm Việc",
        "mode": "Chế Độ",
        "append_mode": "Thêm vào dữ liệu hiện có",
        "replace_mode": "Thay thế toàn bộ bộ dữ liệu",
        "import_csv": "Nhập CSV",
        "invalid_login": "Sai tên đăng nhập hoặc mật khẩu.",
    },
}


def get_lang() -> str:
    lang = session.get("lang", "en")
    return lang if lang in SUPPORTED_LANGS else "en"


def t(key: str) -> str:
    lang = get_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def require_login() -> Any:
    if request.endpoint is None:
        return None
    if request.endpoint in {"login", "set_language", "static"}:
        return None
    if session.get("is_authenticated"):
        return None

    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("login", next=next_url))


@app.context_processor
def inject_translation_helpers() -> dict[str, Any]:
    return {"t": t, "lang": get_lang()}


def parse_iso_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def to_minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def ranges_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    a_start = to_minutes(start_a)
    a_end = to_minutes(end_a)
    b_start = to_minutes(start_b)
    b_end = to_minutes(end_b)
    return a_start < b_end and b_start < a_end


def migrate_roster_assignments_for_split_shifts(db: sqlite3.Connection) -> None:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'roster_assignments'"
    ).fetchone()
    if row is None or row["sql"] is None:
        return

    sql_text = row["sql"].replace("\n", " ").replace("  ", " ")
    if "UNIQUE(roster_date, staff_id, shift_id)" in sql_text:
        return
    if "UNIQUE(roster_date, staff_id)" not in sql_text:
        return

    db.executescript(
        """
        CREATE TABLE roster_assignments_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roster_date TEXT NOT NULL,
            staff_id INTEGER NOT NULL,
            shift_id INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            FOREIGN KEY (shift_id) REFERENCES shift_templates(id) ON DELETE CASCADE,
            UNIQUE(roster_date, staff_id, shift_id)
        );

        INSERT INTO roster_assignments_new (id, roster_date, staff_id, shift_id, notes)
        SELECT id, roster_date, staff_id, shift_id, notes
        FROM roster_assignments;

        DROP TABLE roster_assignments;
        ALTER TABLE roster_assignments_new RENAME TO roster_assignments;
        """
    )


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shift_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            required_staff INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS roster_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roster_date TEXT NOT NULL,
            staff_id INTEGER NOT NULL,
            shift_id INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            FOREIGN KEY (shift_id) REFERENCES shift_templates(id) ON DELETE CASCADE,
            UNIQUE(roster_date, staff_id, shift_id)
        );

        CREATE TABLE IF NOT EXISTS staff_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS staff_shift_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            shift_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            FOREIGN KEY (shift_id) REFERENCES shift_templates(id) ON DELETE CASCADE
        );
        """
    )
    migrate_roster_assignments_for_split_shifts(db)
    db.commit()


def csv_response(filename: str, headers: list[str], rows: list[sqlite3.Row]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[h] for h in headers])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/login", methods=["GET", "POST"])
def login() -> str | Any:
    if session.get("is_authenticated"):
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next", "")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_form = request.form.get("next", "").strip()
        if next_form:
            next_url = next_form

        if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
            session["is_authenticated"] = True
            session["username"] = username
            if not next_url.startswith("/"):
                next_url = url_for("dashboard")
            return redirect(next_url or url_for("dashboard"))

        flash(t("invalid_login"), "error")

    return render_template("login.html", next_url=next_url)


@app.post("/set-language")
def set_language() -> Any:
    lang = request.form.get("lang", "en").strip().lower()
    if lang in SUPPORTED_LANGS:
        session["lang"] = lang
    next_url = request.form.get("next", "").strip()
    if not next_url.startswith("/"):
        next_url = request.referrer or url_for("dashboard")
    return redirect(next_url)


@app.post("/logout")
def logout() -> Any:
    session.clear()
    return redirect(url_for("login"))


def auto_schedule_week(db: sqlite3.Connection, week_start: date) -> tuple[int, int, int]:
    staff_rows = db.execute(
        "SELECT id, name FROM staff WHERE active = 1 ORDER BY name"
    ).fetchall()
    shift_rows = db.execute(
        "SELECT id, start_time, end_time, required_staff FROM shift_templates ORDER BY start_time"
    ).fetchall()

    if not staff_rows or not shift_rows:
        return 0, 0, 0

    week_end = week_start + timedelta(days=6)
    recent_start = week_start - timedelta(days=28)
    week_start_str = week_start.isoformat()
    week_end_str = week_end.isoformat()

    recent_counts = {
        row["staff_id"]: row["c"]
        for row in db.execute(
            """
            SELECT staff_id, COUNT(*) AS c
            FROM roster_assignments
            WHERE roster_date BETWEEN ? AND ?
            GROUP BY staff_id
            """,
            (recent_start.isoformat(), week_end.isoformat()),
        ).fetchall()
    }
    week_counts: dict[int, int] = {row["id"]: 0 for row in staff_rows}
    preference_rows = db.execute(
        """
        SELECT staff_id, shift_id, start_date, end_date
        FROM staff_shift_preferences
        WHERE start_date <= ?
          AND end_date >= ?
        """,
        (week_end_str, week_start_str),
    ).fetchall()

    added = 0
    unfilled = 0

    for offset in range(7):
        day_value = week_start + timedelta(days=offset)
        day_str = day_value.isoformat()

        blocked = {
            row["staff_id"]
            for row in db.execute(
                """
                SELECT DISTINCT staff_id
                FROM staff_availability
                WHERE status IN ('leave', 'unavailable')
                  AND start_date <= ?
                  AND end_date >= ?
                """,
                (day_str, day_str),
            ).fetchall()
        }

        assigned_ranges: dict[int, list[tuple[str, str]]] = {}
        for row in db.execute(
            """
            SELECT ra.staff_id, st.start_time, st.end_time
            FROM roster_assignments ra
            JOIN shift_templates st ON st.id = ra.shift_id
            WHERE ra.roster_date = ?
            """,
            (day_str,),
        ).fetchall():
            assigned_ranges.setdefault(row["staff_id"], []).append(
                (row["start_time"], row["end_time"])
            )

        shift_fill = {
            row["shift_id"]: row["c"]
            for row in db.execute(
                """
                SELECT shift_id, COUNT(*) AS c
                FROM roster_assignments
                WHERE roster_date = ?
                GROUP BY shift_id
                """,
                (day_str,),
            ).fetchall()
        }

        for shift in shift_rows:
            open_slots = max(0, shift["required_staff"] - shift_fill.get(shift["id"], 0))
            preferred_for_shift = {
                pref["staff_id"]
                for pref in preference_rows
                if pref["shift_id"] == shift["id"]
                and pref["start_date"] <= day_str
                and pref["end_date"] >= day_str
            }
            for _ in range(open_slots):
                eligible = [
                    s
                    for s in staff_rows
                    if s["id"] not in blocked
                    and all(
                        not ranges_overlap(
                            shift["start_time"],
                            shift["end_time"],
                            existing_start,
                            existing_end,
                        )
                        for existing_start, existing_end in assigned_ranges.get(s["id"], [])
                    )
                ]
                if not eligible:
                    unfilled += 1
                    continue

                chosen = min(
                    eligible,
                    key=lambda s: (
                        0 if s["id"] in preferred_for_shift else 1,
                        week_counts.get(s["id"], 0),
                        recent_counts.get(s["id"], 0),
                        s["name"],
                    ),
                )

                db.execute(
                    """
                    INSERT INTO roster_assignments (roster_date, staff_id, shift_id, notes)
                    VALUES (?, ?, ?, ?)
                    """,
                    (day_str, chosen["id"], shift["id"], "Auto-scheduled"),
                )
                assigned_ranges.setdefault(chosen["id"], []).append(
                    (shift["start_time"], shift["end_time"])
                )
                week_counts[chosen["id"]] = week_counts.get(chosen["id"], 0) + 1
                recent_counts[chosen["id"]] = recent_counts.get(chosen["id"], 0) + 1
                shift_fill[shift["id"]] = shift_fill.get(shift["id"], 0) + 1
                added += 1

    db.commit()
    return added, unfilled, 1


@app.route("/")
def dashboard() -> str:
    db = get_db()
    today = date.today().isoformat()

    staff_count = db.execute("SELECT COUNT(*) AS c FROM staff WHERE active = 1").fetchone()["c"]
    shift_count = db.execute("SELECT COUNT(*) AS c FROM shift_templates").fetchone()["c"]
    assignments_today = db.execute(
        "SELECT COUNT(*) AS c FROM roster_assignments WHERE roster_date = ?", (today,)
    ).fetchone()["c"]
    unavailable_today = db.execute(
        """
        SELECT COUNT(DISTINCT staff_id) AS c
        FROM staff_availability
        WHERE status IN ('leave', 'unavailable')
          AND start_date <= ?
          AND end_date >= ?
        """,
        (today, today),
    ).fetchone()["c"]

    return render_template(
        "dashboard.html",
        today=today,
        staff_count=staff_count,
        shift_count=shift_count,
        assignments_today=assignments_today,
        unavailable_today=unavailable_today,
    )


@app.route("/staff", methods=["GET", "POST"])
def staff() -> str:
    db = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not role:
            flash("Name and role are required.", "error")
        else:
            db.execute(
                "INSERT INTO staff (name, role, email) VALUES (?, ?, ?)",
                (name, role, email or None),
            )
            db.commit()
            flash("Staff member added.", "success")
            return redirect(url_for("staff"))

    rows = db.execute(
        "SELECT id, name, role, email, active, created_at FROM staff ORDER BY active DESC, name"
    ).fetchall()
    return render_template("staff.html", staff=rows)


@app.post("/staff/<int:staff_id>/toggle")
def toggle_staff(staff_id: int) -> Any:
    db = get_db()
    row = db.execute("SELECT active FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if row is None:
        flash("Staff member not found.", "error")
    else:
        new_value = 0 if row["active"] else 1
        db.execute("UPDATE staff SET active = ? WHERE id = ?", (new_value, staff_id))
        db.commit()
        flash("Staff status updated.", "success")
    return redirect(url_for("staff"))


@app.post("/staff/<int:staff_id>/edit")
def edit_staff(staff_id: int) -> Any:
    db = get_db()
    row = db.execute("SELECT id FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if row is None:
        flash("Staff member not found.", "error")
        return redirect(url_for("staff"))

    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()

    if not name or not role:
        flash("Name and role are required.", "error")
        return redirect(url_for("staff"))

    db.execute(
        "UPDATE staff SET name = ?, role = ?, email = ? WHERE id = ?",
        (name, role, email or None, staff_id),
    )
    db.commit()
    flash("Staff information updated.", "success")
    return redirect(url_for("staff"))


@app.post("/staff/import")
def import_staff_csv() -> Any:
    db = get_db()
    file_obj = request.files.get("csv_file")

    if not file_obj or not file_obj.filename:
        flash("Choose a CSV file to import.", "error")
        return redirect(url_for("staff"))

    try:
        content = file_obj.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("CSV must be UTF-8 encoded.", "error")
        return redirect(url_for("staff"))

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if len(rows) <= 1:
        flash("CSV must include a header row and at least one staff row.", "error")
        return redirect(url_for("staff"))

    added = 0
    skipped = 0
    for row in rows[1:]:
        # Expected structure: A=name, B=role, C=email
        name = (row[0] if len(row) > 0 else "").strip()
        role = (row[1] if len(row) > 1 else "").strip()
        email = (row[2] if len(row) > 2 else "").strip()

        if not name or not role:
            skipped += 1
            continue

        db.execute(
            "INSERT INTO staff (name, role, email) VALUES (?, ?, ?)",
            (name, role, email or None),
        )
        added += 1

    db.commit()
    flash(f"Staff import finished: {added} rows added, {skipped} rows skipped.", "success")
    return redirect(url_for("staff"))


@app.route("/shifts", methods=["GET", "POST"])
def shifts() -> str:
    db = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        required_staff_raw = request.form.get("required_staff", "1").strip()

        try:
            required_staff = max(1, int(required_staff_raw))
        except ValueError:
            required_staff = 1

        if not name or not start_time or not end_time:
            flash("Name, start time, and end time are required.", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO shift_templates (name, start_time, end_time, required_staff) VALUES (?, ?, ?, ?)",
                    (name, start_time, end_time, required_staff),
                )
                db.commit()
                flash("Shift template added.", "success")
                return redirect(url_for("shifts"))
            except sqlite3.IntegrityError:
                flash("Shift name must be unique.", "error")

    rows = db.execute(
        "SELECT id, name, start_time, end_time, required_staff FROM shift_templates ORDER BY start_time"
    ).fetchall()
    return render_template("shifts.html", shifts=rows)


@app.route("/availability", methods=["GET", "POST"])
def availability() -> str:
    db = get_db()
    today = date.today().isoformat()

    if request.method == "POST":
        staff_id = request.form.get("staff_id", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        status = request.form.get("status", "leave").strip()
        notes = request.form.get("notes", "").strip()

        start_obj = parse_iso_date(start_date)
        end_obj = parse_iso_date(end_date)

        if not staff_id or not start_obj or not end_obj:
            flash("Staff, start date, and end date are required.", "error")
        elif end_obj < start_obj:
            flash("End date must be on or after start date.", "error")
        elif status not in {"leave", "unavailable"}:
            flash("Invalid availability status.", "error")
        else:
            db.execute(
                """
                INSERT INTO staff_availability (staff_id, start_date, end_date, status, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (int(staff_id), start_date, end_date, status, notes or None),
            )
            db.commit()
            flash("Availability entry added.", "success")
            return redirect(url_for("availability"))

    staff_rows = db.execute("SELECT id, name, role FROM staff ORDER BY name").fetchall()
    availability_rows = db.execute(
        """
        SELECT
            sa.id,
            sa.start_date,
            sa.end_date,
            sa.status,
            sa.notes,
            s.name AS staff_name,
            s.role AS staff_role
        FROM staff_availability sa
        JOIN staff s ON s.id = sa.staff_id
        ORDER BY sa.start_date DESC, s.name
        """
    ).fetchall()
    shift_rows = db.execute(
        "SELECT id, name, start_time, end_time FROM shift_templates ORDER BY start_time"
    ).fetchall()
    preference_rows = db.execute(
        """
        SELECT
            sp.id,
            sp.start_date,
            sp.end_date,
            sp.notes,
            s.name AS staff_name,
            s.role AS staff_role,
            st.name AS shift_name,
            st.start_time,
            st.end_time
        FROM staff_shift_preferences sp
        JOIN staff s ON s.id = sp.staff_id
        JOIN shift_templates st ON st.id = sp.shift_id
        ORDER BY sp.start_date DESC, s.name, st.start_time
        """
    ).fetchall()

    return render_template(
        "availability.html",
        today=today,
        staff_rows=staff_rows,
        shift_rows=shift_rows,
        availability_rows=availability_rows,
        preference_rows=preference_rows,
    )


@app.post("/availability/<int:entry_id>/delete")
def delete_availability(entry_id: int) -> Any:
    db = get_db()
    db.execute("DELETE FROM staff_availability WHERE id = ?", (entry_id,))
    db.commit()
    flash("Availability entry removed.", "success")
    return redirect(url_for("availability"))


@app.post("/availability/preferences")
def add_shift_preference() -> Any:
    db = get_db()
    staff_id = request.form.get("staff_id", "").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    shift_ids = request.form.getlist("shift_ids")
    notes = request.form.get("notes", "").strip()

    start_obj = parse_iso_date(start_date)
    end_obj = parse_iso_date(end_date)

    if not staff_id or not start_obj or not end_obj:
        flash("Staff, start date, and end date are required for shift preferences.", "error")
        return redirect(url_for("availability"))
    if end_obj < start_obj:
        flash("Preference end date must be on or after start date.", "error")
        return redirect(url_for("availability"))
    if not shift_ids:
        flash("Select at least one preferred shift.", "error")
        return redirect(url_for("availability"))

    added = 0
    for shift_id_raw in shift_ids:
        try:
            shift_id = int(shift_id_raw)
        except ValueError:
            continue
        db.execute(
            """
            INSERT INTO staff_shift_preferences (staff_id, shift_id, start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(staff_id), shift_id, start_date, end_date, notes or None),
        )
        added += 1
    db.commit()
    flash(f"Added {added} preferred shift entries.", "success")
    return redirect(url_for("availability"))


@app.post("/availability/preferences/<int:preference_id>/delete")
def delete_shift_preference(preference_id: int) -> Any:
    db = get_db()
    db.execute("DELETE FROM staff_shift_preferences WHERE id = ?", (preference_id,))
    db.commit()
    flash("Shift preference removed.", "success")
    return redirect(url_for("availability"))


@app.route("/roster", methods=["GET", "POST"])
def roster() -> str:
    db = get_db()

    selected_date = request.values.get("roster_date", date.today().isoformat())
    selected_obj = parse_iso_date(selected_date) or date.today()

    if request.method == "POST":
        staff_id = request.form.get("staff_id", "").strip()
        shift_id = request.form.get("shift_id", "").strip()
        notes = request.form.get("notes", "").strip()

        if not staff_id or not shift_id:
            flash("Staff and shift are required.", "error")
        else:
            try:
                staff_id_int = int(staff_id)
                shift_id_int = int(shift_id)
            except ValueError:
                flash("Invalid staff or shift.", "error")
                return redirect(url_for("roster", roster_date=selected_date))

            target_shift = db.execute(
                "SELECT start_time, end_time FROM shift_templates WHERE id = ?",
                (shift_id_int,),
            ).fetchone()
            if target_shift is None:
                flash("Shift not found.", "error")
                return redirect(url_for("roster", roster_date=selected_date))

            blocked = db.execute(
                """
                SELECT 1
                FROM staff_availability
                WHERE staff_id = ?
                  AND status IN ('leave', 'unavailable')
                  AND start_date <= ?
                  AND end_date >= ?
                LIMIT 1
                """,
                (staff_id_int, selected_date, selected_date),
            ).fetchone()
            if blocked:
                flash("Staff member is unavailable on this date.", "error")
            else:
                overlap = db.execute(
                    """
                    SELECT 1
                    FROM roster_assignments ra
                    JOIN shift_templates st ON st.id = ra.shift_id
                    WHERE ra.staff_id = ?
                      AND ra.roster_date = ?
                      AND (? < st.end_time AND st.start_time < ?)
                    LIMIT 1
                    """,
                    (
                        staff_id_int,
                        selected_date,
                        target_shift["start_time"],
                        target_shift["end_time"],
                    ),
                ).fetchone()
                if overlap:
                    flash("Shift overlaps with an existing assignment for this staff on this date.", "error")
                    return redirect(url_for("roster", roster_date=selected_date))

                try:
                    db.execute(
                        "INSERT INTO roster_assignments (roster_date, staff_id, shift_id, notes) VALUES (?, ?, ?, ?)",
                        (selected_date, staff_id_int, shift_id_int, notes or None),
                    )
                    db.commit()
                    flash("Assignment added.", "success")
                    return redirect(url_for("roster", roster_date=selected_date))
                except sqlite3.IntegrityError:
                    flash("This staff member already has this shift on this date.", "error")

    staff_rows = db.execute(
        "SELECT id, name, role FROM staff WHERE active = 1 ORDER BY name"
    ).fetchall()
    shift_rows = db.execute(
        "SELECT id, name, start_time, end_time FROM shift_templates ORDER BY start_time"
    ).fetchall()

    assignments = db.execute(
        """
        SELECT
            ra.id,
            ra.roster_date,
            ra.notes,
            s.name AS staff_name,
            s.role AS staff_role,
            st.name AS shift_name,
            st.start_time,
            st.end_time
        FROM roster_assignments ra
        JOIN staff s ON s.id = ra.staff_id
        JOIN shift_templates st ON st.id = ra.shift_id
        WHERE ra.roster_date = ?
        ORDER BY st.start_time, s.name
        """,
        (selected_date,),
    ).fetchall()

    return render_template(
        "roster.html",
        selected_date=selected_date,
        week_start=monday_for(selected_obj).isoformat(),
        staff_rows=staff_rows,
        shift_rows=shift_rows,
        assignments=assignments,
    )


@app.post("/roster/auto-schedule")
def auto_schedule() -> Any:
    db = get_db()
    week_start_raw = request.form.get("week_start", "")
    week_start = parse_iso_date(week_start_raw)
    if week_start is None:
        flash("Invalid week start date.", "error")
        return redirect(url_for("roster"))

    added, unfilled, ran = auto_schedule_week(db, week_start)
    if ran == 0:
        flash("Need at least one active staff and one shift template before auto-scheduling.", "error")
    else:
        flash(
            f"Auto-schedule completed for week of {week_start.isoformat()}: added {added} assignments, {unfilled} slots unfilled.",
            "success",
        )
    return redirect(url_for("roster", roster_date=week_start.isoformat()))


@app.post("/roster/<int:assignment_id>/delete")
def delete_assignment(assignment_id: int) -> Any:
    db = get_db()
    roster_date = request.form.get("roster_date", date.today().isoformat())
    db.execute("DELETE FROM roster_assignments WHERE id = ?", (assignment_id,))
    db.commit()
    flash("Assignment removed.", "success")
    return redirect(url_for("roster", roster_date=roster_date))


@app.route("/data")
def data_page() -> str:
    return render_template("data.html")


@app.route("/data/export/<dataset>")
def export_dataset(dataset: str) -> Response:
    db = get_db()
    if dataset == "assignments":
        rows = db.execute(
            """
            SELECT
                ra.roster_date,
                s.id AS staff_id,
                s.name AS staff_name,
                s.role AS staff_role,
                st.name AS shift_name,
                st.start_time
            FROM roster_assignments ra
            JOIN staff s ON s.id = ra.staff_id
            JOIN shift_templates st ON st.id = ra.shift_id
            ORDER BY ra.roster_date, s.name, st.start_time
            """
        ).fetchall()

        if not rows:
            return Response(
                "staff_name,role\n",
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=roster_empty.csv"},
            )

        date_columns = sorted({row["roster_date"] for row in rows})
        staff_map: dict[int, dict[str, Any]] = {}
        for row in rows:
            staff_id = row["staff_id"]
            if staff_id not in staff_map:
                staff_map[staff_id] = {
                    "staff_name": row["staff_name"],
                    "role": row["staff_role"],
                }
            date_key = row["roster_date"]
            if date_key not in staff_map[staff_id]:
                staff_map[staff_id][date_key] = []
            staff_map[staff_id][date_key].append(row["shift_name"])

        ordered_staff = sorted(
            staff_map.values(),
            key=lambda item: item["staff_name"].lower(),
        )
        headers = ["staff_name", "role", *date_columns]

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for staff in ordered_staff:
            row_values: list[str] = [staff.get("staff_name", ""), staff.get("role", "")]
            for date_key in date_columns:
                shifts = staff.get(date_key, [])
                if isinstance(shifts, list):
                    row_values.append(" | ".join(shifts))
                else:
                    row_values.append(str(shifts))
            writer.writerow(row_values)

        start_obj = parse_iso_date(date_columns[0])
        end_obj = parse_iso_date(date_columns[-1])
        if start_obj and end_obj:
            filename = f"roster_{start_obj.strftime('%d%m')}_{end_obj.strftime('%d%m')}.csv"
        else:
            filename = "roster.csv"

        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    queries: dict[str, tuple[str, list[str], str]] = {
        "staff": (
            "SELECT id, name, role, email, active FROM staff ORDER BY id",
            ["id", "name", "role", "email", "active"],
            "staff.csv",
        ),
        "shifts": (
            "SELECT id, name, start_time, end_time, required_staff FROM shift_templates ORDER BY id",
            ["id", "name", "start_time", "end_time", "required_staff"],
            "shifts.csv",
        ),
        "availability": (
            """
            SELECT
                sa.id,
                s.name AS staff_name,
                sa.start_date,
                sa.end_date,
                sa.status,
                sa.notes
            FROM staff_availability sa
            JOIN staff s ON s.id = sa.staff_id
            ORDER BY sa.start_date, sa.id
            """,
            ["id", "staff_name", "start_date", "end_date", "status", "notes"],
            "availability.csv",
        ),
    }

    if dataset not in queries:
        flash("Unknown dataset.", "error")
        return redirect(url_for("data_page"))

    query, headers, filename = queries[dataset]
    rows = db.execute(query).fetchall()
    return csv_response(filename, headers, rows)


@app.post("/data/import")
def import_dataset() -> Any:
    db = get_db()
    dataset = request.form.get("dataset", "")
    replace_existing = request.form.get("replace_existing") == "1"
    file_obj = request.files.get("csv_file")

    if not file_obj or not file_obj.filename:
        flash("Choose a CSV file to import.", "error")
        return redirect(url_for("data_page"))

    try:
        content = file_obj.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("CSV must be UTF-8 encoded.", "error")
        return redirect(url_for("data_page"))

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        flash("CSV file has no data rows.", "error")
        return redirect(url_for("data_page"))

    try:
        if dataset == "staff":
            if replace_existing:
                db.execute("DELETE FROM staff")
            added, skipped = 0, 0
            for row in rows:
                name = (row.get("name") or "").strip()
                role = (row.get("role") or "").strip()
                email = (row.get("email") or "").strip()
                active_raw = (row.get("active") or "1").strip()
                if not name or not role:
                    skipped += 1
                    continue
                active = 1 if active_raw not in {"0", "false", "False"} else 0
                db.execute(
                    "INSERT INTO staff (name, role, email, active) VALUES (?, ?, ?, ?)",
                    (name, role, email or None, active),
                )
                added += 1

        elif dataset == "shifts":
            if replace_existing:
                db.execute("DELETE FROM shift_templates")
            added, skipped = 0, 0
            for row in rows:
                name = (row.get("name") or "").strip()
                start_time = (row.get("start_time") or "").strip()
                end_time = (row.get("end_time") or "").strip()
                required_raw = (row.get("required_staff") or "1").strip()
                if not name or not start_time or not end_time:
                    skipped += 1
                    continue
                try:
                    required_staff = max(1, int(required_raw))
                    db.execute(
                        "INSERT INTO shift_templates (name, start_time, end_time, required_staff) VALUES (?, ?, ?, ?)",
                        (name, start_time, end_time, required_staff),
                    )
                    added += 1
                except (ValueError, sqlite3.IntegrityError):
                    skipped += 1

        elif dataset == "assignments":
            if replace_existing:
                db.execute("DELETE FROM roster_assignments")
            added, skipped = 0, 0
            for row in rows:
                roster_date = (row.get("roster_date") or "").strip()
                staff_id_raw = (row.get("staff_id") or "").strip()
                shift_id_raw = (row.get("shift_id") or "").strip()
                notes = (row.get("notes") or "").strip()
                if not parse_iso_date(roster_date):
                    skipped += 1
                    continue
                try:
                    db.execute(
                        "INSERT INTO roster_assignments (roster_date, staff_id, shift_id, notes) VALUES (?, ?, ?, ?)",
                        (roster_date, int(staff_id_raw), int(shift_id_raw), notes or None),
                    )
                    added += 1
                except (ValueError, sqlite3.IntegrityError):
                    skipped += 1

        elif dataset == "availability":
            if replace_existing:
                db.execute("DELETE FROM staff_availability")
            added, skipped = 0, 0
            for row in rows:
                staff_id_raw = (row.get("staff_id") or "").strip()
                start_date = (row.get("start_date") or "").strip()
                end_date = (row.get("end_date") or "").strip()
                status = (row.get("status") or "leave").strip()
                notes = (row.get("notes") or "").strip()
                start_obj = parse_iso_date(start_date)
                end_obj = parse_iso_date(end_date)
                if (
                    not start_obj
                    or not end_obj
                    or end_obj < start_obj
                    or status not in {"leave", "unavailable", "available"}
                ):
                    skipped += 1
                    continue
                try:
                    db.execute(
                        "INSERT INTO staff_availability (staff_id, start_date, end_date, status, notes) VALUES (?, ?, ?, ?, ?)",
                        (int(staff_id_raw), start_date, end_date, status, notes or None),
                    )
                    added += 1
                except (ValueError, sqlite3.IntegrityError):
                    skipped += 1

        else:
            flash("Unknown dataset.", "error")
            return redirect(url_for("data_page"))

        db.commit()
        flash(f"Import finished: {added} rows added, {skipped} rows skipped.", "success")
    except sqlite3.IntegrityError:
        db.rollback()
        flash("Import failed because rows reference missing records or duplicate unique fields.", "error")

    return redirect(url_for("data_page"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)

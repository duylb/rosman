from __future__ import annotations

import csv
import io
import importlib.util
import os
import sys
from functools import wraps
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import click
from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from config import DevelopmentConfig, ProductionConfig

BASE_DIR = Path(__file__).resolve().parent
EXTENSIONS_FILE = BASE_DIR / "app" / "extensions.py"
_extensions_spec = importlib.util.spec_from_file_location("rosman_extensions", EXTENSIONS_FILE)
if _extensions_spec is None or _extensions_spec.loader is None:
    raise RuntimeError(f"Cannot load SQLAlchemy extensions module at {EXTENSIONS_FILE}.")
_extensions_module = importlib.util.module_from_spec(_extensions_spec)
_extensions_spec.loader.exec_module(_extensions_module)
sys.modules["rosman_extensions"] = _extensions_module
db = _extensions_module.db
csrf = _extensions_module.csrf
migrate = _extensions_module.migrate
MODELS_FILE = BASE_DIR / "app" / "models.py"
_models_spec = importlib.util.spec_from_file_location("rosman_models", MODELS_FILE)
if _models_spec is None or _models_spec.loader is None:
    raise RuntimeError(f"Cannot load models module at {MODELS_FILE}.")
_models_module = importlib.util.module_from_spec(_models_spec)
_models_spec.loader.exec_module(_models_module)
Staff = _models_module.Staff
ShiftTemplate = _models_module.ShiftTemplate
RosterAssignment = _models_module.RosterAssignment
RosterVersion = _models_module.RosterVersion
StaffAvailability = _models_module.StaffAvailability
StaffShiftPreference = _models_module.StaffShiftPreference
User = _models_module.User
Organization = _models_module.Organization

app = Flask(__name__)
app_env = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
app.config.from_object(ProductionConfig if app_env == "production" else DevelopmentConfig)
if not app.config.get("SQLALCHEMY_DATABASE_URI"):
    raise RuntimeError("DATABASE_URL is required.")
db.init_app(app)
csrf.init_app(app)
migrate.init_app(app, db)
app.jinja_env.filters["ddmm"] = lambda value: format_ddmm(value)
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


@app.before_request
def load_current_user() -> None:
    user_id = session.get("user_id")
    g.user = User.query.get(user_id) if user_id else None
    if user_id and g.user is None:
        session.clear()


def current_org_id() -> int:
    if getattr(g, "user", None) is None:
        raise RuntimeError("Authenticated user is required.")
    return int(g.user.org_id)


def login_required(func: Any) -> Any:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if getattr(g, "user", None) is not None:
            return func(*args, **kwargs)
        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("login", next=next_url))

    return wrapper


@app.context_processor
def inject_translation_helpers() -> dict[str, Any]:
    return {"t": t, "lang": get_lang()}


def parse_iso_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def format_ddmm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m")
    if isinstance(value, date):
        return value.strftime("%d-%m")
    if isinstance(value, str):
        raw = value.strip()
        if len(raw) >= 10 and raw[4:5] == "-" and raw[7:8] == "-":
            parsed = parse_iso_date(raw[:10])
            if parsed is not None:
                return parsed.strftime("%d-%m")
        return value
    return str(value)


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


def csv_response(filename: str, headers: list[str], rows: list[dict[str, Any]]) -> Response:
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


def ensure_roster_schema_compatibility() -> None:
    """Bring older databases forward for roster versioning without full Alembic migrations."""
    inspector = inspect(db.engine)
    if not inspector.has_table("roster_assignments"):
        return

    if not inspector.has_table("roster_versions"):
        RosterVersion.__table__.create(bind=db.engine, checkfirst=True)

    inspector = inspect(db.engine)
    assignment_columns = {col["name"] for col in inspector.get_columns("roster_assignments")}
    if "version_id" not in assignment_columns:
        db.session.execute(text("ALTER TABLE roster_assignments ADD COLUMN version_id INTEGER"))
        db.session.commit()

    # Backfill version_id for legacy assignment rows that predate roster versioning.
    legacy_rows = db.session.execute(
        text(
            """
            SELECT DISTINCT org_id, roster_date
            FROM roster_assignments
            WHERE version_id IS NULL
            """
        )
    ).all()
    if not legacy_rows:
        return

    week_version_map: dict[tuple[int, date], int] = {}
    for org_id_raw, roster_date_raw in legacy_rows:
        roster_obj = parse_iso_date(str(roster_date_raw))
        if roster_obj is None:
            continue
        week_start_obj = monday_for(roster_obj)
        map_key = (int(org_id_raw), week_start_obj)
        if map_key in week_version_map:
            continue

        existing = (
            RosterVersion.query.filter_by(
                org_id=int(org_id_raw),
                week_start=week_start_obj,
                status="draft",
            )
            .order_by(RosterVersion.id.desc())
            .first()
        )
        if existing is None:
            existing = RosterVersion(
                org_id=int(org_id_raw),
                week_start=week_start_obj,
                status="draft",
            )
            db.session.add(existing)
            db.session.flush()
        week_version_map[map_key] = existing.id

    for (org_id_value, week_start_obj), version_id_value in week_version_map.items():
        week_end_obj = week_start_obj + timedelta(days=6)
        db.session.execute(
            text(
                """
                UPDATE roster_assignments
                SET version_id = :version_id
                WHERE org_id = :org_id
                  AND version_id IS NULL
                  AND roster_date BETWEEN :week_start AND :week_end
                """
            ),
            {
                "version_id": version_id_value,
                "org_id": org_id_value,
                "week_start": week_start_obj.isoformat(),
                "week_end": week_end_obj.isoformat(),
            },
        )

    db.session.commit()


@app.route("/login", methods=["GET", "POST"])
def login() -> str | Any:
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next", "")
    if request.method == "POST":
        email = (
            request.form.get("email", "").strip().lower()
            or request.form.get("username", "").strip().lower()
        )
        password = request.form.get("password", "")
        next_form = request.form.get("next", "").strip()
        if next_form:
            next_url = next_form

        user = User.query.filter(func.lower(User.email) == email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["role"] = user.role
            if not next_url.startswith("/"):
                next_url = url_for("dashboard")
            return redirect(next_url or url_for("dashboard"))

        flash(t("invalid_login"), "error")

    return render_template("login.html", next_url=next_url)


@app.post("/set-language")
@login_required
def set_language() -> Any:
    lang = request.form.get("lang", "en").strip().lower()
    if lang in SUPPORTED_LANGS:
        session["lang"] = lang
    next_url = request.form.get("next", "").strip()
    if not next_url.startswith("/"):
        next_url = request.referrer or url_for("dashboard")
    return redirect(next_url)


@app.post("/logout")
@login_required
def logout() -> Any:
    session.clear()
    return redirect(url_for("login"))


def auto_schedule_week(week_start: date) -> tuple[int, int, int]:
    org_id = current_org_id()
    staff_rows = Staff.query.filter_by(org_id=org_id, active=1).order_by(Staff.name).all()
    shift_rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()

    if not staff_rows or not shift_rows:
        return 0, 0, 0

    week_end = week_start + timedelta(days=6)
    recent_start = week_start - timedelta(days=28)
    week_start_str = week_start.isoformat()
    week_end_str = week_end.isoformat()

    existing_drafts = (
        RosterVersion.query.filter_by(org_id=org_id, week_start=week_start, status="draft")
        .order_by(RosterVersion.id.desc())
        .all()
    )
    for draft in existing_drafts:
        db.session.delete(draft)
    db.session.flush()

    draft_version = RosterVersion(
        org_id=org_id,
        week_start=week_start,
        status="draft",
    )
    db.session.add(draft_version)
    db.session.flush()

    recent_counts = {
        staff_id: count
        for staff_id, count in (
            db.session.query(RosterAssignment.staff_id, func.count(RosterAssignment.id))
            .filter(
                RosterAssignment.org_id == org_id,
                RosterAssignment.version_id == draft_version.id,
                RosterAssignment.roster_date.between(
                    recent_start.isoformat(), week_end.isoformat()
                )
            )
            .group_by(RosterAssignment.staff_id)
            .all()
        )
    }
    week_counts: dict[int, int] = {row.id: 0 for row in staff_rows}
    preference_rows = (
        StaffShiftPreference.query.filter(
            StaffShiftPreference.org_id == org_id,
            StaffShiftPreference.start_date <= week_end_str,
            StaffShiftPreference.end_date >= week_start_str,
        ).all()
    )

    added = 0
    unfilled = 0

    for offset in range(7):
        day_value = week_start + timedelta(days=offset)
        day_str = day_value.isoformat()

        blocked = {
            staff_id
            for (staff_id,) in (
                db.session.query(StaffAvailability.staff_id)
                .filter(
                    StaffAvailability.org_id == org_id,
                    StaffAvailability.status.in_(["leave", "unavailable"]),
                    StaffAvailability.start_date <= day_str,
                    StaffAvailability.end_date >= day_str,
                )
                .distinct()
                .all()
            )
        }

        assigned_ranges: dict[int, list[tuple[str, str]]] = {}
        for staff_id, start_time, end_time in (
            db.session.query(
                RosterAssignment.staff_id,
                ShiftTemplate.start_time,
                ShiftTemplate.end_time,
            )
            .join(ShiftTemplate, ShiftTemplate.id == RosterAssignment.shift_id)
            .filter(
                RosterAssignment.org_id == org_id,
                RosterAssignment.version_id == draft_version.id,
                ShiftTemplate.org_id == org_id,
                RosterAssignment.roster_date == day_str,
            )
            .all()
        ):
            assigned_ranges.setdefault(staff_id, []).append((start_time, end_time))

        shift_fill = {
            shift_id: count
            for shift_id, count in (
                db.session.query(RosterAssignment.shift_id, func.count(RosterAssignment.id))
                .filter(
                    RosterAssignment.org_id == org_id,
                    RosterAssignment.version_id == draft_version.id,
                    RosterAssignment.roster_date == day_str,
                )
                .group_by(RosterAssignment.shift_id)
                .all()
            )
        }

        for shift in shift_rows:
            open_slots = max(0, shift.required_staff - shift_fill.get(shift.id, 0))
            preferred_for_shift = {
                pref.staff_id
                for pref in preference_rows
                if pref.shift_id == shift.id and pref.start_date <= day_str and pref.end_date >= day_str
            }
            for _ in range(open_slots):
                eligible = [
                    s
                    for s in staff_rows
                    if s.id not in blocked
                    and all(
                        not ranges_overlap(
                            shift.start_time,
                            shift.end_time,
                            existing_start,
                            existing_end,
                        )
                        for existing_start, existing_end in assigned_ranges.get(s.id, [])
                    )
                ]
                if not eligible:
                    unfilled += 1
                    continue

                chosen = min(
                    eligible,
                    key=lambda s: (
                        0 if s.id in preferred_for_shift else 1,
                        week_counts.get(s.id, 0),
                        recent_counts.get(s.id, 0),
                        s.name,
                    ),
                )

                db.session.add(
                    RosterAssignment(
                        org_id=org_id,
                        version_id=draft_version.id,
                        roster_date=day_str,
                        staff_id=chosen.id,
                        shift_id=shift.id,
                        notes="Auto-scheduled",
                    )
                )
                assigned_ranges.setdefault(chosen.id, []).append((shift.start_time, shift.end_time))
                week_counts[chosen.id] = week_counts.get(chosen.id, 0) + 1
                recent_counts[chosen.id] = recent_counts.get(chosen.id, 0) + 1
                shift_fill[shift.id] = shift_fill.get(shift.id, 0) + 1
                added += 1

    db.session.commit()
    return added, unfilled, 1


@app.route("/")
@login_required
def dashboard() -> str:
    org_id = current_org_id()
    today = date.today().isoformat()

    staff_count = Staff.query.filter_by(org_id=org_id, active=1).count()
    shift_count = ShiftTemplate.query.filter_by(org_id=org_id).count()
    assignments_today = RosterAssignment.query.filter_by(org_id=org_id, roster_date=today).count()
    unavailable_today = (
        db.session.query(StaffAvailability.staff_id)
        .filter(
            StaffAvailability.org_id == org_id,
            StaffAvailability.status.in_(["leave", "unavailable"]),
            StaffAvailability.start_date <= today,
            StaffAvailability.end_date >= today,
        )
        .distinct()
        .count()
    )

    return render_template(
        "dashboard.html",
        today=today,
        staff_count=staff_count,
        shift_count=shift_count,
        assignments_today=assignments_today,
        unavailable_today=unavailable_today,
    )


@app.route("/staff", methods=["GET", "POST"])
@login_required
def staff() -> str:
    org_id = current_org_id()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not role:
            flash("Name and role are required.", "error")
        else:
            db.session.add(Staff(org_id=org_id, name=name, role=role, email=email or None))
            db.session.commit()
            flash("Staff member added.", "success")
            return redirect(url_for("staff"))

    rows = Staff.query.filter_by(org_id=org_id).order_by(Staff.active.desc(), Staff.name).all()
    return render_template("staff.html", staff=rows)


@app.post("/staff/<int:staff_id>/toggle")
@login_required
def toggle_staff(staff_id: int) -> Any:
    row = Staff.query.filter_by(id=staff_id, org_id=current_org_id()).first()
    if row is None:
        flash("Staff member not found.", "error")
    else:
        row.active = 0 if row.active else 1
        db.session.commit()
        flash("Staff status updated.", "success")
    return redirect(url_for("staff"))


@app.post("/staff/<int:staff_id>/edit")
@login_required
def edit_staff(staff_id: int) -> Any:
    row = Staff.query.filter_by(id=staff_id, org_id=current_org_id()).first()
    if row is None:
        flash("Staff member not found.", "error")
        return redirect(url_for("staff"))

    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()

    if not name or not role:
        flash("Name and role are required.", "error")
        return redirect(url_for("staff"))

    row.name = name
    row.role = role
    row.email = email or None
    db.session.commit()
    flash("Staff information updated.", "success")
    return redirect(url_for("staff"))


@app.post("/staff/import")
@login_required
def import_staff_csv() -> Any:
    org_id = current_org_id()
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

        db.session.add(Staff(org_id=org_id, name=name, role=role, email=email or None))
        added += 1

    db.session.commit()
    flash(f"Staff import finished: {added} rows added, {skipped} rows skipped.", "success")
    return redirect(url_for("staff"))


@app.route("/shifts", methods=["GET", "POST"])
@login_required
def shifts() -> str:
    org_id = current_org_id()
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
                db.session.add(
                    ShiftTemplate(
                        org_id=org_id,
                        name=name,
                        start_time=start_time,
                        end_time=end_time,
                        required_staff=required_staff,
                    )
                )
                db.session.commit()
                flash("Shift template added.", "success")
                return redirect(url_for("shifts"))
            except IntegrityError:
                db.session.rollback()
                flash("Shift name must be unique.", "error")

    rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()
    return render_template("shifts.html", shifts=rows)


@app.route("/availability", methods=["GET", "POST"])
@login_required
def availability() -> str:
    org_id = current_org_id()
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
            try:
                staff_id_int = int(staff_id)
            except ValueError:
                flash("Invalid staff.", "error")
                return redirect(url_for("availability"))

            staff = Staff.query.filter_by(id=staff_id_int, org_id=org_id).first()
            if staff is None:
                flash("Staff member not found.", "error")
                return redirect(url_for("availability"))
            db.session.add(
                StaffAvailability(
                    org_id=org_id,
                    staff_id=staff_id_int,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                    notes=notes or None,
                )
            )
            db.session.commit()
            flash("Availability entry added.", "success")
            return redirect(url_for("availability"))

    staff_rows = Staff.query.filter_by(org_id=org_id).order_by(Staff.name).all()
    availability_rows = [
        {
            "id": row.id,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "status": row.status,
            "notes": row.notes,
            "staff_name": row.staff.name,
            "staff_role": row.staff.role,
        }
        for row in (
            StaffAvailability.query.join(Staff)
            .filter(StaffAvailability.org_id == org_id, Staff.org_id == org_id)
            .order_by(StaffAvailability.start_date.desc(), Staff.name)
            .all()
        )
    ]
    shift_rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()
    preference_rows = [
        {
            "id": row.id,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "notes": row.notes,
            "staff_name": row.staff.name,
            "staff_role": row.staff.role,
            "shift_name": row.shift_template.name,
            "start_time": row.shift_template.start_time,
            "end_time": row.shift_template.end_time,
        }
        for row in (
            StaffShiftPreference.query.join(Staff).join(ShiftTemplate)
            .filter(
                StaffShiftPreference.org_id == org_id,
                Staff.org_id == org_id,
                ShiftTemplate.org_id == org_id,
            )
            .order_by(StaffShiftPreference.start_date.desc(), Staff.name, ShiftTemplate.start_time)
            .all()
        )
    ]

    return render_template(
        "availability.html",
        today=today,
        staff_rows=staff_rows,
        shift_rows=shift_rows,
        availability_rows=availability_rows,
        preference_rows=preference_rows,
    )


@app.post("/availability/<int:entry_id>/delete")
@login_required
def delete_availability(entry_id: int) -> Any:
    entry = StaffAvailability.query.filter_by(id=entry_id, org_id=current_org_id()).first()
    if entry is not None:
        db.session.delete(entry)
        db.session.commit()
    flash("Availability entry removed.", "success")
    return redirect(url_for("availability"))


@app.post("/availability/preferences")
@login_required
def add_shift_preference() -> Any:
    org_id = current_org_id()
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
    try:
        staff_id_int = int(staff_id)
    except ValueError:
        flash("Invalid staff.", "error")
        return redirect(url_for("availability"))

    staff = Staff.query.filter_by(id=staff_id_int, org_id=org_id).first()
    if staff is None:
        flash("Staff member not found.", "error")
        return redirect(url_for("availability"))

    for shift_id_raw in shift_ids:
        try:
            shift_id = int(shift_id_raw)
        except ValueError:
            continue
        shift = ShiftTemplate.query.filter_by(id=shift_id, org_id=org_id).first()
        if shift is None:
            continue
        db.session.add(
            StaffShiftPreference(
                org_id=org_id,
                staff_id=staff_id_int,
                shift_id=shift_id,
                start_date=start_date,
                end_date=end_date,
                notes=notes or None,
            )
        )
        added += 1
    db.session.commit()
    flash(f"Added {added} preferred shift entries.", "success")
    return redirect(url_for("availability"))


@app.post("/availability/preferences/<int:preference_id>/delete")
@login_required
def delete_shift_preference(preference_id: int) -> Any:
    preference = StaffShiftPreference.query.filter_by(
        id=preference_id, org_id=current_org_id()
    ).first()
    if preference is not None:
        db.session.delete(preference)
        db.session.commit()
    flash("Shift preference removed.", "success")
    return redirect(url_for("availability"))


@app.route("/roster", methods=["GET", "POST"])
@login_required
def roster() -> str:
    org_id = current_org_id()
    selected_date = request.values.get("roster_date", date.today().isoformat())
    selected_obj = parse_iso_date(selected_date) or date.today()
    week_start_obj = monday_for(selected_obj)
    version_id_raw = request.args.get("version_id", "").strip()

    confirmed_versions = (
        RosterVersion.query.filter_by(org_id=org_id, week_start=week_start_obj, status="confirmed")
        .order_by(RosterVersion.confirmed_at.desc(), RosterVersion.id.desc())
        .all()
    )
    draft_versions = (
        RosterVersion.query.filter_by(org_id=org_id, week_start=week_start_obj, status="draft")
        .order_by(RosterVersion.created_at.desc(), RosterVersion.id.desc())
        .all()
    )
    version_list = [*confirmed_versions, *draft_versions]

    default_version = (confirmed_versions[0] if confirmed_versions else None) or (
        draft_versions[0] if draft_versions else None
    )
    current_version = default_version
    if version_id_raw:
        try:
            selected_version_id = int(version_id_raw)
        except ValueError:
            abort(404)
        current_version = RosterVersion.query.filter_by(
            id=selected_version_id,
            org_id=org_id,
            week_start=week_start_obj,
        ).first()
        if current_version is None:
            abort(404)

    if request.method == "POST":
        if current_version is not None and current_version.status == "confirmed":
            flash("Confirmed versions are read-only. Switch to a draft version to edit.", "error")
            return redirect(
                url_for(
                    "roster",
                    roster_date=week_start_obj.isoformat(),
                    version_id=current_version.id,
                )
            )

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

            target_shift = ShiftTemplate.query.filter_by(id=shift_id_int, org_id=org_id).first()
            if target_shift is None:
                flash("Shift not found.", "error")
                return redirect(url_for("roster", roster_date=selected_date))

            staff_member = Staff.query.filter_by(id=staff_id_int, org_id=org_id, active=1).first()
            if staff_member is None:
                flash("Staff member not found.", "error")
                return redirect(url_for("roster", roster_date=selected_date))

            blocked = (
                StaffAvailability.query.filter(
                    StaffAvailability.org_id == org_id,
                    StaffAvailability.staff_id == staff_id_int,
                    StaffAvailability.status.in_(["leave", "unavailable"]),
                    StaffAvailability.start_date <= selected_date,
                    StaffAvailability.end_date >= selected_date,
                ).first()
                is not None
            )
            if blocked:
                flash("Staff member is unavailable on this date.", "error")
            else:
                if current_version is None or current_version.status != "draft":
                    current_version = RosterVersion(
                        org_id=org_id,
                        week_start=week_start_obj,
                        status="draft",
                    )
                    db.session.add(current_version)
                    db.session.flush()

                overlap = (
                    db.session.query(RosterAssignment.id)
                    .join(RosterVersion, RosterVersion.id == RosterAssignment.version_id)
                    .join(ShiftTemplate, ShiftTemplate.id == RosterAssignment.shift_id)
                    .filter(
                        RosterAssignment.org_id == org_id,
                        RosterAssignment.version_id == current_version.id,
                        RosterVersion.org_id == org_id,
                        RosterVersion.week_start == week_start_obj,
                        ShiftTemplate.org_id == org_id,
                        RosterAssignment.staff_id == staff_id_int,
                        RosterAssignment.roster_date == selected_date,
                        target_shift.start_time < ShiftTemplate.end_time,
                        ShiftTemplate.start_time < target_shift.end_time,
                    )
                    .first()
                )
                if overlap:
                    flash("Shift overlaps with an existing assignment for this staff on this date.", "error")
                    return redirect(url_for("roster", roster_date=selected_date))

                try:
                    db.session.add(
                        RosterAssignment(
                            org_id=org_id,
                            version_id=current_version.id,
                            roster_date=selected_date,
                            staff_id=staff_id_int,
                            shift_id=shift_id_int,
                            notes=notes or None,
                        )
                    )
                    db.session.commit()
                    flash("Assignment added.", "success")
                    return redirect(url_for("roster", roster_date=selected_date))
                except IntegrityError:
                    db.session.rollback()
                    flash("This staff member already has this shift on this date.", "error")

    staff_rows = Staff.query.filter_by(org_id=org_id, active=1).order_by(Staff.name).all()
    shift_rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()

    week_columns = [
        {
            "date": (week_start_obj + timedelta(days=offset)).isoformat(),
            "weekday": (week_start_obj + timedelta(days=offset)).strftime("%A"),
        }
        for offset in range(7)
    ]
    week_dates = [item["date"] for item in week_columns]
    week_range_label = f"{week_start_obj.strftime('%d-%m')} - {(week_start_obj + timedelta(days=6)).strftime('%d-%m')}"
    is_historical_view = (
        current_version is not None
        and default_version is not None
        and current_version.id != default_version.id
    )
    assignments: list[dict[str, Any]] = []
    if current_version is not None:
        assignments = [
            {
                "id": row.id,
                "roster_date": row.roster_date,
                "staff_id": row.staff.id,
                "notes": row.notes,
                "staff_name": row.staff.name,
                "staff_role": row.staff.role,
                "shift_name": row.shift_template.name,
                "start_time": row.shift_template.start_time,
                "end_time": row.shift_template.end_time,
            }
            for row in (
                RosterAssignment.query.join(RosterVersion, RosterVersion.id == RosterAssignment.version_id)
                .join(Staff)
                .join(ShiftTemplate)
                .filter(
                    RosterAssignment.org_id == org_id,
                    RosterVersion.org_id == org_id,
                    RosterVersion.week_start == week_start_obj,
                    RosterAssignment.version_id == current_version.id,
                    Staff.org_id == org_id,
                    ShiftTemplate.org_id == org_id,
                    RosterAssignment.roster_date.between(week_dates[0], week_dates[-1]),
                )
                .order_by(RosterAssignment.roster_date, ShiftTemplate.start_time, Staff.name)
                .all()
            )
        ]

    assignments_by_staff_and_day: dict[int, dict[str, list[dict[str, Any]]]] = {
        row.id: {day_value: [] for day_value in week_dates}
        for row in staff_rows
    }
    for row in assignments:
        staff_entry = assignments_by_staff_and_day.get(row["staff_id"])
        if staff_entry is None:
            continue
        if row["roster_date"] not in staff_entry:
            continue
        staff_entry[row["roster_date"]].append(row)

    return render_template(
        "roster.html",
        selected_date=selected_date,
        week_start=week_start_obj.isoformat(),
        week_columns=week_columns,
        week_dates=week_dates,
        week_range_label=week_range_label,
        current_version=current_version,
        version_list=version_list,
        is_historical_view=is_historical_view,
        staff_rows=staff_rows,
        shift_rows=shift_rows,
        assignments=assignments,
        assignments_by_staff_and_day=assignments_by_staff_and_day,
    )


@app.post("/roster/auto-schedule")
@login_required
def auto_schedule() -> Any:
    week_start_raw = request.form.get("week_start", "")
    week_start = parse_iso_date(week_start_raw)
    if week_start is None:
        flash("Invalid week start date.", "error")
        return redirect(url_for("roster"))

    added, unfilled, ran = auto_schedule_week(week_start)
    if ran == 0:
        flash("Need at least one active staff and one shift template before auto-scheduling.", "error")
    else:
        flash(
            f"Auto-schedule completed for week of {week_start.strftime('%d-%m')}: added {added} assignments, {unfilled} slots unfilled.",
            "success",
        )
    return redirect(url_for("roster", roster_date=week_start.isoformat()))


@app.post("/roster/confirm/<int:version_id>")
@login_required
def confirm_roster_version(version_id: int) -> Any:
    org_id = current_org_id()
    deleted_version_ids: list[int] = []
    now_utc = datetime.utcnow()
    roster_date = request.form.get("roster_date", "").strip()

    try:
        version = RosterVersion.query.filter_by(id=version_id, org_id=org_id).first()
        if version is None:
            if request.is_json or request.args.get("format") == "json":
                return jsonify({"error": "Roster version not found."}), 404
            flash("Roster version not found.", "error")
            return redirect(url_for("roster", roster_date=roster_date or date.today().isoformat()))

        other_confirmed_versions = (
            RosterVersion.query.filter(
                RosterVersion.org_id == org_id,
                RosterVersion.week_start == version.week_start,
                RosterVersion.status == "confirmed",
                RosterVersion.id != version.id,
            ).all()
        )
        deleted_version_ids = [row.id for row in other_confirmed_versions]
        for row in other_confirmed_versions:
            db.session.delete(row)

        version.status = "confirmed"
        version.confirmed_at = now_utc
        db.session.commit()

        payload = {
            "version": {
                "id": version.id,
                "org_id": version.org_id,
                "week_start": version.week_start.isoformat(),
                "status": version.status,
                "confirmed_at": version.confirmed_at.isoformat() if version.confirmed_at else None,
            },
            "deleted_version_ids": deleted_version_ids,
        }
        if request.is_json or request.args.get("format") == "json":
            return jsonify(payload), 200

        flash("Roster confirmed.", "success")
        target_date = roster_date or version.week_start.isoformat()
        return redirect(url_for("roster", roster_date=target_date))
    except IntegrityError:
        db.session.rollback()
        if request.is_json or request.args.get("format") == "json":
            return jsonify({"error": "Unable to confirm roster version."}), 409
        flash("Unable to confirm roster version.", "error")
        return redirect(url_for("roster", roster_date=roster_date or date.today().isoformat()))


@app.post("/roster/discard/<int:version_id>")
@login_required
def discard_roster_version(version_id: int) -> Any:
    org_id = current_org_id()
    version = RosterVersion.query.filter_by(id=version_id, org_id=org_id).first()
    if version is None:
        abort(404)
    if version.status != "draft":
        abort(403)

    target_date = version.week_start.isoformat()
    try:
        RosterAssignment.query.filter_by(
            org_id=org_id,
            version_id=version.id,
        ).delete(synchronize_session=False)
        db.session.delete(version)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    return redirect(url_for("roster", roster_date=target_date))


@app.post("/roster/<int:assignment_id>/delete")
@login_required
def delete_assignment(assignment_id: int) -> Any:
    roster_date = request.form.get("roster_date", date.today().isoformat())
    selected_obj = parse_iso_date(roster_date) or date.today()
    week_start_obj = monday_for(selected_obj)
    org_id = current_org_id()
    draft_version = (
        RosterVersion.query.filter_by(org_id=org_id, week_start=week_start_obj, status="draft")
        .order_by(RosterVersion.id.desc())
        .first()
    )
    if draft_version is None:
        flash("Confirmed roster is read-only. Create or load a draft version to edit.", "error")
        return redirect(url_for("roster", roster_date=roster_date))

    assignment = RosterAssignment.query.filter_by(
        id=assignment_id,
        org_id=org_id,
        version_id=draft_version.id,
    ).first()
    if assignment is not None:
        db.session.delete(assignment)
        db.session.commit()
        flash("Assignment removed.", "success")
    else:
        flash("Confirmed roster is read-only. Only draft assignments can be removed.", "error")
    return redirect(url_for("roster", roster_date=roster_date))


@app.route("/data")
@login_required
def data_page() -> str:
    return render_template("data.html")


@app.route("/data/export/<dataset>")
@login_required
def export_dataset(dataset: str) -> Response:
    org_id = current_org_id()
    if dataset == "assignments":
        rows = [
            {
                "roster_date": row.roster_date,
                "staff_id": row.staff.id,
                "staff_name": row.staff.name,
                "staff_role": row.staff.role,
                "shift_name": row.shift_template.name,
                "start_time": row.shift_template.start_time,
            }
            for row in (
                RosterAssignment.query.join(Staff).join(ShiftTemplate)
                .filter(
                    RosterAssignment.org_id == org_id,
                    Staff.org_id == org_id,
                    ShiftTemplate.org_id == org_id,
                )
                .order_by(RosterAssignment.roster_date, Staff.name, ShiftTemplate.start_time)
                .all()
            )
        ]

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

    if dataset == "staff":
        rows = [
            {
                "id": row.id,
                "name": row.name,
                "role": row.role,
                "email": row.email,
                "active": row.active,
            }
            for row in Staff.query.filter_by(org_id=org_id).order_by(Staff.id).all()
        ]
        return csv_response("staff.csv", ["id", "name", "role", "email", "active"], rows)

    if dataset == "shifts":
        rows = [
            {
                "id": row.id,
                "name": row.name,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "required_staff": row.required_staff,
            }
            for row in ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.id).all()
        ]
        return csv_response(
            "shifts.csv",
            ["id", "name", "start_time", "end_time", "required_staff"],
            rows,
        )

    if dataset == "availability":
        rows = [
            {
                "id": row.id,
                "staff_name": row.staff.name,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "status": row.status,
                "notes": row.notes,
            }
            for row in (
                StaffAvailability.query.join(Staff)
                .filter(StaffAvailability.org_id == org_id, Staff.org_id == org_id)
                .order_by(StaffAvailability.start_date, StaffAvailability.id)
                .all()
            )
        ]
        return csv_response(
            "availability.csv",
            ["id", "staff_name", "start_date", "end_date", "status", "notes"],
            rows,
        )

    flash("Unknown dataset.", "error")
    return redirect(url_for("data_page"))


@app.post("/data/import")
@login_required
def import_dataset() -> Any:
    org_id = current_org_id()
    dataset = request.form.get("dataset", "")
    replace_existing = request.form.get("replace_existing") == "1"
    roster_redirect_date: str | None = None
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
                for item in Staff.query.filter_by(org_id=org_id).all():
                    db.session.delete(item)
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
                db.session.add(
                    Staff(org_id=org_id, name=name, role=role, email=email or None, active=active)
                )
                added += 1

        elif dataset == "shifts":
            if replace_existing:
                for item in ShiftTemplate.query.filter_by(org_id=org_id).all():
                    db.session.delete(item)
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
                    with db.session.begin_nested():
                        db.session.add(
                            ShiftTemplate(
                                org_id=org_id,
                                name=name,
                                start_time=start_time,
                                end_time=end_time,
                                required_staff=required_staff,
                            )
                        )
                        db.session.flush()
                    added += 1
                except (ValueError, IntegrityError):
                    skipped += 1

        elif dataset == "assignments":
            added, skipped = 0, 0
            import_week_start: date | None = None
            parsed_rows: list[dict[str, Any]] = []
            for row in rows:
                roster_date = (row.get("roster_date") or "").strip()
                staff_id_raw = (row.get("staff_id") or "").strip()
                shift_id_raw = (row.get("shift_id") or "").strip()
                notes = (row.get("notes") or "").strip()
                roster_date_obj = parse_iso_date(roster_date)
                if not roster_date_obj:
                    skipped += 1
                    continue
                try:
                    staff_id = int(staff_id_raw)
                    shift_id = int(shift_id_raw)
                    staff_exists = (
                        Staff.query.filter_by(id=staff_id, org_id=org_id).first() is not None
                    )
                    shift_exists = (
                        ShiftTemplate.query.filter_by(id=shift_id, org_id=org_id).first() is not None
                    )
                    if not staff_exists or not shift_exists:
                        skipped += 1
                        continue

                    row_week_start = monday_for(roster_date_obj)
                    if import_week_start is None:
                        import_week_start = row_week_start
                    elif row_week_start != import_week_start:
                        skipped += 1
                        continue

                    parsed_rows.append(
                        {
                            "roster_date": roster_date,
                            "staff_id": staff_id,
                            "shift_id": shift_id,
                            "notes": notes or None,
                        }
                    )
                except (ValueError, IntegrityError):
                    skipped += 1

            if import_week_start is not None:
                if replace_existing:
                    existing_drafts = (
                        RosterVersion.query.filter_by(
                            org_id=org_id,
                            week_start=import_week_start,
                            status="draft",
                        ).all()
                    )
                    for draft in existing_drafts:
                        db.session.delete(draft)
                    db.session.flush()

                draft_version = RosterVersion(
                    org_id=org_id,
                    week_start=import_week_start,
                    status="draft",
                )
                db.session.add(draft_version)
                db.session.flush()

                for parsed in parsed_rows:
                    try:
                        with db.session.begin_nested():
                            db.session.add(
                                RosterAssignment(
                                    org_id=org_id,
                                    version_id=draft_version.id,
                                    roster_date=parsed["roster_date"],
                                    staff_id=parsed["staff_id"],
                                    shift_id=parsed["shift_id"],
                                    notes=parsed["notes"],
                                )
                            )
                            db.session.flush()
                        added += 1
                    except IntegrityError:
                        skipped += 1

                roster_redirect_date = import_week_start.isoformat()

        elif dataset == "availability":
            if replace_existing:
                for item in StaffAvailability.query.filter_by(org_id=org_id).all():
                    db.session.delete(item)
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
                    staff_id = int(staff_id_raw)
                    if Staff.query.filter_by(id=staff_id, org_id=org_id).first() is None:
                        skipped += 1
                        continue
                    with db.session.begin_nested():
                        db.session.add(
                            StaffAvailability(
                                org_id=org_id,
                                staff_id=staff_id,
                                start_date=start_date,
                                end_date=end_date,
                                status=status,
                                notes=notes or None,
                            )
                        )
                        db.session.flush()
                    added += 1
                except (ValueError, IntegrityError):
                    skipped += 1

        else:
            flash("Unknown dataset.", "error")
            return redirect(url_for("data_page"))

        db.session.commit()
        flash(f"Import finished: {added} rows added, {skipped} rows skipped.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Import failed because rows reference missing records or duplicate unique fields.", "error")

    if dataset == "assignments" and roster_redirect_date:
        return redirect(url_for("roster", roster_date=roster_redirect_date))
    return redirect(url_for("data_page"))


@app.cli.command("create-admin")
def create_admin() -> None:
    if User.query.count() > 0:
        click.echo("Admin creation skipped: at least one user already exists.")
        return

    email = click.prompt("Admin email").strip().lower()
    while not email:
        click.echo("Email is required.")
        email = click.prompt("Admin email").strip().lower()

    if User.query.filter(func.lower(User.email) == email).first():
        click.echo("A user with that email already exists.")
        return

    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    while not password:
        click.echo("Password is required.")
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    default_org_name = f"{email.split('@')[0]}'s Organization"
    org_name = click.prompt("Organization name", default=default_org_name).strip()
    while not org_name:
        click.echo("Organization name is required.")
        org_name = click.prompt("Organization name", default=default_org_name).strip()

    organization = Organization(name=org_name)
    db.session.add(organization)
    db.session.flush()

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role="owner",
        org_id=organization.id,
    )
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin user created: {email} (org: {org_name})")


with app.app_context():
    db.create_all()
    try:
        ensure_roster_schema_compatibility()
    except SQLAlchemyError:
        db.session.rollback()
        raise


if __name__ == "__main__":
    app.run(debug=True)

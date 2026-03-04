from __future__ import annotations

import csv
import io
import importlib.util
import os
import sys
from functools import wraps
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import click
from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from config import DevelopmentConfig, ProductionConfig
from duy import create_duy_blueprint
from utils.i18n import get_lang, set_lang, t

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
app.jinja_env.filters["ddmm"] = lambda value: format_date(value, include_year=False)
app.jinja_env.filters["datefmt"] = lambda value, include_year=True: format_date(value, include_year=include_year)
app.jinja_env.filters["datetimefmt"] = lambda value: format_datetime(value)
app.jinja_env.filters["money"] = lambda value: format_money(value)
def format_money(value: Any) -> str:
    amount = Decimal(str(value or 0))
    return f"{amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def parse_non_negative_decimal(raw: str) -> Decimal | None:
    if raw == "":
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if value < 0:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def has_payroll_access() -> bool:
    user = getattr(g, "user", None)
    role = (user.role if user else "") or ""
    return bool(getattr(user, "is_owner", False)) or role.lower() in {"owner", "manager"}


def payroll_access_required(func: Any) -> Any:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if has_payroll_access():
            return func(*args, **kwargs)
        abort(403)

    return wrapper


@app.before_request
def load_current_user() -> None:
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None
    if user_id and g.user is None:
        session.clear()
        return
    if g.user is None:
        return
    if is_user_denied(g.user):
        session.clear()
        if is_account_expired(g.user):
            flash("msg_account_expired_contact_admin", "error")
        else:
            flash("msg_account_locked_contact_admin", "error")
        if request.endpoint not in {"login", "set_language", "static"}:
            g.user = None
            next_url = request.full_path if request.query_string else request.path
            if not next_url.startswith("/"):
                next_url = url_for("dashboard")
            return redirect(url_for("login", next=next_url))


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
    return {
        "t": t,
        "lang": get_lang(),
        "app_version": app.config.get("APP_VERSION", ""),
        "app_author": app.config.get("APP_AUTHOR", ""),
    }


def parse_iso_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_iso_datetime(raw: str) -> datetime | None:
    raw_value = (raw or "").strip()
    if not raw_value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue
    return None


def is_account_expired(user: Any, now_utc: datetime | None = None) -> bool:
    expires_at = getattr(user, "expires_at", None)
    if expires_at is None:
        return False
    now_value = now_utc or datetime.utcnow()
    return expires_at <= now_value


def is_user_denied(user: Any, now_utc: datetime | None = None) -> bool:
    if getattr(user, "is_owner", False):
        return is_account_expired(user, now_utc=now_utc)
    if not bool(getattr(user, "is_active", True)):
        return True
    return is_account_expired(user, now_utc=now_utc)


def format_date(value: Any, include_year: bool = True) -> str:
    if value is None:
        return ""
    date_format = "%d/%m/%Y" if include_year else "%d/%m"
    if isinstance(value, datetime):
        return value.strftime(date_format)
    if isinstance(value, date):
        return value.strftime(date_format)
    if isinstance(value, str):
        raw = value.strip()
        if len(raw) >= 10 and raw[4:5] == "-" and raw[7:8] == "-":
            parsed = parse_iso_date(raw[:10])
            if parsed is not None:
                return parsed.strftime(date_format)
        return value
    return str(value)


def format_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return f"{format_date(value.date())} {value.strftime('%H:%M')}"
    if isinstance(value, str):
        raw = value.strip()
        parsed: datetime | None = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if parsed is not None:
            return f"{format_date(parsed.date())} {parsed.strftime('%H:%M')}"
        parsed_date = parse_iso_date(raw[:10]) if len(raw) >= 10 else None
        if parsed_date is not None:
            return format_date(parsed_date)
        return value
    if isinstance(value, date):
        return format_date(value)
    return str(value)


def monday_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def to_minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def shift_duration_hours(start_hhmm: str, end_hhmm: str) -> Decimal:
    try:
        start_minutes = to_minutes(start_hhmm)
        end_minutes = to_minutes(end_hhmm)
    except (ValueError, AttributeError):
        return Decimal("0.00")
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60
    duration_minutes = end_minutes - start_minutes
    duration_hours = Decimal(duration_minutes) / Decimal(60)
    return duration_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def each_date(start_obj: date, end_obj: date) -> list[str]:
    total_days = (end_obj - start_obj).days + 1
    return [(start_obj + timedelta(days=offset)).isoformat() for offset in range(total_days)]


def month_bounds(day: date) -> tuple[date, date]:
    start_obj = day.replace(day=1)
    if start_obj.month == 12:
        next_month = start_obj.replace(year=start_obj.year + 1, month=1, day=1)
    else:
        next_month = start_obj.replace(month=start_obj.month + 1, day=1)
    return start_obj, next_month - timedelta(days=1)


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

    roster_version_columns = {col["name"] for col in inspector.get_columns("roster_versions")}
    if "updated_at" not in roster_version_columns:
        db.session.execute(text("ALTER TABLE roster_versions ADD COLUMN updated_at TIMESTAMP"))
        db.session.commit()

    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_roster_assignments_org_version_date "
            "ON roster_assignments (org_id, version_id, roster_date)"
        )
    )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_roster_versions_org_week_status "
            "ON roster_versions (org_id, week_start, status)"
        )
    )
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


def ensure_staff_schema_compatibility() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table("staff"):
        return
    staff_columns = {col["name"] for col in inspector.get_columns("staff")}
    if "hourly_wage" not in staff_columns:
        db.session.execute(text("ALTER TABLE staff ADD COLUMN hourly_wage NUMERIC"))
    if "department" not in staff_columns:
        db.session.execute(text("ALTER TABLE staff ADD COLUMN department VARCHAR(120)"))
    db.session.execute(
        text("CREATE INDEX IF NOT EXISTS ix_staff_org_department ON staff (org_id, department)")
    )
    db.session.commit()


def ensure_user_schema_compatibility() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table("users"):
        return
    dialect_name = db.engine.dialect.name.lower()
    bool_type = "BOOLEAN" if dialect_name == "postgresql" else "INTEGER"
    bool_true = "TRUE" if dialect_name == "postgresql" else "1"
    bool_false = "FALSE" if dialect_name == "postgresql" else "0"
    datetime_type = "TIMESTAMP" if dialect_name == "postgresql" else "DATETIME"

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "is_active" not in user_columns:
        db.session.execute(
            text(f"ALTER TABLE users ADD COLUMN is_active {bool_type} NOT NULL DEFAULT {bool_true}")
        )
    if "expires_at" not in user_columns:
        db.session.execute(text(f"ALTER TABLE users ADD COLUMN expires_at {datetime_type}"))
    if "is_owner" not in user_columns:
        db.session.execute(
            text(f"ALTER TABLE users ADD COLUMN is_owner {bool_type} NOT NULL DEFAULT {bool_false}")
        )

    # Keep legacy owner role semantics while introducing explicit owner flag.
    db.session.execute(text(f"UPDATE users SET is_owner = {bool_true} WHERE role = 'owner'"))
    db.session.execute(text(f"UPDATE users SET is_active = {bool_true} WHERE is_owner = {bool_true}"))

    owner_count = db.session.execute(
        text(f"SELECT COUNT(1) FROM users WHERE is_owner = {bool_true}")
    ).scalar_one()
    if int(owner_count or 0) == 0:
        first_user_id = db.session.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).scalar_one_or_none()
        if first_user_id is not None:
            db.session.execute(
                text(
                    f"UPDATE users SET is_owner = {bool_true}, is_active = {bool_true} "
                    "WHERE id = :user_id"
                ),
                {"user_id": int(first_user_id)},
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
        if user and is_user_denied(user):
            if is_account_expired(user):
                flash("msg_account_expired_contact_admin", "error")
            else:
                flash("msg_account_locked_contact_admin", "error")
            return render_template("login.html", next_url=next_url)

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["role"] = user.role
            if not next_url.startswith("/"):
                next_url = url_for("dashboard")
            return redirect(next_url or url_for("dashboard"))

        flash("invalid_login", "error")

    return render_template("login.html", next_url=next_url)


@app.post("/set-language")
def set_language() -> Any:
    lang = request.form.get("lang", "en").strip().lower()
    set_lang(lang)
    next_url = request.form.get("next", "").strip()
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = request.referrer or url_for("dashboard")
    return redirect(next_url)


@app.post("/logout")
@login_required
def logout() -> Any:
    session.clear()
    return redirect(url_for("login"))


app.register_blueprint(
    create_duy_blueprint(
        db=db,
        User=User,
        Organization=Organization,
        login_required=login_required,
        parse_iso_datetime=parse_iso_datetime,
    )
)


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

    existing_draft = (
        RosterVersion.query.filter_by(org_id=org_id, week_start=week_start, status="draft")
        .order_by(RosterVersion.id.desc())
        .first()
    )
    draft_version = existing_draft
    if draft_version is None:
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
    week_counts = {
        staff_id: count
        for staff_id, count in (
            db.session.query(RosterAssignment.staff_id, func.count(RosterAssignment.id))
            .filter(
                RosterAssignment.org_id == org_id,
                RosterAssignment.version_id == draft_version.id,
                RosterAssignment.roster_date.between(week_start.isoformat(), week_end.isoformat()),
            )
            .group_by(RosterAssignment.staff_id)
            .all()
        )
    }
    for row in staff_rows:
        week_counts.setdefault(row.id, 0)
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
        existing_staff_shift_pairs = {
            (staff_id, shift_id)
            for staff_id, shift_id in (
                db.session.query(RosterAssignment.staff_id, RosterAssignment.shift_id)
                .filter(
                    RosterAssignment.org_id == org_id,
                    RosterAssignment.roster_date == day_str,
                )
                .all()
            )
        }
        manual_assigned_staff = {
            staff_id
            for (staff_id,) in (
                db.session.query(RosterAssignment.staff_id)
                .filter(
                    RosterAssignment.org_id == org_id,
                    RosterAssignment.version_id == draft_version.id,
                    RosterAssignment.roster_date == day_str,
                    (RosterAssignment.notes.is_(None)) | (RosterAssignment.notes != "Auto-scheduled"),
                )
                .distinct()
                .all()
            )
        }

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
            # Existing assignments in this draft (manual + auto) always take priority.
            current_fill = shift_fill.get(shift.id, 0)
            if current_fill >= shift.required_staff:
                continue
            open_slots = shift.required_staff - current_fill
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
                    and s.id not in manual_assigned_staff
                    and (s.id, shift.id) not in existing_staff_shift_pairs
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
                existing_staff_shift_pairs.add((chosen.id, shift.id))
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
        department = request.form.get("department", "").strip()
        hourly_wage_raw = request.form.get("hourly_wage", "").strip()
        hourly_wage = parse_non_negative_decimal(hourly_wage_raw)

        if not name or not role:
            flash(t("msg_name_role_required"), "error")
        elif hourly_wage_raw and hourly_wage is None:
            flash(t("msg_hourly_wage_non_negative"), "error")
        else:
            db.session.add(
                Staff(
                    org_id=org_id,
                    name=name,
                    role=role,
                    email=email or None,
                    department=department or None,
                    hourly_wage=hourly_wage,
                )
            )
            db.session.commit()
            flash(t("msg_staff_member_added"), "success")
            return redirect(url_for("staff"))

    rows = Staff.query.filter_by(org_id=org_id).order_by(Staff.active.desc(), Staff.name).all()
    return render_template("staff.html", staff=rows)


@app.post("/staff/<int:staff_id>/toggle")
@login_required
def toggle_staff(staff_id: int) -> Any:
    row = Staff.query.filter_by(id=staff_id, org_id=current_org_id()).first()
    if row is None:
        flash(t("msg_staff_member_not_found"), "error")
    else:
        row.active = 0 if row.active else 1
        db.session.commit()
        flash(t("msg_staff_status_updated"), "success")
    return redirect(url_for("staff"))


@app.post("/staff/<int:staff_id>/edit")
@login_required
def edit_staff(staff_id: int) -> Any:
    row = Staff.query.filter_by(id=staff_id, org_id=current_org_id()).first()
    if row is None:
        flash(t("msg_staff_member_not_found"), "error")
        return redirect(url_for("staff"))

    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()
    hourly_wage_raw = request.form.get("hourly_wage", "").strip()
    hourly_wage = parse_non_negative_decimal(hourly_wage_raw)

    if not name or not role:
        flash(t("msg_name_role_required"), "error")
        return redirect(url_for("staff"))
    if hourly_wage_raw and hourly_wage is None:
        flash(t("msg_hourly_wage_non_negative"), "error")
        return redirect(url_for("staff"))

    row.name = name
    row.role = role
    row.email = email or None
    row.department = department or None
    row.hourly_wage = hourly_wage
    db.session.commit()
    flash(t("msg_staff_info_updated"), "success")
    return redirect(url_for("staff"))


@app.post("/staff/<int:staff_id>/delete")
@login_required
def delete_staff(staff_id: int) -> Any:
    row = Staff.query.filter_by(id=staff_id, org_id=current_org_id()).first()
    if row is None:
        flash(t("msg_staff_member_not_found"), "error")
        return redirect(url_for("staff"))

    db.session.delete(row)
    db.session.commit()
    flash(t("msg_staff_removed"), "success")
    return redirect(url_for("staff"))


@app.post("/staff/import")
@login_required
def import_staff_csv() -> Any:
    org_id = current_org_id()
    file_obj = request.files.get("csv_file")

    if not file_obj or not file_obj.filename:
        flash(t("msg_choose_csv_file"), "error")
        return redirect(url_for("staff"))

    try:
        content = file_obj.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash(t("msg_csv_utf8_required"), "error")
        return redirect(url_for("staff"))

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if len(rows) <= 1:
        flash(t("msg_csv_staff_header_required"), "error")
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
    flash(t("msg_staff_import_finished").format(added=added, skipped=skipped), "success")
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
            flash(t("msg_shift_required_fields"), "error")
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
                flash(t("msg_shift_template_added"), "success")
                return redirect(url_for("shifts"))
            except IntegrityError:
                db.session.rollback()
                flash(t("msg_shift_name_unique"), "error")

    rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()
    return render_template("shifts.html", shifts=rows)


@app.post("/shifts/<int:shift_id>/edit")
@login_required
def edit_shift_template(shift_id: int) -> Any:
    org_id = current_org_id()
    shift = ShiftTemplate.query.filter_by(id=shift_id, org_id=org_id).first()
    if shift is None:
        abort(404)

    name = request.form.get("name", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()

    if not name or not start_time or not end_time:
        flash(t("msg_shift_required_fields"), "error")
        return redirect(url_for("shifts"))

    try:
        start_minutes = to_minutes(start_time)
        end_minutes = to_minutes(end_time)
    except (ValueError, AttributeError):
        flash(t("msg_shift_invalid_time_order"), "error")
        return redirect(url_for("shifts"))

    if start_minutes >= end_minutes:
        flash(t("msg_shift_invalid_time_order"), "error")
        return redirect(url_for("shifts"))

    overlap = (
        ShiftTemplate.query.filter(
            ShiftTemplate.org_id == org_id,
            ShiftTemplate.id != shift.id,
            ShiftTemplate.start_time < end_time,
            start_time < ShiftTemplate.end_time,
        )
        .order_by(ShiftTemplate.start_time)
        .first()
    )
    if overlap is not None:
        flash(t("msg_shift_template_overlap"), "error")
        return redirect(url_for("shifts"))

    shift.name = name
    shift.start_time = start_time
    shift.end_time = end_time

    try:
        db.session.commit()
        flash(t("msg_shift_template_updated"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(t("msg_shift_name_unique"), "error")

    return redirect(url_for("shifts"))


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
            flash(t("msg_availability_required_fields"), "error")
        elif end_obj < start_obj:
            flash(t("msg_end_date_on_or_after_start"), "error")
        elif status not in {"leave", "unavailable"}:
            flash(t("msg_invalid_availability_status"), "error")
        else:
            try:
                staff_id_int = int(staff_id)
            except ValueError:
                flash(t("msg_invalid_staff"), "error")
                return redirect(url_for("availability"))

            staff = Staff.query.filter_by(id=staff_id_int, org_id=org_id).first()
            if staff is None:
                flash(t("msg_staff_member_not_found"), "error")
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
            flash(t("msg_availability_entry_added"), "success")
            return redirect(url_for("availability"))

    staff_rows = Staff.query.filter_by(org_id=org_id).order_by(Staff.name).all()
    availability_rows = [
        {
            "id": row.id,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "status": row.status,
            "notes": row.notes,
            "staff_name": row.staff_name,
            "staff_role": row.staff_role,
        }
        for row in (
            db.session.query(
                StaffAvailability.id,
                StaffAvailability.start_date,
                StaffAvailability.end_date,
                StaffAvailability.status,
                StaffAvailability.notes,
                Staff.name.label("staff_name"),
                Staff.role.label("staff_role"),
            )
            .join(Staff, Staff.id == StaffAvailability.staff_id)
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
            "staff_name": row.staff_name,
            "staff_role": row.staff_role,
            "shift_name": row.shift_name,
            "start_time": row.start_time,
            "end_time": row.end_time,
        }
        for row in (
            db.session.query(
                StaffShiftPreference.id,
                StaffShiftPreference.start_date,
                StaffShiftPreference.end_date,
                StaffShiftPreference.notes,
                Staff.name.label("staff_name"),
                Staff.role.label("staff_role"),
                ShiftTemplate.name.label("shift_name"),
                ShiftTemplate.start_time,
                ShiftTemplate.end_time,
            )
            .join(Staff, Staff.id == StaffShiftPreference.staff_id)
            .join(ShiftTemplate, ShiftTemplate.id == StaffShiftPreference.shift_id)
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
    flash(t("msg_availability_entry_removed"), "success")
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
        flash(t("msg_shift_pref_required_fields"), "error")
        return redirect(url_for("availability"))
    if end_obj < start_obj:
        flash(t("msg_shift_pref_end_date_on_or_after_start"), "error")
        return redirect(url_for("availability"))
    if not shift_ids:
        flash(t("msg_select_preferred_shift"), "error")
        return redirect(url_for("availability"))

    added = 0
    try:
        staff_id_int = int(staff_id)
    except ValueError:
        flash(t("msg_invalid_staff"), "error")
        return redirect(url_for("availability"))

    staff = Staff.query.filter_by(id=staff_id_int, org_id=org_id).first()
    if staff is None:
        flash(t("msg_staff_member_not_found"), "error")
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
    flash(t("msg_added_preferred_shift_entries").format(count=added), "success")
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
    flash(t("msg_shift_preference_removed"), "success")
    return redirect(url_for("availability"))


@app.route("/roster", methods=["GET", "POST"])
@login_required
def roster() -> str:
    org_id = current_org_id()
    selected_date_raw = request.values.get("roster_date", "").strip()
    selected_obj = parse_iso_date(selected_date_raw)
    if selected_obj is None:
        end_date_raw = request.values.get("end_date", "").strip()
        end_obj = parse_iso_date(end_date_raw)
        if end_obj is not None:
            selected_obj = end_obj - timedelta(days=6)
    if selected_obj is None:
        selected_obj = date.today()
    selected_date = selected_obj.isoformat()
    week_start_obj = monday_for(selected_obj)
    version_id_raw = request.args.get("version_id", "").strip()
    edit_confirmed_mode_requested = request.args.get("edit_confirmed", "0").strip() == "1"

    current_version: Any | None = None
    if version_id_raw:
        try:
            selected_version_id = int(version_id_raw)
        except ValueError:
            abort(404)
        current_version = RosterVersion.query.filter_by(
            id=selected_version_id,
            org_id=org_id,
        ).first()
        if current_version is None:
            abort(404)
        week_start_obj = current_version.week_start
        week_end_obj = week_start_obj + timedelta(days=6)
        if not (week_start_obj <= selected_obj <= week_end_obj):
            selected_obj = week_start_obj
            selected_date = selected_obj.isoformat()

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
    if current_version is None:
        current_version = default_version

    today_obj = date.today()
    current_month_start, current_month_end = month_bounds(today_obj)
    confirmed_month_versions_rows = (
        RosterVersion.query.filter(
            RosterVersion.org_id == org_id,
            RosterVersion.status == "confirmed",
            RosterVersion.week_start.between(current_month_start, current_month_end),
        )
        .order_by(RosterVersion.week_start.asc(), RosterVersion.id.asc())
        .all()
    )
    confirmed_month_versions = []
    for version in confirmed_month_versions_rows:
        week_end_value = version.week_start + timedelta(days=6)
        confirmed_month_versions.append(
            {
                "id": version.id,
                "week_start": version.week_start.isoformat(),
                "label": f"{version.week_start.strftime('%d/%m')}-{week_end_value.strftime('%d/%m')}",
                "is_active": bool(current_version and current_version.id == version.id),
            }
        )

    can_edit_confirmed_current_version = bool(
        current_version is not None
        and current_version.status == "confirmed"
        and current_version.week_start.year == today_obj.year
        and current_version.week_start.month == today_obj.month
    )
    if (
        edit_confirmed_mode_requested
        and current_version is not None
        and current_version.status == "confirmed"
        and not can_edit_confirmed_current_version
    ):
        flash(t("msg_confirmed_edit_current_month_only"), "error")
        return redirect(
            url_for(
                "roster",
                roster_date=current_version.week_start.isoformat(),
                version_id=current_version.id,
            )
        )
    edit_confirmed_mode = edit_confirmed_mode_requested and can_edit_confirmed_current_version

    if request.method == "POST":
        # If user explicitly selected a confirmed version, keep it read-only.
        # Otherwise (default view), allow creating/filling a draft for manual edits.
        if (
            version_id_raw
            and current_version is not None
            and current_version.status == "confirmed"
        ):
            flash(t("msg_confirmed_read_only"), "error")
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
            flash(t("msg_staff_shift_required"), "error")
        else:
            try:
                staff_id_int = int(staff_id)
                shift_id_int = int(shift_id)
            except ValueError:
                flash(t("msg_invalid_staff_or_shift"), "error")
                return redirect(
                    url_for(
                        "roster",
                        roster_date=selected_date,
                        version_id=current_version.id if version_id_raw and current_version else None,
                    )
                )

            target_shift = ShiftTemplate.query.filter_by(id=shift_id_int, org_id=org_id).first()
            if target_shift is None:
                flash(t("msg_shift_not_found"), "error")
                return redirect(
                    url_for(
                        "roster",
                        roster_date=selected_date,
                        version_id=current_version.id if version_id_raw and current_version else None,
                    )
                )

            staff_member = Staff.query.filter_by(id=staff_id_int, org_id=org_id, active=1).first()
            if staff_member is None:
                flash(t("msg_staff_member_not_found"), "error")
                return redirect(
                    url_for(
                        "roster",
                        roster_date=selected_date,
                        version_id=current_version.id if version_id_raw and current_version else None,
                    )
                )

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
                flash(t("msg_staff_unavailable_on_date"), "error")
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
                    flash(t("msg_shift_overlap"), "error")
                    return redirect(
                        url_for(
                            "roster",
                            roster_date=selected_date,
                            version_id=current_version.id if version_id_raw and current_version else None,
                        )
                    )

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
                    flash(t("msg_assignment_added"), "success")
                    return redirect(
                        url_for(
                            "roster",
                            roster_date=selected_date,
                            version_id=current_version.id if version_id_raw and current_version else None,
                        )
                    )
                except IntegrityError:
                    db.session.rollback()
                    flash(t("msg_assignment_duplicate"), "error")

    staff_rows = Staff.query.filter_by(org_id=org_id, active=1).order_by(Staff.name).all()
    shift_rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()

    week_columns = [
        {
            "date": (week_start_obj + timedelta(days=offset)).isoformat(),
            "weekday": t(f"weekday_{(week_start_obj + timedelta(days=offset)).weekday()}"),
        }
        for offset in range(7)
    ]
    week_dates = [item["date"] for item in week_columns]
    week_end_obj = week_start_obj + timedelta(days=6)
    week_range_label = f"From {format_date(week_start_obj)} to {format_date(week_end_obj)}"
    is_historical_view = (
        current_version is not None
        and default_version is not None
        and current_version.id != default_version.id
    )
    assignments: list[dict[str, Any]] = []
    if current_version is not None:
        assignment_rows = (
            db.session.query(
                RosterAssignment.id,
                RosterAssignment.roster_date,
                RosterAssignment.staff_id,
                RosterAssignment.shift_id,
                RosterAssignment.notes,
                Staff.name.label("staff_name"),
                Staff.role.label("staff_role"),
                ShiftTemplate.name.label("shift_name"),
                ShiftTemplate.start_time,
                ShiftTemplate.end_time,
            )
            .join(RosterVersion, RosterVersion.id == RosterAssignment.version_id)
            .join(Staff, Staff.id == RosterAssignment.staff_id)
            .join(ShiftTemplate, ShiftTemplate.id == RosterAssignment.shift_id)
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
        assignments = [
            {
                "id": row.id,
                "roster_date": row.roster_date,
                "staff_id": row.staff_id,
                "shift_id": row.shift_id,
                "notes": row.notes,
                "staff_name": row.staff_name,
                "staff_role": row.staff_role,
                "shift_name": row.shift_name,
                "start_time": row.start_time,
                "end_time": row.end_time,
            }
            for row in assignment_rows
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

    editable_assignment_map: dict[int, dict[str, int]] = {
        row.id: {day_value: 0 for day_value in week_dates}
        for row in staff_rows
    }
    multi_assignment_cell_keys: set[str] = set()
    for row in assignments:
        staff_entry = editable_assignment_map.get(row["staff_id"])
        if staff_entry is None:
            continue
        roster_date_value = row["roster_date"]
        if roster_date_value not in staff_entry:
            continue
        if staff_entry[roster_date_value] == 0:
            staff_entry[roster_date_value] = int(row["shift_id"])
        elif staff_entry[roster_date_value] != int(row["shift_id"]):
            multi_assignment_cell_keys.add(f"{row['staff_id']}_{roster_date_value}")

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
        confirmed_month_versions=confirmed_month_versions,
        edit_confirmed_mode=edit_confirmed_mode,
        editable_assignment_map=editable_assignment_map,
        multi_assignment_cell_keys=multi_assignment_cell_keys,
    )


@app.post("/roster/auto-schedule")
@login_required
def auto_schedule() -> Any:
    week_start_raw = request.form.get("week_start", "")
    week_start = parse_iso_date(week_start_raw)
    if week_start is None:
        flash(t("msg_invalid_week_start_date"), "error")
        return redirect(url_for("roster"))

    try:
        added, unfilled, ran = auto_schedule_week(week_start)
    except IntegrityError:
        db.session.rollback()
        flash(t("msg_auto_schedule_duplicate"), "error")
        return redirect(url_for("roster", roster_date=week_start.isoformat()))
    if ran == 0:
        flash(t("msg_auto_schedule_requirements"), "error")
    else:
        flash(
            t("msg_auto_schedule_completed").format(
                week_start=format_date(week_start),
                added=added,
                unfilled=unfilled,
            ),
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
            flash(t("msg_roster_version_not_found"), "error")
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
        version.updated_at = now_utc
        db.session.commit()

        payload = {
            "version": {
                "id": version.id,
                "org_id": version.org_id,
                "week_start": version.week_start.isoformat(),
                "status": version.status,
                "confirmed_at": version.confirmed_at.isoformat() if version.confirmed_at else None,
                "updated_at": version.updated_at.isoformat() if version.updated_at else None,
            },
            "deleted_version_ids": deleted_version_ids,
        }
        if request.is_json or request.args.get("format") == "json":
            return jsonify(payload), 200

        flash(t("msg_roster_confirmed"), "success")
        target_date = roster_date or version.week_start.isoformat()
        return redirect(url_for("roster", roster_date=target_date))
    except IntegrityError:
        db.session.rollback()
        if request.is_json or request.args.get("format") == "json":
            return jsonify({"error": "Unable to confirm roster version."}), 409
        flash(t("msg_roster_confirm_failed"), "error")
        return redirect(url_for("roster", roster_date=roster_date or date.today().isoformat()))


@app.post("/roster/confirmed/<int:version_id>/override")
@login_required
def confirm_confirmed_roster_override(version_id: int) -> Any:
    org_id = current_org_id()
    version = RosterVersion.query.filter_by(id=version_id, org_id=org_id, status="confirmed").first()
    if version is None:
        abort(404)

    today_obj = date.today()
    if version.week_start.year != today_obj.year or version.week_start.month != today_obj.month:
        flash(t("msg_confirmed_edit_current_month_only"), "error")
        return redirect(
            url_for(
                "roster",
                roster_date=version.week_start.isoformat(),
                version_id=version.id,
            )
        )

    week_start_obj = version.week_start
    week_end_obj = week_start_obj + timedelta(days=6)
    week_dates = each_date(week_start_obj, week_end_obj)

    staff_rows = Staff.query.filter_by(org_id=org_id, active=1).order_by(Staff.name).all()
    staff_ids = [row.id for row in staff_rows]
    editable_staff_ids = set(staff_ids)
    shift_rows = ShiftTemplate.query.filter_by(org_id=org_id).order_by(ShiftTemplate.start_time).all()
    shift_ids = {row.id for row in shift_rows}

    submitted_assignments: list[tuple[int, str, int]] = []
    for staff_id in staff_ids:
        for day_value in week_dates:
            field_name = f"assignment_{staff_id}_{day_value}"
            selected_shift_raw = (request.form.get(field_name, "0") or "0").strip()
            try:
                selected_shift_id = int(selected_shift_raw)
            except ValueError:
                flash(t("msg_invalid_staff_or_shift"), "error")
                return redirect(
                    url_for(
                        "roster",
                        roster_date=week_start_obj.isoformat(),
                        version_id=version.id,
                        edit_confirmed=1,
                    )
                )

            # "0" means no assignment for that cell (absent/no-show equivalent).
            if selected_shift_id == 0:
                continue
            if selected_shift_id not in shift_ids:
                flash(t("msg_shift_not_found"), "error")
                return redirect(
                    url_for(
                        "roster",
                        roster_date=week_start_obj.isoformat(),
                        version_id=version.id,
                        edit_confirmed=1,
                    )
                )
            submitted_assignments.append((staff_id, day_value, selected_shift_id))

    try:
        existing_assignments = RosterAssignment.query.filter_by(
            org_id=org_id,
            version_id=version.id,
        ).all()
        preserved_assignments = [
            row
            for row in existing_assignments
            if row.staff_id not in editable_staff_ids
        ]

        RosterAssignment.query.filter_by(org_id=org_id, version_id=version.id).delete(synchronize_session=False)
        for row in preserved_assignments:
            db.session.add(
                RosterAssignment(
                    org_id=org_id,
                    version_id=version.id,
                    roster_date=row.roster_date,
                    staff_id=row.staff_id,
                    shift_id=row.shift_id,
                    notes=row.notes,
                )
            )
        for staff_id, roster_date_value, shift_id in submitted_assignments:
            db.session.add(
                RosterAssignment(
                    org_id=org_id,
                    version_id=version.id,
                    roster_date=roster_date_value,
                    staff_id=staff_id,
                    shift_id=shift_id,
                    notes=None,
                )
            )
        version.updated_at = datetime.utcnow()
        db.session.commit()
        flash(t("msg_confirmed_roster_override_saved"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(t("msg_roster_confirm_failed"), "error")

    return redirect(
        url_for(
            "roster",
            roster_date=week_start_obj.isoformat(),
            version_id=version.id,
        )
    )


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
    org_id = current_org_id()
    assignment = (
        RosterAssignment.query.join(RosterVersion, RosterVersion.id == RosterAssignment.version_id)
        .filter(
            RosterAssignment.id == assignment_id,
            RosterAssignment.org_id == org_id,
            RosterVersion.org_id == org_id,
        )
        .first()
    )
    if assignment is None:
        abort(404)

    if assignment.version.status != "draft":
        abort(403)

    target_date = roster_date or assignment.version.week_start.isoformat()
    db.session.delete(assignment)
    db.session.commit()
    flash(t("msg_assignment_removed"), "success")
    return redirect(url_for("roster", roster_date=target_date))


@app.route("/payroll")
@login_required
@payroll_access_required
def payroll() -> str | Response:
    org_id = current_org_id()
    today_obj = date.today()
    default_start_obj, default_end_obj = month_bounds(today_obj)

    start_raw = request.args.get("start_date", "").strip()
    end_raw = request.args.get("end_date", "").strip()
    start_obj = parse_iso_date(start_raw) if start_raw else default_start_obj
    end_obj = parse_iso_date(end_raw) if end_raw else default_end_obj
    if start_obj is None or end_obj is None:
        flash(t("msg_invalid_payroll_date_range"), "error")
        start_obj, end_obj = default_start_obj, default_end_obj
    if end_obj < start_obj:
        flash(t("msg_end_date_on_or_after_start"), "error")
        end_obj = start_obj

    start_date = start_obj.isoformat()
    end_date = end_obj.isoformat()
    date_columns = each_date(start_obj, end_obj)

    selected_staff_raw = request.args.get("staff_id", "").strip()
    selected_staff_id: int | None = None
    if selected_staff_raw:
        try:
            selected_staff_id = int(selected_staff_raw)
        except ValueError:
            flash(t("msg_invalid_staff_filter"), "error")

    department_rows = (
        db.session.query(Staff.department)
        .filter(
            Staff.org_id == org_id,
            Staff.department.isnot(None),
            Staff.department != "",
        )
        .distinct()
        .order_by(Staff.department.asc())
        .all()
    )
    departments = [str(row.department) for row in department_rows if row.department]
    selected_department = request.args.get("department", "").strip()
    if selected_department and selected_department not in departments:
        flash(t("msg_invalid_department_filter"), "error")
        selected_department = ""

    staff_options_query = Staff.query.filter(Staff.org_id == org_id)
    if selected_department:
        staff_options_query = staff_options_query.filter(Staff.department == selected_department)
    staff_options = staff_options_query.order_by(Staff.name).all()

    staff_query = Staff.query.filter(Staff.org_id == org_id)
    if selected_department:
        staff_query = staff_query.filter(Staff.department == selected_department)
    if selected_staff_id is not None:
        staff_query = staff_query.filter(Staff.id == selected_staff_id)
    staff_rows = staff_query.order_by(Staff.name).all()
    staff_ids = [row.id for row in staff_rows]

    payroll_rows: dict[int, dict[str, Any]] = {}
    total_by_date = {date_key: Decimal("0.00") for date_key in date_columns}
    grand_total_hours = Decimal("0.00")
    grand_total_salary = Decimal("0.00")

    for staff_row in staff_rows:
        wage_value = (
            Decimal(str(staff_row.hourly_wage)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if staff_row.hourly_wage is not None
            else Decimal("0.00")
        )
        payroll_rows[staff_row.id] = {
            "staff_id": staff_row.id,
            "staff_name": staff_row.name,
            "role": staff_row.role,
            "hours_by_date": {date_key: Decimal("0.00") for date_key in date_columns},
            "total_hours": Decimal("0.00"),
            "hourly_wage": wage_value,
            "wage_missing": staff_row.hourly_wage is None,
            "total_salary": Decimal("0.00"),
        }

    if staff_ids:
        assignment_query = (
            db.session.query(
                RosterAssignment.staff_id,
                RosterAssignment.roster_date,
                ShiftTemplate.start_time,
                ShiftTemplate.end_time,
            )
            .join(RosterVersion, RosterVersion.id == RosterAssignment.version_id)
            .join(ShiftTemplate, ShiftTemplate.id == RosterAssignment.shift_id)
            .join(Staff, Staff.id == RosterAssignment.staff_id)
            .filter(
                RosterAssignment.org_id == org_id,
                RosterVersion.org_id == org_id,
                ShiftTemplate.org_id == org_id,
                Staff.org_id == org_id,
                RosterVersion.status == "confirmed",
                RosterAssignment.roster_date.between(start_date, end_date),
                RosterAssignment.staff_id.in_(staff_ids),
            )
        )
        if selected_department:
            assignment_query = assignment_query.filter(Staff.department == selected_department)
        assignment_rows = assignment_query.order_by(
            RosterAssignment.roster_date,
            RosterAssignment.staff_id,
            ShiftTemplate.start_time,
        ).all()

        for row in assignment_rows:
            entry = payroll_rows.get(row.staff_id)
            if entry is None:
                continue
            duration = shift_duration_hours(str(row.start_time), str(row.end_time))
            roster_date = str(row.roster_date)
            if roster_date in entry["hours_by_date"]:
                entry["hours_by_date"][roster_date] += duration
            entry["total_hours"] += duration

    ordered_rows = []
    for _, entry in sorted(payroll_rows.items(), key=lambda item: item[1]["staff_name"].lower()):
        for date_key in date_columns:
            entry["hours_by_date"][date_key] = entry["hours_by_date"][date_key].quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            total_by_date[date_key] += entry["hours_by_date"][date_key]
        entry["total_hours"] = entry["total_hours"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        entry["total_salary"] = (entry["total_hours"] * entry["hourly_wage"]).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        grand_total_hours += entry["total_hours"]
        grand_total_salary += entry["total_salary"]
        ordered_rows.append(entry)

    grand_total_hours = grand_total_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    grand_total_salary = grand_total_salary.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if request.args.get("export", "").strip().lower() == "csv":
        headers = ["staff_name", "role", *date_columns, "total_hours", "hourly_wage", "total_salary"]
        csv_rows: list[dict[str, Any]] = []
        for entry in ordered_rows:
            line: dict[str, Any] = {
                "staff_name": entry["staff_name"],
                "role": entry["role"],
                "total_hours": format_money(entry["total_hours"]),
                "hourly_wage": format_money(entry["hourly_wage"]),
                "total_salary": format_money(entry["total_salary"]),
            }
            for date_key in date_columns:
                line[date_key] = format_money(entry["hours_by_date"][date_key])
            csv_rows.append(line)
        filename = f"payroll_{start_obj.strftime('%d%m%Y')}_{end_obj.strftime('%d%m%Y')}.csv"
        return csv_response(filename, headers, csv_rows)

    return render_template(
        "payroll.html",
        start_date=start_date,
        end_date=end_date,
        date_columns=date_columns,
        payroll_rows=ordered_rows,
        staff_options=staff_options,
        selected_staff_id=selected_staff_id,
        departments=departments,
        selected_department=selected_department,
        totals_row={
            "hours_by_date": total_by_date,
            "total_hours": grand_total_hours,
            "total_salary": grand_total_salary,
        },
    )


@app.route("/data")
@login_required
def data_page() -> str:
    today_obj = date.today()
    start_obj = monday_for(today_obj)
    end_obj = start_obj + timedelta(days=6)
    return render_template(
        "data.html",
        export_start_date=start_obj.isoformat(),
        export_end_date=end_obj.isoformat(),
    )


@app.route("/data/export/<dataset>")
@login_required
def export_dataset(dataset: str) -> Response:
    org_id = current_org_id()
    if dataset == "assignments":
        start_date_raw = request.args.get("start_date", "").strip()
        end_date_raw = request.args.get("end_date", "").strip()
        version_type = (request.args.get("version_type", "confirmed") or "confirmed").strip().lower()
        if version_type not in {"confirmed", "draft"}:
            flash(t("msg_invalid_roster_export_version_type"), "error")
            return redirect(url_for("data_page"))

        if start_date_raw and end_date_raw:
            start_obj = parse_iso_date(start_date_raw)
            end_obj = parse_iso_date(end_date_raw)
        else:
            start_obj = monday_for(date.today())
            end_obj = start_obj + timedelta(days=6)
            start_date_raw = start_obj.isoformat()
            end_date_raw = end_obj.isoformat()

        if not start_obj or not end_obj:
            flash(t("msg_invalid_export_date_range"), "error")
            return redirect(url_for("data_page"))
        if end_obj < start_obj:
            flash(t("msg_end_date_on_or_after_start"), "error")
            return redirect(url_for("data_page"))

        status_filter = ["confirmed"] if version_type == "confirmed" else ["draft"]
        rows = [
            {
                "roster_date": row.roster_date,
                "staff_id": row.staff_id,
                "staff_name": row.staff_name,
                "staff_role": row.staff_role,
                "shift_name": row.shift_name,
                "start_time": row.start_time,
            }
            for row in (
                db.session.query(
                    RosterAssignment.roster_date,
                    Staff.id.label("staff_id"),
                    Staff.name.label("staff_name"),
                    Staff.role.label("staff_role"),
                    ShiftTemplate.name.label("shift_name"),
                    ShiftTemplate.start_time,
                )
                .join(Staff, Staff.id == RosterAssignment.staff_id)
                .join(ShiftTemplate, ShiftTemplate.id == RosterAssignment.shift_id)
                .join(RosterVersion, RosterVersion.id == RosterAssignment.version_id)
                .filter(
                    RosterAssignment.org_id == org_id,
                    RosterAssignment.roster_date.between(start_obj.isoformat(), end_obj.isoformat()),
                    Staff.org_id == org_id,
                    ShiftTemplate.org_id == org_id,
                    RosterVersion.org_id == org_id,
                    RosterVersion.status.in_(status_filter),
                )
                .order_by(RosterAssignment.roster_date, Staff.name, ShiftTemplate.start_time)
                .all()
            )
        ]

        if not rows:
            filename = f"roster_{start_obj.strftime('%d%m%Y')}_{end_obj.strftime('%d%m%Y')}.csv"
            return Response(
                "staff_name,role\n",
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
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

        filename = f"roster_{start_obj.strftime('%d%m%Y')}_{end_obj.strftime('%d%m%Y')}.csv"

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
        start_date_raw = request.args.get("start_date", "").strip()
        end_date_raw = request.args.get("end_date", "").strip()
        if start_date_raw and end_date_raw:
            start_obj = parse_iso_date(start_date_raw)
            end_obj = parse_iso_date(end_date_raw)
        else:
            start_obj = monday_for(date.today())
            end_obj = start_obj + timedelta(days=6)
        if not start_obj or not end_obj:
            flash(t("msg_invalid_export_date_range"), "error")
            return redirect(url_for("data_page"))
        if end_obj < start_obj:
            flash(t("msg_end_date_on_or_after_start"), "error")
            return redirect(url_for("data_page"))

        rows = [
            {
                "id": row.id,
                "staff_name": row.staff_name,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "status": row.status,
                "notes": row.notes,
            }
            for row in (
                db.session.query(
                    StaffAvailability.id,
                    Staff.name.label("staff_name"),
                    StaffAvailability.start_date,
                    StaffAvailability.end_date,
                    StaffAvailability.status,
                    StaffAvailability.notes,
                )
                .join(Staff, Staff.id == StaffAvailability.staff_id)
                .filter(
                    StaffAvailability.org_id == org_id,
                    Staff.org_id == org_id,
                    StaffAvailability.start_date <= end_obj.isoformat(),
                    StaffAvailability.end_date >= start_obj.isoformat(),
                )
                .order_by(StaffAvailability.start_date, StaffAvailability.id)
                .all()
            )
        ]
        return csv_response(
            "availability.csv",
            ["id", "staff_name", "start_date", "end_date", "status", "notes"],
            rows,
        )

    flash(t("msg_unknown_dataset"), "error")
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
        flash(t("msg_choose_csv_file"), "error")
        return redirect(url_for("data_page"))

    try:
        content = file_obj.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash(t("msg_csv_utf8_required"), "error")
        return redirect(url_for("data_page"))

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        flash(t("msg_csv_no_data_rows"), "error")
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
            flash(t("msg_unknown_dataset"), "error")
            return redirect(url_for("data_page"))

        db.session.commit()
        flash(t("msg_import_finished").format(added=added, skipped=skipped), "success")
    except IntegrityError:
        db.session.rollback()
        flash(t("msg_import_failed_reference_or_duplicate"), "error")

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
        is_owner=True,
        is_active=True,
        expires_at=None,
    )
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin user created: {email} (org: {org_name})")


@app.cli.command("create-owner")
def create_owner() -> None:
    email = click.prompt("Owner email").strip().lower()
    while not email:
        click.echo("Email is required.")
        email = click.prompt("Owner email").strip().lower()

    if User.query.filter(func.lower(User.email) == email).first():
        click.echo("A user with that email already exists.")
        return

    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    while not password:
        click.echo("Password is required.")
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    org_rows = Organization.query.order_by(Organization.id.asc()).all()
    if not org_rows:
        default_org_name = f"{email.split('@')[0]}'s Organization"
        org_name = click.prompt("Organization name", default=default_org_name).strip()
        while not org_name:
            click.echo("Organization name is required.")
            org_name = click.prompt("Organization name", default=default_org_name).strip()
        org = Organization(name=org_name)
        db.session.add(org)
        db.session.flush()
    else:
        click.echo("Available organizations:")
        for org in org_rows:
            click.echo(f"- {org.id}: {org.name}")
        org_id = click.prompt("Organization ID", type=int)
        org = Organization.query.filter_by(id=org_id).first()
        if org is None:
            click.echo("Organization not found.")
            return

    user = User(
        email=email,
        password_hash=generate_password_hash(password),
        role="owner",
        org_id=org.id,
        is_owner=True,
        is_active=True,
        expires_at=None,
    )
    db.session.add(user)
    db.session.commit()
    click.echo(f"Owner user created: {email} (org: {org.name})")


with app.app_context():
    db.create_all()
    try:
        ensure_user_schema_compatibility()
        ensure_staff_schema_compatibility()
        ensure_roster_schema_compatibility()
    except SQLAlchemyError:
        db.session.rollback()
        raise


if __name__ == "__main__":
    app.run(debug=True)




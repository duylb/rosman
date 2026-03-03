from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Any

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash


def create_duy_blueprint(
    db: Any,
    User: Any,
    Organization: Any,
    login_required: Any,
    parse_iso_datetime: Any,
) -> Blueprint:
    bp = Blueprint("duy", __name__, url_prefix="/duy")

    def is_owner_user() -> bool:
        user = getattr(g, "user", None)
        if user is None:
            return False
        role = (user.role or "").strip().lower()
        return bool(getattr(user, "is_owner", False)) or role == "owner"

    def owner_required(func: Any) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not is_owner_user():
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    @bp.get("/")
    @login_required
    @owner_required
    def panel() -> str:
        org_rows = Organization.query.order_by(Organization.name.asc()).all()
        now_utc = datetime.utcnow()
        users = (
            db.session.query(
                User.id,
                User.email,
                User.org_id,
                Organization.name.label("org_name"),
                User.is_active,
                User.expires_at,
                User.is_owner,
            )
            .join(Organization, Organization.id == User.org_id)
            .order_by(User.is_owner.desc(), User.email.asc())
            .all()
        )

        user_rows: list[dict[str, Any]] = []
        for row in users:
            expired = bool(row.expires_at and row.expires_at <= now_utc)
            if expired:
                status_key = "status_expired"
            elif not bool(row.is_active):
                status_key = "status_locked"
            else:
                status_key = "status_active"
            user_rows.append(
                {
                    "id": row.id,
                    "email": row.email,
                    "org_name": row.org_name,
                    "org_id": row.org_id,
                    "is_active": bool(row.is_active),
                    "expires_at": row.expires_at,
                    "is_owner": bool(row.is_owner),
                    "status_key": status_key,
                }
            )

        return render_template("duy/panel.html", users=user_rows, organizations=org_rows)

    @bp.post("/users/create")
    @login_required
    @owner_required
    def create_user() -> Any:
        email = (request.form.get("email", "") or "").strip().lower()
        password = request.form.get("password", "") or ""
        org_id_raw = (request.form.get("org_id", "") or "").strip()
        expires_at_raw = (request.form.get("expires_at", "") or "").strip()
        owner_requested = request.form.get("is_owner") == "1"

        if not email or not password or not org_id_raw:
            flash("msg_duy_create_required", "error")
            return redirect(url_for("duy.panel"))

        try:
            org_id = int(org_id_raw)
        except ValueError:
            flash("msg_duy_invalid_org", "error")
            return redirect(url_for("duy.panel"))

        org = Organization.query.filter_by(id=org_id).first()
        if org is None:
            flash("msg_duy_invalid_org", "error")
            return redirect(url_for("duy.panel"))

        if User.query.filter(func.lower(User.email) == email).first() is not None:
            flash("msg_duy_email_exists", "error")
            return redirect(url_for("duy.panel"))

        expires_at = parse_iso_datetime(expires_at_raw) if expires_at_raw else None
        if expires_at_raw and expires_at is None:
            flash("msg_duy_invalid_expiration", "error")
            return redirect(url_for("duy.panel"))

        owner_exists = (
            db.session.query(User.id)
            .filter(User.is_owner == 1)
            .first()
            is not None
        )
        is_owner = owner_requested or not owner_exists

        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            org_id=org_id,
            role="owner" if is_owner else "manager",
            is_owner=is_owner,
            is_active=True,
            expires_at=expires_at,
        )
        db.session.add(user)
        try:
            db.session.commit()
            flash("msg_duy_user_created", "success")
        except IntegrityError:
            db.session.rollback()
            flash("msg_duy_email_exists", "error")

        return redirect(url_for("duy.panel"))

    @bp.post("/users/<int:user_id>/toggle-active")
    @login_required
    @owner_required
    def toggle_active(user_id: int) -> Any:
        target = User.query.filter_by(id=user_id).first()
        if target is None:
            flash("msg_duy_user_not_found", "error")
            return redirect(url_for("duy.panel"))

        if bool(target.is_owner):
            target.is_active = True
            db.session.commit()
            flash("msg_duy_owner_lock_forbidden", "error")
            return redirect(url_for("duy.panel"))

        target.is_active = not bool(target.is_active)
        db.session.commit()
        flash("msg_duy_user_status_updated", "success")
        return redirect(url_for("duy.panel"))

    @bp.post("/users/<int:user_id>/extend")
    @login_required
    @owner_required
    def extend_expiration(user_id: int) -> Any:
        target = User.query.filter_by(id=user_id).first()
        if target is None:
            flash("msg_duy_user_not_found", "error")
            return redirect(url_for("duy.panel"))

        expires_at_raw = (request.form.get("expires_at", "") or "").strip()
        expires_at = parse_iso_datetime(expires_at_raw) if expires_at_raw else None
        if expires_at is None:
            flash("msg_duy_invalid_expiration", "error")
            return redirect(url_for("duy.panel"))

        target.expires_at = expires_at
        db.session.commit()
        flash("msg_duy_expiration_updated", "success")
        return redirect(url_for("duy.panel"))

    return bp

import os
import re
import traceback
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from app.extensions import csrf, db
from app.models import Organization, SaleItem, SalesReport

sales_api = Blueprint("sales_api", __name__)
API_KEY = os.environ.get("SALES_API_KEY")


def parse_date_value(raw: str) -> datetime:
    value = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid date format. Use DD/MM/YYYY or YYYY-MM-DD.")


def parse_datetime_value(raw: str) -> datetime:
    value = (raw or "").strip()
    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid datetime format.")


def get_nested_value(payload: dict[str, object], path: tuple[str, ...]) -> object:
    current: object = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def first_non_empty_str(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def infer_month_bounds_from_created_datetime(raw_created: object) -> tuple[str, str]:
    if not raw_created:
        return "", ""
    created_obj = parse_datetime_value(str(raw_created))
    month_start = created_obj.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    return month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")


def parse_decimal_value(raw: object, fallback: Decimal = Decimal("0")) -> Decimal:
    if raw is None or raw == "":
        return fallback
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return fallback


def build_item_code(item: dict[str, object], index: int) -> str:
    raw_code = str(item.get("item_code", item.get("product_code", "")) or "").strip()
    if raw_code:
        return raw_code
    raw_name = str(item.get("item_name", item.get("product_name", "")) or "").strip().upper()
    normalized = re.sub(r"[^A-Z0-9]+", "", raw_name)[:24]
    if normalized:
        return f"AUTO-{normalized}"
    return f"AUTO-{index + 1:05d}"


@sales_api.route("/api/import-sales", methods=["POST"])
@csrf.exempt
def import_sales():
    if not API_KEY or request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        print("Incoming JSON:", data)

        organization_name = str(data.get("organization", "")).strip()
        org_id_raw = data.get("org_id")
        organization: Organization | None = None

        if organization_name:
            organization = Organization.query.filter_by(name=organization_name).first()
            if organization is None:
                organization = Organization(name=organization_name)
                db.session.add(organization)
                db.session.flush()
        elif org_id_raw is not None:
            try:
                org_id = int(org_id_raw)
            except (TypeError, ValueError):
                return jsonify({"status": "error", "message": "org_id must be an integer."}), 400
            organization = Organization.query.filter_by(id=org_id).first()
            if organization is None:
                return jsonify({"status": "error", "message": "organization not found for org_id."}), 404
        else:
            return jsonify({"status": "error", "message": "organization or org_id is required."}), 400

        start_date_raw = first_non_empty_str(
            data.get("start_date"),
            data.get("startDate"),
            data.get("report_start_date"),
            data.get("period_start"),
            get_nested_value(data, ("report_period", "start_date")),
            get_nested_value(data, ("reportPeriod", "startDate")),
        )
        end_date_raw = first_non_empty_str(
            data.get("end_date"),
            data.get("endDate"),
            data.get("report_end_date"),
            data.get("period_end"),
            get_nested_value(data, ("report_period", "end_date")),
            get_nested_value(data, ("reportPeriod", "endDate")),
        )
        if not start_date_raw or not end_date_raw:
            inferred_start, inferred_end = infer_month_bounds_from_created_datetime(data.get("created_datetime"))
            start_date_raw = start_date_raw or inferred_start
            end_date_raw = end_date_raw or inferred_end
        if not start_date_raw or not end_date_raw:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "start_date and end_date are required.",
                        "hints": [
                            "Provide start_date/end_date (DD/MM/YYYY or YYYY-MM-DD).",
                            "Accepted aliases: startDate/endDate, report_period.start_date/end_date.",
                        ],
                    }
                ),
                400,
            )
        report_title = str(data.get("report_title", "")).strip() or "Sales Report"
        branch = str(data.get("branch", "")).strip() or None
        summary_payload = data.get("summary") or {}

        items_payload = data.get("items")
        if items_payload is None:
            # Backward-compatible payload support.
            items_payload = data.get("products", [])
        if not isinstance(items_payload, list):
            return jsonify({"status": "error", "message": "items must be an array."}), 400

        normalized_items: list[dict[str, object]] = []
        for idx, item in enumerate(items_payload):
            item_code = build_item_code(item, idx)
            item_name = str(item.get("item_name", item.get("product_name", "")) or "").strip()
            if not item_name:
                return jsonify({"status": "error", "message": "Each item requires item_name or product_name."}), 400

            revenue = parse_decimal_value(item.get("revenue"))
            returned_quantity = int(item.get("returned_quantity", item.get("return_units", 0)) or 0)
            returned_amount = parse_decimal_value(item.get("returned_amount", item.get("return_value", 0)))
            net_revenue = parse_decimal_value(item.get("net_revenue"), revenue - returned_amount)
            quantity = int(item.get("quantity", item.get("units_sold", 0)) or 0)

            normalized_items.append(
                {
                    "item_code": item_code,
                    "item_name": item_name,
                    "revenue": revenue,
                    "returned_quantity": max(0, returned_quantity),
                    "returned_amount": returned_amount,
                    "net_revenue": net_revenue,
                    "quantity": max(0, quantity),
                }
            )

        report = SalesReport(
            org_id=organization.id,
            report_title=report_title,
            start_date=parse_date_value(start_date_raw),
            end_date=parse_date_value(end_date_raw),
            branch=branch,
            created_datetime=parse_datetime_value(data.get("created_datetime")) if data.get("created_datetime") else datetime.utcnow(),
            total_products=int(summary_payload.get("total_products", len(normalized_items)) or len(normalized_items)),
            total_units_sold=int(
                summary_payload.get("total_units_sold", sum(int(item["quantity"]) for item in normalized_items))
                or 0
            ),
            total_revenue=parse_decimal_value(
                summary_payload.get("total_revenue", sum(parse_decimal_value(item["revenue"]) for item in normalized_items))
            ),
            total_return_units=int(
                summary_payload.get("total_return_units", sum(int(item["returned_quantity"]) for item in normalized_items))
                or 0
            ),
            total_return_value=parse_decimal_value(
                summary_payload.get("total_return_value", sum(parse_decimal_value(item["returned_amount"]) for item in normalized_items))
            ),
            net_revenue=parse_decimal_value(
                summary_payload.get("net_revenue", sum(parse_decimal_value(item["net_revenue"]) for item in normalized_items))
            ),
        )
        db.session.add(report)
        db.session.flush()

        for item in normalized_items:
            product = SaleItem(
                report_id=report.id,
                item_code=str(item["item_code"]),
                item_name=str(item["item_name"]),
                units_sold=int(item["quantity"]),
                revenue=item["revenue"],
                returned_quantity=int(item["returned_quantity"]),
                returned_amount=item["returned_amount"],
                net_revenue=item["net_revenue"],
                quantity=int(item["quantity"]),
            )
            db.session.add(product)

        db.session.commit()
        return {
            "status": "success",
            "report_id": report.id,
            "organization_id": organization.id,
            "organization": organization.name,
            "items_inserted": len(normalized_items),
        }
    except Exception as e:
        db.session.rollback()
        print("ERROR:", str(e))
        traceback.print_exc()
        return {"status": "error", "message": str(e)}, 500

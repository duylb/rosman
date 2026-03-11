import os
import re
import traceback
from datetime import datetime
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

        start_date_raw = str(data.get("start_date", "")).strip()
        end_date_raw = str(data.get("end_date", "")).strip()
        if not start_date_raw or not end_date_raw:
            return jsonify({"status": "error", "message": "start_date and end_date are required."}), 400

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
            organization_id=organization.id,
            report_title=organization.name,
            start_date=parse_date_value(start_date_raw),
            end_date=parse_date_value(end_date_raw),
            created_datetime=parse_datetime_value(data.get("created_datetime")) if data.get("created_datetime") else datetime.utcnow(),
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

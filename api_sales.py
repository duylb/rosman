import os
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import csrf, db
from app.models import ProductSale, SalesReport

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


@sales_api.route("/api/import-sales", methods=["POST"])
@csrf.exempt
def import_sales():
    if not API_KEY or request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        print("Incoming JSON:", data)

        org_id = data.get("org_id")
        if org_id is None:
            return jsonify({"status": "error", "message": "org_id is required."}), 400
        try:
            org_id = int(org_id)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "org_id must be an integer."}), 400

        summary = data.get("summary") or {}
        products = data.get("products") or []
        if not isinstance(products, list):
            return jsonify({"status": "error", "message": "products must be an array."}), 400
        for required_key in ("report_title", "start_date", "end_date", "branch"):
            if not str(data.get(required_key, "")).strip():
                return jsonify({"status": "error", "message": f"{required_key} is required."}), 400

        total_units_from_rows = 0
        total_revenue_from_rows = 0
        total_return_units_from_rows = 0
        total_return_value_from_rows = 0
        normalized_products = []
        for p in products:
            units_sold = int(p.get("units_sold", 0) or 0)
            revenue = float(p.get("revenue", 0) or 0)
            return_units = int(p.get("return_units", 0) or 0)
            return_value = float(p.get("return_value", 0) or 0)
            total_units_from_rows += units_sold
            total_revenue_from_rows += revenue
            total_return_units_from_rows += return_units
            total_return_value_from_rows += return_value
            normalized_products.append(
                {
                    "product_code": p.get("product_code", "") or "",
                    "product_name": p.get("product_name", "") or "",
                    "units_sold": units_sold,
                    "revenue": revenue,
                    "return_units": return_units,
                    "return_value": return_value,
                }
            )

        report = SalesReport(
            org_id=org_id,
            report_title=data["report_title"],
            start_date=parse_date_value(data["start_date"]),
            end_date=parse_date_value(data["end_date"]),
            branch=data["branch"],
            created_datetime=parse_datetime_value(data.get("created_datetime")) if data.get("created_datetime") else datetime.utcnow(),
            total_products=int(summary.get("total_products", len(normalized_products)) or len(normalized_products)),
            total_units_sold=int(summary.get("total_units_sold", total_units_from_rows) or total_units_from_rows),
            total_revenue=float(summary.get("total_revenue", total_revenue_from_rows) or total_revenue_from_rows),
            total_return_value=float(
                summary.get("total_return_value", total_return_value_from_rows) or total_return_value_from_rows
            ),
            total_return_units=int(
                summary.get("total_return_units", total_return_units_from_rows) or total_return_units_from_rows
            ),
        )
        db.session.add(report)
        db.session.flush()

        for p in normalized_products:
            product = ProductSale(
                report_id=report.id,
                product_code=p["product_code"],
                product_name=p["product_name"],
                units_sold=p["units_sold"],
                revenue=p["revenue"],
                return_units=p["return_units"],
                return_value=p["return_value"],
            )
            db.session.add(product)

        db.session.commit()
        return {"status": "success", "report_id": report.id}
    except Exception as e:
        db.session.rollback()
        print("ERROR:", str(e))
        traceback.print_exc()
        return {"status": "error", "message": str(e)}, 500

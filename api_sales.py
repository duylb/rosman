import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import ProductSale, SalesReport

sales_api = Blueprint("sales_api", __name__)
API_KEY = os.environ.get("SALES_API_KEY", "Baoduy567")


@sales_api.route("/api/import-sales", methods=["POST"])
def import_sales():
    if request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    try:
        report = SalesReport(
            report_title=data["report_title"],
            start_date=datetime.strptime(data["start_date"], "%d/%m/%Y").date(),
            end_date=datetime.strptime(data["end_date"], "%d/%m/%Y").date(),
            branch=data["branch"],
            created_datetime=datetime.strptime(data["created_datetime"], "%d/%m/%Y %H:%M"),
            total_products=data["summary"]["total_products"],
            total_units_sold=data["summary"]["total_units_sold"],
            total_revenue=data["summary"]["total_revenue"],
            total_return_value=data["summary"]["total_return_value"],
            total_return_units=data["summary"]["total_return_units"],
        )
        db.session.add(report)
        db.session.flush()

        for p in data["products"]:
            product = ProductSale(
                report_id=report.id,
                product_code=p["product_code"],
                product_name=p["product_name"],
                units_sold=p["units_sold"],
                revenue=p["revenue"],
                return_units=p["return_units"],
                return_value=p["return_value"],
                net_revenue=float(p["revenue"]) - float(p["return_value"]),
            )
            db.session.add(product)

        db.session.commit()
        return jsonify({"status": "success", "report_id": report.id}), 201
    except (KeyError, TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Invalid payload: {exc}"}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to import sales"}), 500

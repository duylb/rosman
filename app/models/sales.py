from __future__ import annotations

from app.extensions import db
from sqlalchemy.orm import synonym


class SalesReport(db.Model):
    __tablename__ = "sales_reports"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    report_title = db.Column(db.String(200), nullable=True)
    start_date = db.Column(db.Date, nullable=True, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    branch = db.Column(db.String(200), nullable=True)
    created_datetime = db.Column(db.DateTime, nullable=False, default=db.func.now())
    total_products = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    total_units_sold = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    total_revenue = db.Column(db.Float, nullable=False, server_default=db.text("0"))
    total_return_value = db.Column(db.Float, nullable=False, server_default=db.text("0"))
    total_return_units = db.Column(db.Integer, nullable=False, server_default=db.text("0"))

    organization = db.relationship("Organization", back_populates="sale_reports")
    product_sales = db.relationship(
        "ProductSale",
        back_populates="sales_report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Backward-compatible aliases for existing app code.
    filename = synonym("report_title")
    imported_at = synonym("created_datetime")

    @property
    def sale_items(self) -> list["ProductSale"]:
        return self.product_sales

    @sale_items.setter
    def sale_items(self, value: list["ProductSale"]) -> None:
        self.product_sales = value


class ProductSale(db.Model):
    __tablename__ = "product_sales"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_code = db.Column(db.String(50), nullable=True, index=True)
    product_name = db.Column(db.String(200), nullable=True)
    units_sold = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    revenue = db.Column(db.Float, nullable=False, server_default=db.text("0"))
    return_units = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    return_value = db.Column(db.Float, nullable=False, server_default=db.text("0"))

    # Keep existing business views/filtering compatible.
    net_revenue = db.Column(db.Float, nullable=False, server_default=db.text("0"))
    category = db.Column(db.String(120), nullable=False, server_default=db.text("'Uncategorized'"), index=True)
    type = db.Column(db.String(120), nullable=False, server_default=db.text("'Other'"), index=True)

    sales_report = db.relationship("SalesReport", back_populates="product_sales")

    # Backward-compatible aliases for existing app code.
    sale_report_id = synonym("report_id")
    sku = synonym("product_code")
    name = synonym("product_name")
    quantity = synonym("units_sold")
    returns = synonym("return_units")

    @property
    def sale_report(self) -> SalesReport:
        return self.sales_report

    @sale_report.setter
    def sale_report(self, value: SalesReport) -> None:
        self.sales_report = value


# Backward-compatible class aliases.
SaleReport = SalesReport
SaleItem = ProductSale

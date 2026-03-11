from __future__ import annotations

from app.extensions import db
from sqlalchemy.orm import synonym


class SalesReport(db.Model):
    __tablename__ = "sales_reports"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_title = db.Column(db.String(255), nullable=False, server_default=db.text("'Sales Report'"))
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    created_datetime = db.Column(db.DateTime, nullable=False, default=db.func.now())
    branch = db.Column(db.String(160), nullable=True)
    total_products = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    total_units_sold = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    total_revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    total_return_units = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    total_return_value = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    net_revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="sale_reports")
    products = db.relationship(
        "SalesProduct",
        back_populates="report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Compatibility aliases for existing code.
    imported_at = synonym("created_datetime")
    filename = synonym("report_title")

    @property
    def sale_items(self) -> list["SalesProduct"]:
        return self.products

    @sale_items.setter
    def sale_items(self, value: list["SalesProduct"]) -> None:
        self.products = value

    @property
    def product_sales(self) -> list["SalesProduct"]:
        return self.products

    @product_sales.setter
    def product_sales(self, value: list["SalesProduct"]) -> None:
        self.products = value


class SalesProduct(db.Model):
    __tablename__ = "sales_items"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_code = db.Column(db.String(64), nullable=False, index=True)
    item_name = db.Column(db.String(255), nullable=False)
    units_sold = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    return_quantity = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    return_amount = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    net_revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    report = db.relationship("SalesReport", back_populates="products")

    # Backward-compatible aliases for existing app code.
    sale_report_id = synonym("report_id")
    product_code = synonym("item_code")
    product_name = synonym("item_name")
    sku = synonym("item_code")
    name = synonym("item_name")
    quantity = synonym("units_sold")
    returned_quantity = synonym("return_quantity")
    returned_amount = synonym("return_amount")
    return_units = synonym("return_quantity")
    returns = synonym("return_quantity")
    return_value = synonym("return_amount")

    @property
    def sale_report(self) -> SalesReport:
        return self.report

    @sale_report.setter
    def sale_report(self, value: SalesReport) -> None:
        self.report = value


# Backward-compatible class aliases.
SaleReport = SalesReport
SaleItem = SalesProduct
ProductSale = SalesProduct

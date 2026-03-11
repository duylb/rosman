from __future__ import annotations

from app.extensions import db
from sqlalchemy.orm import synonym


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.text("CURRENT_TIMESTAMP"))

    organization = db.relationship("Organization", back_populates="branches")
    sales_reports = db.relationship(
        "SalesReport",
        back_populates="branch",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    item_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.text("CURRENT_TIMESTAMP"))

    sales_report_items = db.relationship("SalesReportItem", back_populates="product")

    # Backward-compatible aliases.
    sku = synonym("item_code")
    name = synonym("item_name")


class SalesReport(db.Model):
    __tablename__ = "sales_reports"
    __table_args__ = (
        db.UniqueConstraint("branch_id", "start_date", "end_date", name="uq_sales_reports_branch_period"),
        db.Index("ix_sales_reports_start_end", "start_date", "end_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = db.Column(
        db.Integer,
        db.ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_title = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_datetime = db.Column(db.DateTime, nullable=True)
    total_products = db.Column(db.Integer, nullable=True)
    total_units_sold = db.Column(db.Integer, nullable=True)
    total_revenue = db.Column(db.Numeric(14, 2), nullable=True)
    total_return_units = db.Column(db.Integer, nullable=True)
    total_return_value = db.Column(db.Numeric(14, 2), nullable=True)
    net_revenue = db.Column(db.Numeric(14, 2), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, server_default=db.text("CURRENT_TIMESTAMP"))

    organization = db.relationship("Organization", back_populates="sales_reports")
    branch = db.relationship("Branch", back_populates="sales_reports")
    sales_report_items = db.relationship(
        "SalesReportItem",
        back_populates="sales_report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Backward-compatible aliases used by existing code.
    org_id = synonym("organization_id")
    imported_at = synonym("created_datetime")
    created_at = synonym("uploaded_at")
    filename = synonym("report_title")

    @property
    def products(self) -> list["SalesReportItem"]:
        return self.sales_report_items

    @products.setter
    def products(self, value: list["SalesReportItem"]) -> None:
        self.sales_report_items = value

    @property
    def sale_items(self) -> list["SalesReportItem"]:
        return self.sales_report_items

    @sale_items.setter
    def sale_items(self, value: list["SalesReportItem"]) -> None:
        self.sales_report_items = value


class SalesReportItem(db.Model):
    __tablename__ = "sales_report_items"

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey("sales_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    units_sold = db.Column(db.Integer, nullable=True)
    revenue = db.Column(db.Numeric(14, 2), nullable=True)
    return_quantity = db.Column(db.Integer, nullable=True)
    return_amount = db.Column(db.Numeric(14, 2), nullable=True)
    net_revenue = db.Column(db.Numeric(14, 2), nullable=True)

    sales_report = db.relationship("SalesReport", back_populates="sales_report_items")
    product = db.relationship("Product", back_populates="sales_report_items")

    # Backward-compatible aliases used by existing code paths.
    sale_report_id = synonym("report_id")
    quantity = synonym("units_sold")
    returned_quantity = synonym("return_quantity")
    returned_amount = synonym("return_amount")
    return_units = synonym("return_quantity")
    returns = synonym("return_quantity")
    return_value = synonym("return_amount")

    @property
    def item_code(self) -> str | None:
        return self.product.item_code if self.product else None

    @property
    def item_name(self) -> str | None:
        return self.product.item_name if self.product else None

    @property
    def sku(self) -> str | None:
        return self.item_code

    @property
    def name(self) -> str | None:
        return self.item_name


# Backward-compatible aliases.
SaleReport = SalesReport
SaleItem = SalesReportItem
SalesProduct = SalesReportItem
ProductSale = SalesReportItem

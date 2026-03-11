from __future__ import annotations

from typing import ClassVar

from app.extensions import db
from sqlalchemy.orm import synonym


class SalesReport(db.Model):
    __tablename__ = "sales_reports"
    __allow_unmapped__ = True

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date = db.Column(db.Date, nullable=True, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    created_datetime = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="sale_reports")
    sales_items = db.relationship(
        "SalesItem",
        back_populates="sales_report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Backward-compatible aliases for existing app code/query filters.
    org_id = synonym("organization_id")
    imported_at = synonym("created_datetime")

    # Legacy placeholders retained so old code paths can assign without crashing.
    _legacy_report_title: ClassVar[str | None] = None
    _legacy_total_revenue: ClassVar[float | None] = None
    _legacy_branch: ClassVar[str | None] = None

    @property
    def filename(self) -> str | None:
        return self._legacy_report_title

    @filename.setter
    def filename(self, value: str | None) -> None:
        self._legacy_report_title = value

    @property
    def report_title(self) -> str | None:
        return self._legacy_report_title

    @report_title.setter
    def report_title(self, value: str | None) -> None:
        self._legacy_report_title = value

    @property
    def branch(self) -> str | None:
        return self._legacy_branch

    @branch.setter
    def branch(self, value: str | None) -> None:
        self._legacy_branch = value

    @property
    def total_revenue(self) -> float:
        if self._legacy_total_revenue is not None:
            return float(self._legacy_total_revenue)
        return float(sum(float(item.net_revenue or 0) for item in self.sales_items))

    @total_revenue.setter
    def total_revenue(self, value: float | int | None) -> None:
        self._legacy_total_revenue = float(value or 0)

    @property
    def sale_items(self) -> list["SalesItem"]:
        return self.sales_items

    @sale_items.setter
    def sale_items(self, value: list["SalesItem"]) -> None:
        self.sales_items = value

    @property
    def product_sales(self) -> list["SalesItem"]:
        return self.sales_items

    @product_sales.setter
    def product_sales(self, value: list["SalesItem"]) -> None:
        self.sales_items = value


class SalesItem(db.Model):
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
    revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    returned_quantity = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    returned_amount = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    net_revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))

    # Compatibility columns used by existing reporting screens.
    quantity = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    category = db.Column(db.String(120), nullable=False, server_default=db.text("'Uncategorized'"), index=True)
    type = db.Column(db.String(120), nullable=False, server_default=db.text("'Other'"), index=True)

    sales_report = db.relationship("SalesReport", back_populates="sales_items")

    # Backward-compatible aliases for existing app code.
    sale_report_id = synonym("report_id")
    product_code = synonym("item_code")
    product_name = synonym("item_name")
    sku = synonym("item_code")
    name = synonym("item_name")
    return_units = synonym("returned_quantity")
    returns = synonym("returned_quantity")
    return_value = synonym("returned_amount")

    @property
    def sale_report(self) -> SalesReport:
        return self.sales_report

    @sale_report.setter
    def sale_report(self, value: SalesReport) -> None:
        self.sales_report = value


# Backward-compatible class aliases.
SaleReport = SalesReport
SaleItem = SalesItem
ProductSale = SalesItem

from app.extensions import db


class SaleReport(db.Model):
    __tablename__ = "sale_reports"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=True, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    imported_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    total_revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))

    organization = db.relationship("Organization", back_populates="sale_reports")
    sale_items = db.relationship(
        "SaleItem",
        back_populates="sale_report",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_report_id = db.Column(
        db.Integer,
        db.ForeignKey("sale_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku = db.Column(db.Text, nullable=False, index=True)
    name = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    returns = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    return_value = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    net_revenue = db.Column(db.Numeric(14, 2), nullable=False, server_default=db.text("0"))
    category = db.Column(db.String(120), nullable=False, index=True)
    type = db.Column(db.String(120), nullable=False, index=True)

    sale_report = db.relationship("SaleReport", back_populates="sale_items")
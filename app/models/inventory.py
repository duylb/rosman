from app.extensions import db


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(160), nullable=False)
    contact = db.Column(db.Text, nullable=True)
    lead_time_days = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="suppliers")
    inventory_items = db.relationship("InventoryItem", back_populates="supplier")


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"
    __table_args__ = (
        db.UniqueConstraint("org_id", "sku", name="uq_inventory_items_org_sku"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sku = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    unit = db.Column(db.String(20), nullable=False, server_default=db.text("'pcs'"))
    minimum_stock_level = db.Column(db.Numeric(12, 2), nullable=False, server_default=db.text("0"))
    current_stock = db.Column(db.Numeric(12, 2), nullable=False, server_default=db.text("0"))
    unit_cost = db.Column(db.Numeric(12, 2), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="inventory_items")
    supplier = db.relationship("Supplier", back_populates="inventory_items")
    recipes = db.relationship(
        "Recipe",
        back_populates="inventory_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stock_logs = db.relationship(
        "StockLog",
        back_populates="inventory_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Recipe(db.Model):
    __tablename__ = "recipes"
    __table_args__ = (
        db.UniqueConstraint(
            "org_id",
            "sale_item_ref",
            "match_type",
            "inventory_item_id",
            name="uq_recipe_org_ref_match_inventory",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # match_type=exact => sale_item_ref is full SKU (e.g. BC001)
    # match_type=prefix => sale_item_ref is prefix (e.g. BC, BT, FB)
    match_type = db.Column(db.String(16), nullable=False, server_default=db.text("'exact'"))
    sale_item_ref = db.Column(db.String(64), nullable=False, index=True)
    sale_item_name = db.Column(db.String(180), nullable=True)
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity_per_sale = db.Column(db.Numeric(12, 3), nullable=False, server_default=db.text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="recipes")
    inventory_item = db.relationship("InventoryItem", back_populates="recipes")


class StockLog(db.Model):
    __tablename__ = "stock_logs"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type = db.Column(db.String(20), nullable=False)  # addition|deduction|adjustment|waste
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    source_type = db.Column(db.String(30), nullable=True)  # sales_report|purchase|manual|waste
    source_ref = db.Column(db.String(120), nullable=True)
    note = db.Column(db.Text, nullable=True)
    before_stock = db.Column(db.Numeric(12, 3), nullable=True)
    after_stock = db.Column(db.Numeric(12, 3), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="stock_logs")
    inventory_item = db.relationship("InventoryItem", back_populates="stock_logs")
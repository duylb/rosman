from rosman_extensions import db


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku = db.Column(db.Text, nullable=False, index=True)
    name = db.Column(db.Text, nullable=False)
    quantity_on_hand = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    unit_cost = db.Column(db.Numeric(12, 2), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    organization = db.relationship("Organization", back_populates="inventory_items")
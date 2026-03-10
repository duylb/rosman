from __future__ import annotations

import os
from sqlalchemy import create_engine, inspect, text


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to run migrations.")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    dialect = engine.dialect.name.lower()

    with engine.begin() as conn:
        # Ensure required tables exist for new inventory domain.
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS suppliers (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL,
                    name VARCHAR(160) NOT NULL,
                    contact TEXT,
                    lead_time_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_logs (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL,
                    inventory_item_id INTEGER NOT NULL,
                    action_type VARCHAR(20) NOT NULL,
                    quantity NUMERIC(12,3) NOT NULL,
                    source_type VARCHAR(30),
                    source_ref VARCHAR(120),
                    note TEXT,
                    before_stock NUMERIC(12,3),
                    after_stock NUMERIC(12,3),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recipes (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL,
                    match_type VARCHAR(16) NOT NULL DEFAULT 'exact',
                    sale_item_ref VARCHAR(64) NOT NULL,
                    sale_item_name VARCHAR(180),
                    inventory_item_id INTEGER NOT NULL,
                    quantity_per_sale NUMERIC(12,3) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        # Required inventory_items columns requested by user.
        if dialect == "postgresql":
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS supplier_id INTEGER"))
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS unit VARCHAR(50)"))
            conn.execute(
                text("ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS minimum_stock_level FLOAT DEFAULT 0")
            )
            conn.execute(
                text("ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS current_stock FLOAT DEFAULT 0")
            )
            conn.execute(text("ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS unit_cost FLOAT DEFAULT 0"))

            # Helpful sales period columns.
            conn.execute(text("ALTER TABLE sale_reports ADD COLUMN IF NOT EXISTS start_date DATE"))
            conn.execute(text("ALTER TABLE sale_reports ADD COLUMN IF NOT EXISTS end_date DATE"))
        else:
            columns = {c["name"] for c in inspector.get_columns("inventory_items")}
            if "supplier_id" not in columns:
                conn.execute(text("ALTER TABLE inventory_items ADD COLUMN supplier_id INTEGER"))
            if "unit" not in columns:
                conn.execute(text("ALTER TABLE inventory_items ADD COLUMN unit VARCHAR(50)"))
            if "minimum_stock_level" not in columns:
                conn.execute(text("ALTER TABLE inventory_items ADD COLUMN minimum_stock_level FLOAT DEFAULT 0"))
            if "current_stock" not in columns:
                conn.execute(text("ALTER TABLE inventory_items ADD COLUMN current_stock FLOAT DEFAULT 0"))
            if "unit_cost" not in columns:
                conn.execute(text("ALTER TABLE inventory_items ADD COLUMN unit_cost FLOAT DEFAULT 0"))

            if inspector.has_table("sale_reports"):
                report_cols = {c["name"] for c in inspector.get_columns("sale_reports")}
                if "start_date" not in report_cols:
                    conn.execute(text("ALTER TABLE sale_reports ADD COLUMN start_date DATE"))
                if "end_date" not in report_cols:
                    conn.execute(text("ALTER TABLE sale_reports ADD COLUMN end_date DATE"))

    print("Database migration completed.")


if __name__ == "__main__":
    run()

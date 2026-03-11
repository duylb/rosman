from __future__ import annotations

import os
from sqlalchemy import create_engine, text


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to run migrations.")

    engine = create_engine(database_url)
    dialect = engine.dialect.name.lower()
    report_id_def = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
    item_id_def = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"

    with engine.begin() as conn:
        # 1) Drop all sales-related tables/data.
        for table_name in ["sales_items", "sales_reports", "product_sales", "sale_items", "sale_reports", "sales"]:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))

        # 2) Recreate n8n-ready sales schema from scratch.
        conn.execute(
            text(
                f"""
                CREATE TABLE sales_reports (
                    id {report_id_def},
                    organization_id INTEGER NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    created_datetime TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE sales_items (
                    id {item_id_def},
                    report_id INTEGER NOT NULL,
                    item_code VARCHAR(64) NOT NULL,
                    item_name VARCHAR(255) NOT NULL,
                    units_sold INTEGER NOT NULL DEFAULT 0,
                    revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
                    returned_quantity INTEGER NOT NULL DEFAULT 0,
                    returned_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
                    net_revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
                    category VARCHAR(120) NOT NULL DEFAULT 'Uncategorized',
                    type VARCHAR(120) NOT NULL DEFAULT 'Other',
                    FOREIGN KEY (report_id) REFERENCES sales_reports (id) ON DELETE CASCADE
                )
                """
            )
        )

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_organization_id ON sales_reports (organization_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_start_date ON sales_reports (start_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_end_date ON sales_reports (end_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_report_id ON sales_items (report_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_item_code ON sales_items (item_code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_category ON sales_items (category)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_type ON sales_items (type)"))

    print("Sales database reset and n8n-ready schema created.")


if __name__ == "__main__":
    run()

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
    report_id_def = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
    product_id_def = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"

    with engine.begin() as conn:
        # Ensure required tables exist for inventory + sales domains.
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

        # Canonical sales tables for n8n automation.
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS sales_reports (
                    id {report_id_def},
                    org_id INTEGER,
                    report_title VARCHAR(200),
                    start_date DATE,
                    end_date DATE,
                    branch VARCHAR(200),
                    created_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_products INTEGER DEFAULT 0,
                    total_units_sold INTEGER DEFAULT 0,
                    total_revenue FLOAT DEFAULT 0,
                    total_return_value FLOAT DEFAULT 0,
                    total_return_units INTEGER DEFAULT 0
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS product_sales (
                    id {product_id_def},
                    report_id INTEGER NOT NULL,
                    product_code VARCHAR(50),
                    product_name VARCHAR(200),
                    units_sold INTEGER DEFAULT 0,
                    revenue FLOAT DEFAULT 0,
                    return_units INTEGER DEFAULT 0,
                    return_value FLOAT DEFAULT 0,
                    net_revenue FLOAT DEFAULT 0,
                    category VARCHAR(120) DEFAULT 'Uncategorized',
                    type VARCHAR(120) DEFAULT 'Other'
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

            # Helpful compatibility columns.
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS org_id INTEGER"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS report_title VARCHAR(200)"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS start_date DATE"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS end_date DATE"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS branch VARCHAR(200)"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS created_datetime TIMESTAMP"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS total_products INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS total_units_sold INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS total_revenue FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS total_return_value FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN IF NOT EXISTS total_return_units INTEGER DEFAULT 0"))

            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS report_id INTEGER"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS product_code VARCHAR(50)"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS product_name VARCHAR(200)"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS units_sold INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS revenue FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS return_units INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS return_value FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS net_revenue FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS category VARCHAR(120) DEFAULT 'Uncategorized'"))
            conn.execute(text("ALTER TABLE product_sales ADD COLUMN IF NOT EXISTS type VARCHAR(120) DEFAULT 'Other'"))
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

            report_cols = {c["name"] for c in inspector.get_columns("sales_reports")}
            if "org_id" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN org_id INTEGER"))
            if "report_title" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN report_title VARCHAR(200)"))
            if "start_date" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN start_date DATE"))
            if "end_date" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN end_date DATE"))
            if "branch" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN branch VARCHAR(200)"))
            if "created_datetime" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN created_datetime TIMESTAMP"))
            if "total_products" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN total_products INTEGER DEFAULT 0"))
            if "total_units_sold" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN total_units_sold INTEGER DEFAULT 0"))
            if "total_revenue" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN total_revenue FLOAT DEFAULT 0"))
            if "total_return_value" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN total_return_value FLOAT DEFAULT 0"))
            if "total_return_units" not in report_cols:
                conn.execute(text("ALTER TABLE sales_reports ADD COLUMN total_return_units INTEGER DEFAULT 0"))

            product_cols = {c["name"] for c in inspector.get_columns("product_sales")}
            if "report_id" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN report_id INTEGER"))
            if "product_code" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN product_code VARCHAR(50)"))
            if "product_name" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN product_name VARCHAR(200)"))
            if "units_sold" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN units_sold INTEGER DEFAULT 0"))
            if "revenue" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN revenue FLOAT DEFAULT 0"))
            if "return_units" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN return_units INTEGER DEFAULT 0"))
            if "return_value" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN return_value FLOAT DEFAULT 0"))
            if "net_revenue" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN net_revenue FLOAT DEFAULT 0"))
            if "category" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN category VARCHAR(120) DEFAULT 'Uncategorized'"))
            if "type" not in product_cols:
                conn.execute(text("ALTER TABLE product_sales ADD COLUMN type VARCHAR(120) DEFAULT 'Other'"))

        if inspector.has_table("sale_reports"):
            conn.execute(
                text(
                    """
                    INSERT INTO sales_reports (
                        id, org_id, report_title, start_date, end_date, branch, created_datetime,
                        total_products, total_units_sold, total_revenue, total_return_value, total_return_units
                    )
                    SELECT
                        sr.id,
                        sr.org_id,
                        COALESCE(sr.filename, 'Sales Report'),
                        sr.start_date,
                        sr.end_date,
                        NULL,
                        COALESCE(sr.imported_at, CURRENT_TIMESTAMP),
                        CASE WHEN EXISTS (SELECT 1 FROM sale_items si WHERE si.sale_report_id = sr.id) THEN
                            (SELECT COUNT(1) FROM sale_items si WHERE si.sale_report_id = sr.id)
                        ELSE 0 END,
                        CASE WHEN EXISTS (SELECT 1 FROM sale_items si WHERE si.sale_report_id = sr.id) THEN
                            (SELECT COALESCE(SUM(si.quantity), 0) FROM sale_items si WHERE si.sale_report_id = sr.id)
                        ELSE 0 END,
                        COALESCE(sr.total_revenue, 0),
                        CASE WHEN EXISTS (SELECT 1 FROM sale_items si WHERE si.sale_report_id = sr.id) THEN
                            (SELECT COALESCE(SUM(si.return_value), 0) FROM sale_items si WHERE si.sale_report_id = sr.id)
                        ELSE 0 END,
                        CASE WHEN EXISTS (SELECT 1 FROM sale_items si WHERE si.sale_report_id = sr.id) THEN
                            (SELECT COALESCE(SUM(si.returns), 0) FROM sale_items si WHERE si.sale_report_id = sr.id)
                        ELSE 0 END
                    FROM sale_reports sr
                    WHERE NOT EXISTS (SELECT 1 FROM sales_reports ns WHERE ns.id = sr.id)
                    """
                )
            )

        if inspector.has_table("sale_items"):
            legacy_item_cols = {c["name"] for c in inspector.get_columns("sale_items")}
            report_ref_expr = "si.sale_report_id" if "sale_report_id" in legacy_item_cols else "si.report_id"
            product_code_expr = "si.sku" if "sku" in legacy_item_cols else "si.product_code"
            product_name_expr = "si.name" if "name" in legacy_item_cols else "si.product_name"
            units_expr = "COALESCE(si.quantity, 0)" if "quantity" in legacy_item_cols else "COALESCE(si.units_sold, 0)"
            revenue_expr = "COALESCE(si.revenue, 0)"
            return_units_expr = "COALESCE(si.returns, 0)" if "returns" in legacy_item_cols else "COALESCE(si.return_units, 0)"
            return_value_expr = "COALESCE(si.return_value, 0)"
            net_revenue_expr = (
                "COALESCE(si.net_revenue, COALESCE(si.revenue, 0) - COALESCE(si.return_value, 0))"
                if "net_revenue" in legacy_item_cols
                else f"({revenue_expr} - {return_value_expr})"
            )
            category_expr = "COALESCE(NULLIF(si.category, ''), 'Uncategorized')" if "category" in legacy_item_cols else "'Uncategorized'"
            type_expr = "COALESCE(NULLIF(si.type, ''), 'Other')" if "type" in legacy_item_cols else "'Other'"

            conn.execute(
                text(
                    f"""
                    INSERT INTO product_sales (
                        id, report_id, product_code, product_name, units_sold, revenue, return_units, return_value,
                        net_revenue, category, type
                    )
                    SELECT
                        si.id,
                        {report_ref_expr},
                        {product_code_expr},
                        {product_name_expr},
                        {units_expr},
                        {revenue_expr},
                        {return_units_expr},
                        {return_value_expr},
                        {net_revenue_expr},
                        {category_expr},
                        {type_expr}
                    FROM sale_items si
                    WHERE NOT EXISTS (SELECT 1 FROM product_sales ps WHERE ps.id = si.id)
                    """
                )
            )

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_org_id ON sales_reports (org_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_start_date ON sales_reports (start_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_end_date ON sales_reports (end_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_sales_report_id ON product_sales (report_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_sales_product_code ON product_sales (product_code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_sales_category ON product_sales (category)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_sales_type ON product_sales (type)"))

    print("Database migration completed.")


if __name__ == "__main__":
    run()

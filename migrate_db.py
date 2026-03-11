from __future__ import annotations

import os
from sqlalchemy import create_engine, inspect, text


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to run migrations.")

    engine = create_engine(database_url)
    dialect = engine.dialect.name.lower()
    report_id_def = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
    item_id_def = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"

    with engine.begin() as conn:
        inspector = inspect(conn)

        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS sales_reports (
                    id {report_id_def},
                    organization_id INTEGER NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    created_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS sales_items (
                    id {item_id_def},
                    report_id INTEGER NOT NULL,
                    item_code VARCHAR(64) NOT NULL,
                    item_name VARCHAR(255) NOT NULL,
                    revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
                    returned_quantity INTEGER NOT NULL DEFAULT 0,
                    returned_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
                    net_revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    category VARCHAR(120) NOT NULL DEFAULT 'Uncategorized',
                    type VARCHAR(120) NOT NULL DEFAULT 'Other',
                    FOREIGN KEY (report_id) REFERENCES sales_reports (id) ON DELETE CASCADE
                )
                """
            )
        )
        inspector = inspect(conn)

        sales_report_columns = {c["name"] for c in inspector.get_columns("sales_reports")}
        if "organization_id" not in sales_report_columns:
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN organization_id INTEGER"))
        if "start_date" not in sales_report_columns:
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN start_date DATE"))
        if "end_date" not in sales_report_columns:
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN end_date DATE"))
        if "created_datetime" not in sales_report_columns:
            conn.execute(text("ALTER TABLE sales_reports ADD COLUMN created_datetime TIMESTAMP"))

        if "org_id" in sales_report_columns:
            conn.execute(
                text(
                    """
                    UPDATE sales_reports
                    SET organization_id = COALESCE(organization_id, org_id)
                    WHERE organization_id IS NULL
                    """
                )
            )

        conn.execute(
            text(
                """
                UPDATE sales_reports
                SET created_datetime = COALESCE(created_datetime, CURRENT_TIMESTAMP)
                WHERE created_datetime IS NULL
                """
            )
        )

        if inspector.has_table("sale_reports"):
            legacy_report_columns = {c["name"] for c in inspector.get_columns("sale_reports")}
            org_expr = "sr.organization_id" if "organization_id" in legacy_report_columns else "sr.org_id"
            created_expr = (
                "COALESCE(sr.created_datetime, CURRENT_TIMESTAMP)"
                if "created_datetime" in legacy_report_columns
                else "COALESCE(sr.imported_at, CURRENT_TIMESTAMP)"
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO sales_reports (id, organization_id, start_date, end_date, created_datetime)
                    SELECT
                        sr.id,
                        {org_expr},
                        sr.start_date,
                        sr.end_date,
                        {created_expr}
                    FROM sale_reports sr
                    WHERE {org_expr} IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM sales_reports ns WHERE ns.id = sr.id)
                    """
                )
            )

        sales_item_columns = {c["name"] for c in inspector.get_columns("sales_items")}
        if "quantity" not in sales_item_columns:
            conn.execute(text("ALTER TABLE sales_items ADD COLUMN quantity INTEGER NOT NULL DEFAULT 0"))
        if "category" not in sales_item_columns:
            conn.execute(text("ALTER TABLE sales_items ADD COLUMN category VARCHAR(120) NOT NULL DEFAULT 'Uncategorized'"))
        if "type" not in sales_item_columns:
            conn.execute(text("ALTER TABLE sales_items ADD COLUMN type VARCHAR(120) NOT NULL DEFAULT 'Other'"))

        def migrate_items_from(table_name: str) -> None:
            if not inspector.has_table(table_name):
                return
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            report_ref_expr = "si.report_id" if "report_id" in cols else "si.sale_report_id"
            item_code_expr = "si.item_code" if "item_code" in cols else "si.product_code"
            if "item_code" not in cols and "product_code" not in cols and "sku" in cols:
                item_code_expr = "si.sku"
            item_name_expr = "si.item_name" if "item_name" in cols else "si.product_name"
            if "item_name" not in cols and "product_name" not in cols and "name" in cols:
                item_name_expr = "si.name"
            returned_qty_expr = "COALESCE(si.returned_quantity, 0)" if "returned_quantity" in cols else "COALESCE(si.return_units, 0)"
            if "returned_quantity" not in cols and "return_units" not in cols and "returns" in cols:
                returned_qty_expr = "COALESCE(si.returns, 0)"
            returned_amount_expr = "COALESCE(si.returned_amount, 0)" if "returned_amount" in cols else "COALESCE(si.return_value, 0)"
            net_expr = (
                "COALESCE(si.net_revenue, COALESCE(si.revenue, 0) - COALESCE(si.returned_amount, 0))"
                if "net_revenue" in cols and "returned_amount" in cols
                else "COALESCE(si.net_revenue, COALESCE(si.revenue, 0) - COALESCE(si.return_value, 0))"
            )
            quantity_expr = "COALESCE(si.quantity, 0)" if "quantity" in cols else "COALESCE(si.units_sold, 0)"
            if "quantity" not in cols and "units_sold" not in cols:
                quantity_expr = "0"
            category_expr = "COALESCE(si.category, 'Uncategorized')" if "category" in cols else "'Uncategorized'"
            type_expr = "COALESCE(si.type, 'Other')" if "type" in cols else "'Other'"
            conn.execute(
                text(
                    f"""
                    INSERT INTO sales_items (
                        id, report_id, item_code, item_name, revenue,
                        returned_quantity, returned_amount, net_revenue, quantity, category, type
                    )
                    SELECT
                        si.id,
                        {report_ref_expr},
                        {item_code_expr},
                        {item_name_expr},
                        COALESCE(si.revenue, 0),
                        {returned_qty_expr},
                        {returned_amount_expr},
                        {net_expr},
                        {quantity_expr},
                        {category_expr},
                        {type_expr}
                    FROM {table_name} si
                    WHERE {report_ref_expr} IS NOT NULL
                      AND {item_code_expr} IS NOT NULL
                      AND {item_name_expr} IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM sales_items ns WHERE ns.id = si.id)
                    """
                )
            )

        migrate_items_from("product_sales")
        migrate_items_from("sale_items")

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_organization_id ON sales_reports (organization_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_start_date ON sales_reports (start_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_reports_end_date ON sales_reports (end_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_report_id ON sales_items (report_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_item_code ON sales_items (item_code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_category ON sales_items (category)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_items_type ON sales_items (type)"))

        if dialect == "postgresql":
            for obsolete_column in [
                "org_id",
                "report_title",
                "branch",
                "total_products",
                "total_units_sold",
                "total_revenue",
                "total_return_value",
                "total_return_units",
            ]:
                conn.execute(text(f"ALTER TABLE sales_reports DROP COLUMN IF EXISTS {obsolete_column}"))

        # Required data cleanup of obsolete schema payload tables.
        if inspector.has_table("suppliers") and inspector.has_table("inventory_items"):
            conn.execute(text("UPDATE inventory_items SET supplier_id = NULL WHERE supplier_id IS NOT NULL"))
        for cleanup_table in ["sales", "inventory", "suppliers"]:
            if inspector.has_table(cleanup_table):
                conn.execute(text(f"DELETE FROM {cleanup_table}"))

        # Drop old sales architecture tables after migration.
        for old_table in ["product_sales", "sale_items", "sale_reports", "sales", "inventory"]:
            if inspector.has_table(old_table):
                conn.execute(text(f"DROP TABLE IF EXISTS {old_table}"))

    print("Database migration completed.")


if __name__ == "__main__":
    run()

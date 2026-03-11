from __future__ import annotations

import os
from sqlalchemy import create_engine, text


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to run migrations.")

    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                          AND tablename <> 'alembic_version'
                    LOOP
                        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
                    END LOOP;
                END
                $$;
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE organizations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX uq_organizations_name ON organizations (name);

                CREATE TABLE branches (
                    id SERIAL PRIMARY KEY,
                    organization_id INTEGER NOT NULL,
                    branch_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
                );
                CREATE INDEX ix_branches_organization_id ON branches (organization_id);

                CREATE TABLE products (
                    id SERIAL PRIMARY KEY,
                    item_code VARCHAR(50) UNIQUE NOT NULL,
                    item_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX ix_products_item_code ON products (item_code);

                CREATE TABLE sales_reports (
                    id SERIAL PRIMARY KEY,
                    organization_id INTEGER NOT NULL,
                    branch_id INTEGER NOT NULL,
                    report_title VARCHAR(255),
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    created_datetime TIMESTAMP,
                    total_products INTEGER,
                    total_units_sold INTEGER,
                    total_revenue NUMERIC(14,2),
                    total_return_units INTEGER,
                    total_return_value NUMERIC(14,2),
                    net_revenue NUMERIC(14,2),
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id),
                    FOREIGN KEY (branch_id) REFERENCES branches(id),
                    UNIQUE (branch_id, start_date, end_date)
                );
                CREATE INDEX ix_sales_reports_branch_id ON sales_reports (branch_id);
                CREATE INDEX ix_sales_reports_start_end ON sales_reports (start_date, end_date);

                CREATE TABLE sales_report_items (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    units_sold INTEGER,
                    revenue NUMERIC(14,2),
                    return_quantity INTEGER,
                    return_amount NUMERIC(14,2),
                    net_revenue NUMERIC(14,2),
                    FOREIGN KEY (report_id) REFERENCES sales_reports(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                CREATE INDEX ix_sales_report_items_report_id ON sales_report_items (report_id);
                CREATE INDEX ix_sales_report_items_product_id ON sales_report_items (product_id);
                """
            )
        )

    print("Schema reset completed: organizations, branches, products, sales_reports, sales_report_items")


if __name__ == "__main__":
    run()

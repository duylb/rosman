"""rebuild_sales_report_schema

Revision ID: 73e93d947cef
Revises:
Create Date: 2026-03-11 16:56:52.225799
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "73e93d947cef"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop every public table except alembic_version.
    op.execute(
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

    op.execute(
        """
        CREATE TABLE organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE UNIQUE INDEX uq_organizations_name ON organizations (name);")

    op.execute(
        """
        CREATE TABLE branches (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL,
            branch_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_branches_organization
                FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
        );
        """
    )
    op.execute("CREATE INDEX ix_branches_organization_id ON branches (organization_id);")

    op.execute(
        """
        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            item_code VARCHAR(50) UNIQUE NOT NULL,
            item_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX ix_products_item_code ON products (item_code);")

    op.execute(
        """
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
            CONSTRAINT fk_sales_reports_organization
                FOREIGN KEY (organization_id) REFERENCES organizations(id),
            CONSTRAINT fk_sales_reports_branch
                FOREIGN KEY (branch_id) REFERENCES branches(id),
            CONSTRAINT uq_sales_reports_branch_period
                UNIQUE (branch_id, start_date, end_date)
        );
        """
    )
    op.execute("CREATE INDEX ix_sales_reports_branch_id ON sales_reports (branch_id);")
    op.execute("CREATE INDEX ix_sales_reports_start_end ON sales_reports (start_date, end_date);")

    op.execute(
        """
        CREATE TABLE sales_report_items (
            id SERIAL PRIMARY KEY,
            report_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            units_sold INTEGER,
            revenue NUMERIC(14,2),
            return_quantity INTEGER,
            return_amount NUMERIC(14,2),
            net_revenue NUMERIC(14,2),
            CONSTRAINT fk_sales_report_items_report
                FOREIGN KEY (report_id) REFERENCES sales_reports(id) ON DELETE CASCADE,
            CONSTRAINT fk_sales_report_items_product
                FOREIGN KEY (product_id) REFERENCES products(id)
        );
        """
    )
    op.execute("CREATE INDEX ix_sales_report_items_report_id ON sales_report_items (report_id);")
    op.execute("CREATE INDEX ix_sales_report_items_product_id ON sales_report_items (product_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sales_report_items CASCADE;")
    op.execute("DROP TABLE IF EXISTS sales_reports CASCADE;")
    op.execute("DROP TABLE IF EXISTS products CASCADE;")
    op.execute("DROP TABLE IF EXISTS branches CASCADE;")
    op.execute("DROP TABLE IF EXISTS organizations CASCADE;")

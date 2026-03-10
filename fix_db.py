from __future__ import annotations

import os

import psycopg


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to run this fix.")

    statements = [
        "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS unit VARCHAR(50);",
        "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS supplier_id INTEGER;",
        "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS minimum_stock_level FLOAT DEFAULT 0;",
        "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS current_stock FLOAT DEFAULT 0;",
        "ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS unit_cost FLOAT DEFAULT 0;",
    ]

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()

    print("inventory_items schema fix applied successfully.")


if __name__ == "__main__":
    run()
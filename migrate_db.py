from __future__ import annotations

import os
import subprocess
import sys


def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to run migrations.")

    # Safety: this script no longer mutates schema directly.
    # Use Alembic/Flask-Migrate for all schema changes.
    command = [sys.executable, "-m", "flask", "db", "upgrade"]
    subprocess.run(command, check=True)
    print("Migration completed via 'flask db upgrade'.")


if __name__ == "__main__":
    run()

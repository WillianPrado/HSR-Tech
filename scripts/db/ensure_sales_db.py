from __future__ import annotations

from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "sales.db"


def ensure_sales_db(db_path: Path = DB_PATH) -> bool:
    """Ensure sales.db exists. Returns True when created, False when it already existed."""
    if db_path.exists():
        return False

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path):
        pass
    return True


if __name__ == "__main__":
    created = ensure_sales_db()
    if created:
        print(f"Created database: {DB_PATH}")
    else:
        print(f"Database already exists: {DB_PATH}")

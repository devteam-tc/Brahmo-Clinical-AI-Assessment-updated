"""Numbered database migration runner.
Ensures zero-downtime reproducible schema deployment.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.connection import get_connection

def run_migrations():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create migrations table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    
    cursor.execute("SELECT version FROM schema_migrations;")
    applied = set(row[0] for row in cursor.fetchall())
    
    migrations_dir = settings.db.migrations_dir
    sql_files = sorted(migrations_dir.glob("*.sql"))
    
    print(f"[*] Checking migrations in {migrations_dir}...")
    for sql_file in sql_files:
        version_str = sql_file.name.split("_")[0]
        try:
            version = int(version_str)
        except ValueError:
            continue
            
        if version not in applied:
            print(f"  -> Applying migration {sql_file.name} (v{version})...")
            with open(sql_file, "r", encoding="utf-8") as f:
                sql_content = f.read()
            cursor.executescript(sql_content)
            cursor.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?);",
                (version, sql_file.name)
            )
            conn.commit()
            print(f"     Applied successfully.")
        else:
            print(f"  [v] Migration {sql_file.name} already applied.")
            
    conn.close()
    print("[*] All migrations are up to date.")

if __name__ == "__main__":
    run_migrations()

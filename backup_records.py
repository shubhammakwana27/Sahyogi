"""Create a consistent SQLite backup without deleting or changing case records."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

ROOT = Path(__file__).resolve().parent


def backup_database(database, destination=None):
    source = Path(database).resolve()
    if not source.is_file():
        raise ValueError("No saved database was found. Start the app and save a case first.")
    target = Path(destination).resolve() if destination else ROOT / "backups" / (
        "sahyogi_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:6] + ".db")
    if source == target or target.exists():
        raise ValueError("Choose a new backup filename. Existing files will not be overwritten.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.getenv("SAHYOGI_DB", str(ROOT / "data" / "sahyogi.db")))
    parser.add_argument("--output", help="New destination filename; defaults to the backups folder")
    args = parser.parse_args()
    try:
        print("Backup saved to " + str(backup_database(args.database, args.output)))
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

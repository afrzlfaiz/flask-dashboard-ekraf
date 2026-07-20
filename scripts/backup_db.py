#!/usr/bin/env python3
"""
Backup database SQLite ke folder backups/ dengan timestamp.
Jalankan: python scripts/backup_db.py
Atau dari cron: 0 2 * * * cd /path/to/project && python scripts/backup_db.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.backup import create_backup  # noqa: E402


def backup():
    dest = create_backup("manual")
    print(f"✓ Backup berhasil: {dest} ({dest.stat().st_size:,} bytes)")


if __name__ == "__main__":
    backup()

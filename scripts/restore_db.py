#!/usr/bin/env python3
"""Restore a verified SQLite backup with a mandatory confirmation phrase."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.backup import restore_backup  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Pulihkan database dari BACKUP_DIR")
    parser.add_argument("backup_name", help="Nama file backup, bukan path bebas")
    parser.add_argument("--confirm", required=True, help="Harus bernilai RESTORE")
    args = parser.parse_args()
    safety = restore_backup(args.backup_name, confirm=args.confirm)
    print(f"✓ Restore selesai. Backup sebelum restore: {safety.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create, reset, disable, or list local application users."""

import argparse
import getpass
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from auth import ROLES  # noqa: E402
from utils.database import connect_db, initialize_database, transaction, utcnow  # noqa: E402


def require_password() -> str:
    password = getpass.getpass("Password baru: ")
    confirm = getpass.getpass("Ulangi password: ")
    if password != confirm or len(password) < 12:
        raise SystemExit("Password harus sama dan minimal 12 karakter.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("username")
    create.add_argument("--role", choices=ROLES, default="viewer")
    reset = sub.add_parser("reset-password")
    reset.add_argument("username")
    disable = sub.add_parser("disable")
    disable.add_argument("username")
    sub.add_parser("list")
    args = parser.parse_args()
    initialize_database()

    if args.command == "list":
        conn = connect_db()
        try:
            for row in conn.execute("SELECT username, role, is_active FROM users ORDER BY username"):
                print(f"{row['username']}\t{row['role']}\t{'aktif' if row['is_active'] else 'nonaktif'}")
        finally:
            conn.close()
        return

    with transaction() as conn:
        if args.command == "create":
            password = require_password()
            conn.execute(
                """INSERT INTO users
                   (username, password_hash, role, is_active, created_at, must_change_password)
                   VALUES (%s, %s, %s, 1, %s, 0)""",
                (args.username.strip(), generate_password_hash(password), args.role, utcnow()),
            )
        elif args.command == "reset-password":
            password = require_password()
            cursor = conn.execute(
                """UPDATE users SET password_hash = %s, is_active = 1,
                   must_change_password = 0, updated_at = %s WHERE username = %s""",
                (generate_password_hash(password), utcnow(), args.username),
            )
            if cursor.rowcount != 1:
                raise SystemExit("Pengguna tidak ditemukan.")
        elif args.command == "disable":
            cursor = conn.execute(
                "UPDATE users SET is_active = 0, updated_at = %s WHERE username = %s",
                (utcnow(), args.username),
            )
            if cursor.rowcount != 1:
                raise SystemExit("Pengguna tidak ditemukan.")
    print("✓ Perubahan pengguna berhasil.")


if __name__ == "__main__":
    main()

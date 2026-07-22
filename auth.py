"""Flask-Login integration, role enforcement, and secure user bootstrap."""

from __future__ import annotations

import logging
from functools import wraps

from flask import jsonify
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import BOOTSTRAP_ADMIN_PASSWORD, BOOTSTRAP_ADMIN_USERNAME
from utils.database import connect_db, initialize_database, transaction, utcnow

logger = logging.getLogger(__name__)
login_manager = LoginManager()
ROLES = ["operator", "admin"]


class User(UserMixin):
    def __init__(
        self,
        user_id: int,
        username: str,
        role: str,
        is_active: bool = True,
        must_change_password: bool = False,
    ):
        self.id = user_id
        self.username = username
        self.role = role
        self._active = is_active
        self.must_change_password = must_change_password

    @property
    def is_active(self):
        return self._active

    def has_role(self, required_role: str) -> bool:
        if required_role not in ROLES or self.role not in ROLES:
            return False
        return ROLES.index(self.role) >= ROLES.index(required_role)


@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    try:
        row = conn.execute(
            "SELECT id, username, role, is_active, must_change_password FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
    finally:
        conn.close()
    if row and row["is_active"]:
        return User(
            row["id"], row["username"], row["role"], bool(row["is_active"]),
            bool(row["must_change_password"]),
        )
    return None


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"success": False, "message": "Silakan login terlebih dahulu."}), 401


def role_required(role):
    """Require an authenticated user at or above the requested role."""
    def decorator(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"success": False, "message": "Silakan login terlebih dahulu."}), 401
            if not current_user.has_role(role):
                return jsonify({"success": False, "message": "Anda tidak memiliki izin untuk aksi ini."}), 403
            return func(*args, **kwargs)
        return decorated
    return decorator


def _validate_bootstrap_credentials() -> bool:
    if not BOOTSTRAP_ADMIN_USERNAME and not BOOTSTRAP_ADMIN_PASSWORD:
        return False
    if not BOOTSTRAP_ADMIN_USERNAME or len(BOOTSTRAP_ADMIN_PASSWORD) < 12:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_USERNAME dan BOOTSTRAP_ADMIN_PASSWORD minimal 12 karakter wajib diisi bersama."
        )
    return True


def init_users_table():
    """Upgrade auth schema, disable known defaults, and optionally bootstrap an admin."""
    initialize_database()
    with transaction() as conn:
        rows = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE is_active = 1"
        ).fetchall()
        for row in rows:
            if row["username"] == "admin" and check_password_hash(row["password_hash"], "admin123"):
                conn.execute(
                    "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
                    (utcnow(), row["id"]),
                )
                logger.critical(
                    "Akun admin dengan password default dinonaktifkan. Buat/reset admin melalui scripts/manage_users.py."
                )

        active_admin = conn.execute(
            "SELECT 1 FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1"
        ).fetchone()
        if not active_admin and _validate_bootstrap_credentials():
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (BOOTSTRAP_ADMIN_USERNAME,)
            ).fetchone()
            password_hash = generate_password_hash(BOOTSTRAP_ADMIN_PASSWORD)
            now = utcnow()
            if existing:
                conn.execute(
                    """UPDATE users SET password_hash = ?, role = 'admin', is_active = 1,
                       must_change_password = 0, updated_at = ? WHERE id = ?""",
                    (password_hash, now, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO users
                       (username, password_hash, role, is_active, created_at, must_change_password)
                       VALUES (?, ?, 'admin', 1, ?, 0)""",
                    (BOOTSTRAP_ADMIN_USERNAME, password_hash, now),
                )
            logger.warning("Admin bootstrap dibuat dari environment: %s", BOOTSTRAP_ADMIN_USERNAME)

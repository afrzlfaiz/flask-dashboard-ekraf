"""Authentication endpoints with session rotation, timeout, rate limit, and audit."""

from datetime import datetime, timedelta

from flask import g, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from api import api_bp
from auth import User
from utils.database import connection, record_audit, transaction, utcnow

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _is_rate_limited(username: str, ip_address: str) -> bool:
    cutoff = (datetime.now().astimezone() - timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
    with connection() as conn:
        count = conn.execute(
            """SELECT COUNT(*) AS total FROM login_attempts
               WHERE username = %s AND ip_address = %s AND succeeded = 0 AND attempted_at >= %s""",
            (username, ip_address, cutoff),
        ).fetchone()["total"]
        return count >= MAX_FAILED_ATTEMPTS


@api_bp.route("/auth/login", methods=["POST"])
def auth_login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    ip_address = _client_ip()

    if not username or not password:
        return jsonify({"success": False, "message": "Username dan password wajib diisi."}), 400
    if len(username) > 100 or len(password) > 512:
        return jsonify({"success": False, "message": "Kredensial tidak valid."}), 400
    if _is_rate_limited(username, ip_address):
        return jsonify({
            "success": False,
            "message": f"Terlalu banyak percobaan. Coba kembali dalam {LOCKOUT_MINUTES} menit.",
        }), 429

    with transaction() as conn:
        row = conn.execute(
            """SELECT id, username, password_hash, role, is_active, must_change_password
               FROM users WHERE username = %s""",
            (username,),
        ).fetchone()
        valid = bool(
            row and row["is_active"] and check_password_hash(row["password_hash"], password)
        )
        conn.execute(
            "INSERT INTO login_attempts (username, ip_address, succeeded, attempted_at) VALUES (%s, %s, %s, %s)",
            (username, ip_address, int(valid), utcnow()),
        )
        conn.execute(
            "DELETE FROM login_attempts WHERE attempted_at < %s",
            ((datetime.now().astimezone() - timedelta(days=1)).isoformat(timespec="seconds"),),
        )

        if not valid:
            record_audit(
                conn, action="login_failed", entity="auth", new_value={"username": username},
                ip_address=ip_address, request_id=getattr(g, "request_id", None),
            )
            return jsonify({"success": False, "message": "Username atau password salah."}), 401

        conn.execute("UPDATE users SET last_login_at = %s, updated_at = %s WHERE id = %s", (utcnow(), utcnow(), row["id"]))
        record_audit(
            conn, action="login", entity="auth", entity_id=row["id"], user_id=row["id"],
            ip_address=ip_address, request_id=getattr(g, "request_id", None),
        )

    session.clear()
    session.permanent = True
    user = User(
        row["id"], row["username"], row["role"], bool(row["is_active"]),
        bool(row["must_change_password"]),
    )
    login_user(user, remember=False, fresh=True)
    return jsonify({
        "success": True,
        "message": "Login berhasil.",
        "user": {
            "id": user.id, "username": user.username, "role": user.role,
            "must_change_password": user.must_change_password,
        },
    })


@api_bp.route("/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    user_id = current_user.id
    with transaction() as conn:
        record_audit(
            conn, action="logout", entity="auth", entity_id=user_id, user_id=user_id,
            ip_address=_client_ip(), request_id=getattr(g, "request_id", None),
        )
    logout_user()
    session.clear()
    return jsonify({"success": True, "message": "Logout berhasil."})


@api_bp.route("/auth/status")
def auth_status():
    if current_user.is_authenticated:
        return jsonify({
            "success": True,
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "role": current_user.role,
                "must_change_password": current_user.must_change_password,
            },
        })
    return jsonify({"success": True, "authenticated": False, "user": None})


# ── User management (admin only) ─────────────────────────────
@api_bp.route("/auth/users", methods=["GET"])
def list_users():
    """Daftar semua user — admin only."""
    from auth import role_required
    wrapped = role_required("admin")(lambda: None)
    result = wrapped()
    if result is not None:
        return result
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, username, role, is_active, created_at, last_login_at FROM users WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        return jsonify({"success": True, "users": [dict(r) for r in rows]})


@api_bp.route("/auth/users", methods=["POST"])
def create_user():
    """Buat user operator baru — admin only."""
    from auth import role_required
    wrapped = role_required("admin")(lambda: None)
    result = wrapped()
    if result is not None:
        return result

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or len(username) < 3 or len(username) > 64:
        return jsonify({"success": False, "message": "Username harus 3–64 karakter."}), 400
    if len(password) < 8:
        return jsonify({"success": False, "message": "Password minimal 8 karakter."}), 400

    with transaction() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE username = %s", (username,)).fetchone()
        if exists:
            return jsonify({"success": False, "message": "Username sudah digunakan."}), 409

        password_hash = generate_password_hash(password)
        now = utcnow()
        conn.execute(
            """INSERT INTO users (username, password_hash, role, is_active, created_at, must_change_password)
               VALUES (%s, %s, 'operator', 1, %s, 0)""",
            (username, password_hash, now),
        )
        record_audit(
            conn, action="user_created", entity="users", new_value={"username": username},
            user_id=current_user.id, ip_address=_client_ip(),
            request_id=getattr(g, "request_id", None),
        )

    return jsonify({"success": True, "message": f"User {username} berhasil dibuat."}), 201


@api_bp.route("/auth/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Hapus user — admin only, tidak bisa hapus diri sendiri."""
    from auth import role_required
    wrapped = role_required("admin")(lambda: None)
    result = wrapped()
    if result is not None:
        return result

    if user_id == current_user.id:
        return jsonify({"success": False, "message": "Tidak bisa menghapus akun sendiri."}), 400

    with transaction() as conn:
        row = conn.execute(
            "SELECT id, username, role, is_active FROM users WHERE id = %s", (user_id,)
        ).fetchone()
        if not row or not row["is_active"]:
            return jsonify({"success": False, "message": "User tidak ditemukan."}), 404
        if row["role"] != "operator":
            return jsonify({"success": False, "message": "Hanya user operator yang dapat dihapus."}), 400

        conn.execute(
            "UPDATE users SET is_active = 0, updated_at = %s WHERE id = %s", (utcnow(), user_id)
        )
        record_audit(
            conn, action="user_deleted", entity="users", entity_id=user_id,
            new_value={"username": row["username"]},
            user_id=current_user.id, ip_address=_client_ip(),
            request_id=getattr(g, "request_id", None),
        )

    return jsonify({"success": True, "message": f"User {row['username']} dihapus."})

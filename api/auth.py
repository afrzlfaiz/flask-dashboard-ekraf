"""Authentication endpoints with session rotation, timeout, rate limit, and audit."""

from datetime import datetime, timedelta

from flask import g, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from api import api_bp
from auth import User
from utils.database import connect_db, record_audit, transaction, utcnow

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _is_rate_limited(username: str, ip_address: str) -> bool:
    cutoff = (datetime.now().astimezone() - timedelta(minutes=LOCKOUT_MINUTES)).isoformat(timespec="seconds")
    conn = connect_db()
    try:
        count = conn.execute(
            """SELECT COUNT(*) FROM login_attempts
               WHERE username = ? AND ip_address = ? AND succeeded = 0 AND attempted_at >= ?""",
            (username, ip_address, cutoff),
        ).fetchone()[0]
        return count >= MAX_FAILED_ATTEMPTS
    finally:
        conn.close()


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
               FROM users WHERE username = ?""",
            (username,),
        ).fetchone()
        valid = bool(
            row and row["is_active"] and check_password_hash(row["password_hash"], password)
        )
        conn.execute(
            "INSERT INTO login_attempts (username, ip_address, succeeded, attempted_at) VALUES (?, ?, ?, ?)",
            (username, ip_address, int(valid), utcnow()),
        )
        conn.execute(
            "DELETE FROM login_attempts WHERE attempted_at < ?",
            ((datetime.now().astimezone() - timedelta(days=1)).isoformat(timespec="seconds"),),
        )

        if not valid:
            record_audit(
                conn, action="login_failed", entity="auth", new_value={"username": username},
                ip_address=ip_address, request_id=getattr(g, "request_id", None),
            )
            return jsonify({"success": False, "message": "Username atau password salah."}), 401

        conn.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?", (utcnow(), utcnow(), row["id"]))
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

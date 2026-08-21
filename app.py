"""Application factory for the Dashboard Spasial Ekonomi Kreatif Kota Malang."""

import logging
import re
import uuid
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS
from flask_login import current_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from flask_compress import Compress
from werkzeug.middleware.proxy_fix import ProxyFix

from api import api_bp
from auth import init_users_table, login_manager
from config import (
    ALLOWED_ORIGINS,
    CORS_SUPPORTS_CREDENTIALS,
    DEBUG,
    FLASK_ENV,
    HOST,
    LOG_DIR,
    MAX_UPLOAD_SIZE_MB,
    PORT,
    SECRET_KEY,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_TIMEOUT_MINUTES,
)

csrf = CSRFProtect()
compress = Compress()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=SECRET_KEY,
        MAX_CONTENT_LENGTH=MAX_UPLOAD_SIZE_MB * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
        SESSION_COOKIE_SAMESITE=SESSION_COOKIE_SAMESITE,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_TIMEOUT_MINUTES),
        SESSION_REFRESH_EACH_REQUEST=True,
        SEND_FILE_MAX_AGE_DEFAULT=timedelta(days=7) if FLASK_ENV == "production" else 0,
    )
    if test_config:
        app.config.update(test_config)

    if not app.config.get("TESTING"):
        if FLASK_ENV == "production":
            handler = logging.StreamHandler()
        else:
            Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                str(Path(LOG_DIR) / "app.log"), maxBytes=2_000_000, backupCount=10
            )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        ))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    if FLASK_ENV == "production":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]
    if origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": origins}},
            supports_credentials=CORS_SUPPORTS_CREDENTIALS,
        )

    @app.before_request
    def assign_request_id():
        supplied = request.headers.get("X-Request-ID", "")
        g.request_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied) else str(uuid.uuid4())[:12]

    csrf.init_app(app)
    compress.init_app(app)
    login_manager.init_app(app)

    init_users_table()
    app.register_blueprint(api_bp)

    @app.after_request
    def secure_response(response):
        reference = getattr(g, "request_id", None) or str(uuid.uuid4())[:12]
        if response.status_code >= 400 and response.is_json:
            payload = response.get_json(silent=True)
            if isinstance(payload, dict):
                payload.setdefault("success", False)
                payload.setdefault("code", reference)
                response.set_data(app.json.dumps(payload))
        response.headers["X-Request-ID"] = reference
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
        if FLASK_ENV == "production" and request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/survei")
    def survey_page():
        if not current_user.is_authenticated:
            return redirect(url_for("admin_login_page", redirect="/survei"))
        if not current_user.has_role("admin"):
            return redirect(url_for("dashboard"))
        return render_template("survey.html")

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/admin")
    def admin_login_page():
        return render_template("login.html")

    @app.route("/login")
    def login_page():
        return redirect(url_for("admin_login_page"))

    def dashboard_page(page):
        if page == "kelola" and not (current_user.is_authenticated and current_user.has_role("operator")):
            return error_response(403, "Anda tidak memiliki izin membuka halaman kelola data.")
        return render_template("dashboard.html", page=page)

    for page in ["peta", "clustering", "statistik", "tabel", "kelola", "tentang"]:
        app.add_url_rule(f"/{page}", f"page_{page}", dashboard_page, defaults={"page": page})

    def error_response(status, message, *, code=None):
        reference = code or getattr(g, "request_id", str(uuid.uuid4())[:12])
        return jsonify({"success": False, "message": message, "code": reference}), status

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        app.logger.warning("CSRF ditolak [%s]: %s", getattr(g, "request_id", "-"), error.description)
        return error_response(400, "Token keamanan tidak valid. Muat ulang halaman dan coba kembali.")

    @app.errorhandler(400)
    def bad_request(error):
        return error_response(400, "Permintaan tidak valid.")

    @app.errorhandler(401)
    def unauthorized(error):
        return error_response(401, "Silakan login terlebih dahulu.")

    @app.errorhandler(403)
    def forbidden(error):
        return error_response(403, "Anda tidak memiliki izin.")

    @app.errorhandler(404)
    def not_found(error):
        return error_response(404, "Halaman tidak ditemukan.")

    @app.errorhandler(413)
    def too_large(error):
        return error_response(413, f"Ukuran file terlalu besar. Maksimum {MAX_UPLOAD_SIZE_MB} MB.")

    @app.errorhandler(429)
    def too_many_requests(error):
        return error_response(429, "Terlalu banyak permintaan. Silakan coba kembali nanti.")

    @app.errorhandler(500)
    def server_error(error):
        reference = getattr(g, "request_id", str(uuid.uuid4())[:12])
        app.logger.exception("Internal error [%s]", reference, exc_info=error)
        return error_response(
            500, "Terjadi kesalahan internal. Silakan hubungi administrator.", code=reference
        )

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host=HOST, port=PORT, debug=DEBUG)

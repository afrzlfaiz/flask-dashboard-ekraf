/**
 * auth.js — Auth state manager, session tracking, 401 interceptor.
 * Dipanggil pertama sebelum komponen lain.
 */
const Auth = {
    _user: null,
    _checked: false,

    // ── Check session on load ──────────────────────────
    async check() {
        try {
            const resp = await fetch("/api/auth/status");
            const data = await resp.json();
            if (data.authenticated) {
                this._user = data.user;
            }
        } catch (e) {
            this._user = null;
        }
        this._checked = true;
        this.updateUI();
    },

    // ── State queries ───────────────────────────────────
    isAuthenticated() {
        return this._user !== null;
    },
    user() {
        return this._user;
    },
    hasRole(role) {
        if (!this._user) return false;
        const ROLES = ["operator", "admin"];
        if (!ROLES.includes(role) || !ROLES.includes(this._user.role)) return false;
        return ROLES.indexOf(this._user.role) >= ROLES.indexOf(role);
    },

    // ── Redirect to login if not authenticated ──────────
    require(role) {
        if (!this.isAuthenticated()) {
            window.location.href = "/admin?redirect=" + encodeURIComponent(window.location.pathname);
            return false;
        }
        if (role && !this.hasRole(role)) {
            App.showToast("Akses Ditolak", "Anda tidak memiliki izin untuk aksi ini.");
            return false;
        }
        return true;
    },

    // ── Update sidebar UI ───────────────────────────────
    updateUI() {
        const area = document.getElementById("auth-area");
        if (!area) return;

        if (this.isAuthenticated()) {
            const roleBadge = {
                admin: '<span class="badge bg-danger">Admin</span>',
                operator: '<span class="badge bg-info text-dark">Operator</span>',
            }[this._user.role] || "";

            const safeUsername = String(this._user.username)
                .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
            area.innerHTML = `
                <div class="auth-user-info">
                    <div class="d-flex align-items-center gap-2 mb-2">
                        <i class="bi bi-person-circle fs-5"></i>
                        <div>
                            <div class="fw-semibold" style="font-size: 0.85rem;">${safeUsername}</div>
                            <div style="font-size: 0.7rem;">${roleBadge}</div>
                        </div>
                    </div>
                    <button class="btn btn-outline-light btn-sm w-100" onclick="Auth.logout()">
                        <i class="bi bi-box-arrow-right me-1"></i> Logout
                    </button>
                </div>`;
        } else {
            // ponytail: publik tidak perlu login — tombol login tidak ditampilkan.
            area.innerHTML = "";
        }

        // Show/hide admin-only elements
        document.querySelectorAll(".auth-admin-only").forEach(el => {
            el.style.display = this.hasRole("admin") ? "" : "none";
        });
        document.querySelectorAll(".auth-operator-only").forEach(el => {
            el.style.display = this.hasRole("operator") ? "" : "none";
        });
        document.querySelectorAll(".auth-logged-in").forEach(el => {
            el.style.display = this.isAuthenticated() ? "" : "none";
        });
        document.querySelectorAll(".auth-logged-out").forEach(el => {
            el.style.display = this.isAuthenticated() ? "none" : "";
        });
    },

    // ── Login / Logout ──────────────────────────────────
    async login(username, password) {
        const resp = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        return await resp.json();
    },

    async logout() {
        await fetch("/api/auth/logout", { method: "POST" });
        this._user = null;
        this.updateUI();
        window.location.href = "/";
    },
};

// ── Global fetch interceptor — redirect on 401 ──────────
const _originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
    const requestUrl = new URL(url, window.location.origin);
    const method = String(options.method || "GET").toUpperCase();
    if (requestUrl.origin === window.location.origin && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        const headers = new Headers(options.headers || {});
        const token = document.querySelector('meta[name="csrf-token"]')?.content;
        if (token) headers.set("X-CSRFToken", token);
        options = { ...options, headers };
    }
    const resp = await _originalFetch(url, options);
    // If any API call returns 401 and we thought we were logged in, redirect
    if (resp.status === 401 && Auth._checked && Auth.isAuthenticated()) {
        Auth._user = null;
        Auth.updateUI();
        window.location.href = "/admin?expired=1";
    }
    // For non-auth users hitting 401 on mutation endpoints, redirect to login
    if (resp.status === 401 && !Auth.isAuthenticated() &&
        ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        const action = requestUrl.pathname;
        if (action.startsWith("/api/crud") || action === "/api/upload") {
            window.location.href = "/admin?redirect=" + encodeURIComponent(window.location.pathname);
        }
    }
    return resp;
};

// ── Boot on page load ────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => Auth.check());

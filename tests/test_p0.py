"""Regression tests for the P0 security and data-safety controls."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path


_TEMP_ROOT = tempfile.TemporaryDirectory(prefix="dashboard-p0-tests-")
TEST_ROOT = Path(_TEMP_ROOT.name)
os.environ.update({
    "FLASK_ENV": "development",
    "FLASK_DEBUG": "false",
    "SECRET_KEY": "p0-test-secret-key-with-at-least-32-characters",
    "DATABASE_URL": str(TEST_ROOT / "ekraf.db"),
    "BACKUP_DIR": str(TEST_ROOT / "backups"),
    "LOG_DIR": str(TEST_ROOT / "logs"),
    "AUTO_BACKUP_ENABLED": "false",
    "ALLOWED_ORIGINS": "http://localhost",
})

import pandas as pd  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from config import BACKUP_DIR  # noqa: E402
from utils.backup import create_backup, restore_backup  # noqa: E402
from utils.database import connect_db, transaction, utcnow  # noqa: E402


PASSWORD = "StrongPassword!123"


class P0SecurityTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "AUTO_BACKUP_ENABLED": False,
        })
        with transaction() as conn:
            for table in (
                "import_staging", "import_batches", "audit_logs", "login_attempts",
                "pelaku_ekraf", "users",
            ):
                conn.execute(f'DELETE FROM "{table}"')
            conn.execute(
                '''INSERT INTO pelaku_ekraf
                   ("Nama Narasumber", "Nama Usaha", "Alamat", "Kecamatan", "Kelurahan",
                    "No Telp", "Sub Sektor", "Tahun Berdiri", "Email", lat, lon,
                    "Sheet", created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    "Nama Rahasia", "Usaha Rahasia", "Alamat Rahasia", "Klojen", "Klojen",
                    "081234567890", "8) Kuliner", 2020, "rahasia@example.test",
                    -7.981234, 112.631234, "Klojen", utcnow(),
                ),
            )
            for username, role in (
                ("operator1", "operator"),
                ("admin1", "admin"),
            ):
                conn.execute(
                    '''INSERT INTO users
                       (username, password_hash, role, is_active, created_at, must_change_password)
                       VALUES (?, ?, ?, 1, ?, 0)''',
                    (username, generate_password_hash(PASSWORD), role, utcnow()),
                )
        self.client = self.app.test_client()

    def login(self, username: str):
        response = self.client.post(
            "/api/auth/login", json={"username": username, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response

    @staticmethod
    def actor_payload(name: str = "Usaha Operator") -> dict:
        return {
            "nama_narasumber": "Operator Test",
            "nama_usaha": name,
            "alamat": "Jalan Test",
            "kecamatan": "Klojen",
            "kelurahan": "Klojen",
            "no_hp": "081111111111",
            "subsektor": "8) Kuliner",
            "tahun_berdiri": 2022,
            "email": "operator@example.test",
            "latitude": -7.982,
            "longitude": 112.632,
        }

    def test_public_privacy_protected_routes_and_cors(self):
        response = self.client.get("/api/map", headers={"Origin": "http://localhost"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost")
        marker = response.get_json()["markers"][0]
        # ponytail: publik dapat marker individu (nama & alamat terlihat),
        # tapi NO telepon/email (PII dilindungi).
        self.assertIn("nama_narasumber", marker)
        self.assertIn("alamat", marker)
        self.assertNotIn("no_hp", marker)
        self.assertNotIn("email", marker)
        serialized = response.get_data(as_text=True)
        self.assertNotIn("081234567890", serialized)
        self.assertNotIn("rahasia@example.test", serialized)

        denied_cors = self.client.get("/api/map", headers={"Origin": "https://evil.test"})
        self.assertNotIn("Access-Control-Allow-Origin", denied_cors.headers)
        # /api/table now public — returns data without PII
        public_table = self.client.get("/api/table")
        self.assertEqual(public_table.status_code, 200)
        # Protected endpoint returns 401 with code matching X-Request-ID
        crud_denied = self.client.post("/api/crud", json={})
        self.assertEqual(crud_denied.status_code, 401)
        self.assertEqual(crud_denied.get_json()["code"], crud_denied.headers["X-Request-ID"])
        self.assertNotIn("data", self.client.post("/api/filter", json={}).get_json())

    def test_table_server_side_pagination_filter_search_and_sort(self):
        with transaction() as conn:
            for number in range(1, 25):
                kecamatan = "Sukun" if number % 2 == 0 else "Klojen"
                conn.execute(
                    '''INSERT INTO pelaku_ekraf
                       ("Nama Narasumber", "Nama Usaha", "Alamat", "Kecamatan", "Kelurahan",
                        "No Telp", "Sub Sektor", "Tahun Berdiri", "Email", lat, lon,
                        "Sheet", created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        f"Narasumber {number:02d}", f"Usaha {number:02d}",
                        f"Jalan {number}", kecamatan, kecamatan,
                        f"08120000{number:04d}", "8) Kuliner", 2000 + number,
                        f"usaha{number:02d}@example.test", -7.98, 112.63,
                        kecamatan, utcnow(),
                    ),
                )

        # ponytail: tabel publik tanpa login — PII disembunyikan.
        first = self.client.get("/api/table?page=1&per_page=10&draw=7").get_json()
        second = self.client.get("/api/table?page=2&per_page=10").get_json()

        self.assertEqual(first["draw"], 7)
        self.assertEqual((first["recordsTotal"], first["recordsFiltered"]), (25, 25))
        self.assertEqual(len(first["data"]), 10)
        self.assertEqual([row["no"] for row in first["data"]], list(range(1, 11)))
        self.assertEqual([row["no"] for row in second["data"]], list(range(11, 21)))
        self.assertTrue(
            {row["id"] for row in first["data"]}.isdisjoint(
                {row["id"] for row in second["data"]}
            )
        )

        last = self.client.get("/api/table?page=3&per_page=10").get_json()
        empty = self.client.get("/api/table?page=4&per_page=10").get_json()
        self.assertEqual([row["no"] for row in last["data"]], list(range(21, 26)))
        self.assertEqual(empty["data"], [])

        for requested_size in (10, 25, 50, 100):
            sized = self.client.get(
                "/api/table", query_string={"per_page": requested_size}
            ).get_json()
            self.assertEqual(sized["per_page"], requested_size)
            self.assertEqual(len(sized["data"]), min(requested_size, 25))

        bounded = self.client.get("/api/table?page=1&per_page=1000").get_json()
        self.assertEqual(bounded["per_page"], 100)
        self.assertEqual(len(bounded["data"]), 25)

        filtered = self.client.get(
            "/api/table", query_string={"kecamatan": "Sukun", "per_page": 100}
        ).get_json()
        self.assertEqual(filtered["recordsTotal"], 25)
        self.assertEqual(filtered["recordsFiltered"], 12)
        self.assertTrue(all(row["kecamatan"] == "Sukun" for row in filtered["data"]))

        dashboard_search = self.client.get(
            "/api/table", query_string={"search": "Narasumber 07"}
        ).get_json()
        self.assertEqual(dashboard_search["recordsFiltered"], 1)
        self.assertEqual(dashboard_search["data"][0]["nama_narasumber"], "Narasumber 07")

        quick_search = self.client.get(
            "/api/table", query_string={"quick_search": "usaha23@example.test"}
        ).get_json()
        self.assertEqual(quick_search["recordsFiltered"], 1)
        self.assertEqual(quick_search["data"][0]["nama_narasumber"], "Narasumber 23")
        # ponytail: publik must NOT see phone/email; quick_search by email works but doesn't expose it.
        self.assertNotIn("email", quick_search["data"][0])
        self.assertNotIn("no_hp", quick_search["data"][0])

        no_matches = self.client.get(
            "/api/table", query_string={"quick_search": "tidak-ada-hasil"}
        ).get_json()
        self.assertEqual(no_matches["recordsFiltered"], 0)
        self.assertEqual(no_matches["data"], [])

        latest = self.client.get(
            "/api/table?page=1&per_page=5&sort=id&direction=desc"
        ).get_json()["data"]
        self.assertEqual(len(latest), 5)
        self.assertEqual(
            [row["id"] for row in latest],
            sorted((row["id"] for row in latest), reverse=True),
        )

        sorted_names = self.client.get(
            "/api/table?page=1&per_page=10&sort=nama_usaha&direction=desc"
        ).get_json()["data"]
        self.assertEqual(
            [row["nama_usaha"] for row in sorted_names],
            sorted((row["nama_usaha"] for row in sorted_names), reverse=True),
        )

        safe_fallback = self.client.get(
            "/api/table?sort=id%20DESC%3B%20DROP%20TABLE%20users&direction=invalid"
        ).get_json()["data"]
        self.assertEqual(
            [row["id"] for row in safe_fallback],
            sorted(row["id"] for row in safe_fallback),
        )

        # Export requires operator role (contains PII: phone, email).
        self.login("operator1")
        exported = self.client.get("/api/export?format=csv&page=1&per_page=1")
        self.assertEqual(exported.status_code, 200)
        exported_text = exported.get_data(as_text=True)
        self.assertIn("Usaha 01", exported_text)
        self.assertIn("Usaha 24", exported_text)

    def test_rbac_validation_soft_delete_restore_and_purge(self):
        self.login("operator1")
        invalid = self.client.post("/api/crud", json={"nama_usaha": "Tidak Lengkap"})
        self.assertEqual(invalid.status_code, 422)
        created = self.client.post("/api/crud", json=self.actor_payload())
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        actor_id = created.get_json()["id"]
        updated = self.actor_payload("Usaha Diperbarui")
        self.assertEqual(self.client.put(f"/api/crud/{actor_id}", json=updated).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/crud/{actor_id}").status_code, 403)
        self.client.post("/api/auth/logout")

        self.login("admin1")
        self.assertEqual(self.client.delete(f"/api/crud/{actor_id}").status_code, 200)
        active_ids = {row["id"] for row in self.client.get("/api/crud").get_json()["data"]}
        self.assertNotIn(actor_id, active_ids)
        self.assertEqual(self.client.post(f"/api/crud/{actor_id}/restore").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/crud/{actor_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/crud/{actor_id}/purge", json={}).status_code, 400)
        self.assertEqual(
            self.client.delete(f"/api/crud/{actor_id}/purge", json={"confirm": "PURGE"}).status_code,
            200,
        )
        with closing(connect_db()) as conn:
            actions = {row[0] for row in conn.execute("SELECT action FROM audit_logs")}
        self.assertTrue({"create", "update", "soft_delete", "restore", "purge"} <= actions)

    def test_staged_import_preview_commit_error_report_and_rollback(self):
        self.login("operator1")
        fake = self.client.post(
            "/api/upload",
            data={"file": (
                BytesIO(b"PK\x03\x04not-a-real-workbook"),
                "fake.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )},
            content_type="multipart/form-data",
        )
        self.assertEqual(fake.status_code, 400)

        rows = [
            {
                "Nama Narasumber": "Import Test", "Nama Usaha": "Usaha Import",
                "Alamat": "Jalan Import", "Kecamatan": "Klojen", "Kelurahan": "Klojen",
                "No Telp": "082222222222", "Sub Sektor": "8) Kuliner",
                "Kategori Usaha": "UMKM", "Tahun Berdiri": 2021,
                "Email": "import@example.test", "lat": -7.982, "lon": 112.632,
            },
            {
                "Nama Narasumber": "Import Duplikat", "Nama Usaha": "Usaha Import",
                "Alamat": "Jalan Import 2", "Kecamatan": "Klojen", "Kelurahan": "Klojen",
                "No Telp": "082222222222", "Sub Sektor": "8) Kuliner",
                "Kategori Usaha": "UMKM", "Tahun Berdiri": 2021,
                "Email": "duplikat@example.test", "lat": -7.983, "lon": 112.633,
            },
            {
                "Nama Narasumber": "Import Salah", "Nama Usaha": "Usaha Salah",
                "Alamat": "Jalan Salah", "Kecamatan": "Di Luar Malang", "Kelurahan": "X",
                "No Telp": "abc", "Sub Sektor": "Tidak Ada", "Kategori Usaha": "UMKM",
                "Tahun Berdiri": "lama", "Email": "bukan-email", "lat": "salah", "lon": 0,
            },
        ]
        payload = BytesIO()
        with pd.ExcelWriter(payload, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, index=False)
        payload.seek(0)
        preview = self.client.post(
            "/api/upload",
            data={"file": (
                payload,
                "import.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )},
            content_type="multipart/form-data",
        )
        self.assertEqual(preview.status_code, 201, preview.get_data(as_text=True))
        batch = preview.get_json()["batch"]
        self.assertEqual((batch["valid"], batch["errors"], batch["duplicates"]), (1, 1, 1))
        report = self.client.get(f'/api/upload/{batch["id"]}/errors')
        self.assertEqual(report.status_code, 200)
        self.assertIn("duplikat", report.get_data(as_text=True).lower())
        committed = self.client.post(f'/api/upload/{batch["id"]}/commit')
        self.assertEqual(committed.status_code, 200, committed.get_data(as_text=True))
        self.assertEqual(committed.get_json()["inserted"], 1)
        self.assertTrue(list(Path(BACKUP_DIR).glob("*pre-import*.db")))
        self.client.post("/api/auth/logout")

        self.login("admin1")
        rolled_back = self.client.post(f'/api/upload/{batch["id"]}/rollback')
        self.assertEqual(rolled_back.status_code, 200)
        with closing(connect_db()) as conn:
            active = conn.execute(
                "SELECT COUNT(*) FROM pelaku_ekraf WHERE import_batch_id = ? AND is_active = 1",
                (batch["id"],),
            ).fetchone()[0]
        self.assertEqual(active, 0)

    def test_login_rate_limit_and_secure_session_cookie(self):
        for _ in range(5):
            response = self.client.post(
                "/api/auth/login", json={"username": "unknown", "password": "wrong"}
            )
            self.assertEqual(response.status_code, 401)
        limited = self.client.post(
            "/api/auth/login", json={"username": "unknown", "password": "wrong"}
        )
        self.assertEqual(limited.status_code, 429)

        self.app.config["SESSION_COOKIE_SECURE"] = True
        response = self.login("operator1")
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

        with transaction() as conn:
            conn.execute("UPDATE users SET is_active = 0 WHERE username = 'operator1'")
        # User tidak aktif → endpoint terproteksi return 401 (bukan publik)
        self.assertEqual(self.client.get("/api/crud").status_code, 401)

    def test_csrf_safe_errors_and_request_reference(self):
        csrf_app = create_app({
            "TESTING": True,
            "PROPAGATE_EXCEPTIONS": False,
            "WTF_CSRF_ENABLED": True,
            "AUTO_BACKUP_ENABLED": False,
        })
        @csrf_app.get("/_test_internal_error")
        def internal_error():
            raise RuntimeError("detail internal yang tidak boleh bocor")

        csrf_client = csrf_app.test_client()
        csrf_error = csrf_client.post(
            "/api/auth/login", json={"username": "admin1", "password": PASSWORD}
        )
        self.assertEqual(csrf_error.status_code, 400)
        self.assertEqual(csrf_error.get_json()["code"], csrf_error.headers["X-Request-ID"])

        server_error = csrf_client.get("/_test_internal_error")
        self.assertEqual(server_error.status_code, 500)
        body = server_error.get_data(as_text=True)
        self.assertNotIn("RuntimeError", body)
        self.assertNotIn("detail internal", body)
        self.assertEqual(server_error.get_json()["code"], server_error.headers["X-Request-ID"])

    def test_backup_and_restore(self):
        backup = create_backup("test-restore")
        with transaction() as conn:
            conn.execute(
                'UPDATE pelaku_ekraf SET "Nama Usaha" = ? WHERE "Nama Usaha" = ?',
                ("BERUBAH", "Usaha Rahasia"),
            )
        restore_backup(backup.name, confirm="RESTORE")
        with closing(connect_db()) as conn:
            restored = conn.execute(
                'SELECT "Nama Usaha" FROM pelaku_ekraf WHERE "Nama Narasumber" = ?',
                ("Nama Rahasia",),
            ).fetchone()[0]
        self.assertEqual(restored, "Usaha Rahasia")
        self.assertTrue((Path(BACKUP_DIR) / "restore-history.jsonl").exists())

    def test_production_configuration_fails_closed(self):
        safe_environment = os.environ.copy()
        safe_environment.update({
            "FLASK_ENV": "production",
            "FLASK_DEBUG": "false",
            "SECRET_KEY": "production-test-secret-with-at-least-32-characters",
            "ALLOWED_ORIGINS": "https://dashboard.example.test",
            "BACKUP_DIR": str(TEST_ROOT / "production-backups"),
            "SESSION_COOKIE_SECURE": "true",
        })
        valid = subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=Path(__file__).resolve().parents[1],
            env=safe_environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)

        insecure_environment = safe_environment | {"FLASK_DEBUG": "true"}
        rejected = subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=Path(__file__).resolve().parents[1],
            env=insecure_environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("production tidak aman", rejected.stderr)

        insecure_cookie = safe_environment | {"SESSION_COOKIE_SECURE": "false"}
        rejected_cookie = subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=Path(__file__).resolve().parents[1],
            env=insecure_cookie,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(rejected_cookie.returncode, 0)
        self.assertIn("cookie sesi Secure", rejected_cookie.stderr)


if __name__ == "__main__":
    unittest.main()

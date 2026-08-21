import unittest
from unittest.mock import patch

from app import create_app
from api.survey import _page_arg


class SurveyRouteAccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These assertions cover anonymous routing only; they do not need a
        # live PostgreSQL instance in CI.
        with patch("app.init_users_table"):
            cls.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        cls.client = cls.app.test_client()

    def test_survey_pages_redirect_anonymous_users_to_admin_login(self):
        for path in ("/survei", "/survei/periode-2026", "/survei/kelola"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin", response.headers["Location"])

    def test_survey_apis_reject_anonymous_users(self):
        for path in (
            "/api/survey/periods",
            "/api/survey/periods/2026/summary",
            "/api/survey/periods/2026/actors?page=1&per_page=50",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertFalse(response.get_json()["success"])

    def test_actor_page_size_is_capped_at_fifty(self):
        with self.app.test_request_context("/api/survey/periods/2026/actors?per_page=500"):
            self.assertEqual(_page_arg("per_page", 50, maximum=50), 50)


if __name__ == "__main__":
    unittest.main()

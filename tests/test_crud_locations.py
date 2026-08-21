import unittest

from flask import Flask

from api.crud import _bounded_int, validate_actor_payload


class EmptyReferenceConnection:
    def execute(self, *_args, **_kwargs):
        return []


class CrudLocationTest(unittest.TestCase):
    def test_accepts_new_kecamatan_and_kelurahan(self):
        values, errors = validate_actor_payload(
            {
                "nama_narasumber": "Contoh",
                "nama_usaha": "Usaha Contoh",
                "alamat": "Alamat",
                "kecamatan": "Kecamatan Baru",
                "kelurahan": "Kelurahan Baru",
                "subsektor": "8) Kuliner",
                "latitude": -7.98,
                "longitude": 112.63,
            },
            EmptyReferenceConnection(),
        )

        self.assertEqual(errors, [])
        self.assertEqual(values["Kecamatan"], "Kecamatan Baru")
        self.assertEqual(values["Kelurahan"], "Kelurahan Baru")


class CrudPaginationTest(unittest.TestCase):
    def test_page_size_is_bounded(self):
        app = Flask(__name__)
        with app.test_request_context("/api/crud?page=0&per_page=500"):
            self.assertEqual(_bounded_int("page", 1, 1, 2_147_483_647), 1)
            self.assertEqual(_bounded_int("per_page", 25, 1, 50), 50)


if __name__ == "__main__":
    unittest.main()

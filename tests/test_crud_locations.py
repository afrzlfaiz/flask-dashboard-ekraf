import unittest

from api.crud import validate_actor_payload


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


if __name__ == "__main__":
    unittest.main()

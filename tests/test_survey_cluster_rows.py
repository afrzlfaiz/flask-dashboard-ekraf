import unittest

import pandas as pd

from api.survey import _actor_rows


class SurveyClusterRowsTest(unittest.TestCase):
    def test_keeps_actor_identity_and_marks_incomplete_rows(self):
        source = pd.DataFrame([
            {
                "survey_response_id": 11,
                "survey_row_number": 2,
                "nama_usaha": "Usaha A",
                "subsektor_ringkas": "Kuliner",
                "kecamatan": "Klojen",
                "kelurahan": "Oro-Oro Dowo",
                "klasifikasi_umkm": "Mikro",
            },
            {
                "survey_response_id": 12,
                "survey_row_number": 3,
                "nama_usaha": "Usaha B",
                "subsektor_ringkas": "Kriya",
                "kecamatan": "Sukun",
                "kelurahan": "Sukun",
                "klasifikasi_umkm": "Kecil",
            },
        ])
        modeled = pd.DataFrame([
            {
                "survey_response_id": 11,
                "cluster_id": 0,
                "cluster": "Cluster 0",
                "penjualan_tahunan": 100,
                "margin_profit": 0.2,
                "tenaga_kerja": 2,
            },
        ])

        actors = _actor_rows(source, modeled)

        self.assertEqual(actors[0]["nama_usaha"], "Usaha A")
        self.assertEqual(actors[0]["cluster"], "Cluster 0")
        self.assertEqual(actors[1]["status"], "Data tidak lengkap")


if __name__ == "__main__":
    unittest.main()

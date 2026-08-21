import unittest

import pandas as pd

from api.survey import _summary
from utils.survey_loader import _analysis_records


class SurveyClusterRowsTest(unittest.TestCase):
    def test_keeps_actor_identity_and_marks_incomplete_rows(self):
        source = pd.DataFrame([
            {
                "survey_row_number": 2,
                "nama_usaha": "Usaha A",
                "subsektor_ringkas": "Kuliner",
                "kecamatan": "Klojen",
                "kelurahan": "Oro-Oro Dowo",
                "klasifikasi_umkm": "Mikro",
            },
            {
                "survey_row_number": 3,
                "nama_usaha": "Usaha B",
                "subsektor_ringkas": "Kriya",
                "kecamatan": "Sukun",
                "kelurahan": "Sukun",
                "klasifikasi_umkm": "Kecil",
            },
        ])
        model = pd.DataFrame([
            {
                "survey_row_number": 2,
                "cluster_id": 0,
                "cluster": "Cluster 0",
                "pc1": 1.0,
                "pc2": 2.0,
                "penjualan_tahunan": 100,
                "margin_profit": 0.2,
                "tenaga_kerja": 2,
                "barang_tetap": 50,
                "rasio_bahan_baku": 0.1,
                "rasio_utilitas": 0.1,
                "rasio_penggajian": 0.1,
                "tekanan_biaya_terpilih": 0.3,
            },
        ])

        records = _analysis_records(
            {"df": source, "model_df": model},
            [{"id": 11, "row_number": 2}, {"id": 12, "row_number": 3}],
        )

        self.assertEqual(records[0]["nama_usaha"], "Usaha A")
        self.assertEqual(records[0]["cluster_label"], "Cluster 0")
        self.assertEqual(records[0]["status"], "Terpetakan")
        self.assertEqual(records[1]["status"], "Data tidak lengkap")

    def test_summary_uses_only_selected_cluster_rows(self):
        frame = pd.DataFrame([
            {
                "cluster": "Cluster 0", "status": "Terpetakan", "penjualan_tahunan": 100,
                "margin_profit": 0.2, "tenaga_kerja": 2, "barang_tetap": 50,
                "rasio_bahan_baku": 0.1, "rasio_utilitas": 0.1, "rasio_penggajian": 0.1,
                "rasio_barang_tetap": 0.5, "tekanan_biaya_terpilih": 0.3,
            },
            {
                "cluster": "Noise", "status": "Noise", "penjualan_tahunan": 80,
                "margin_profit": 0.1, "tenaga_kerja": 1, "barang_tetap": 20,
                "rasio_bahan_baku": 0.2, "rasio_utilitas": 0.1, "rasio_penggajian": 0.1,
                "rasio_barang_tetap": 0.25, "tekanan_biaya_terpilih": 0.4,
            },
        ])
        period = {
            "id": 1, "survey_year": 2026, "label": "Survei 2026", "source_filename": "survey.xlsx",
            "source_sheet": "Sheet6", "rows": 2, "valid_rows": 2,
            "analysis_version": "test", "analysis_meta": {"eps": 2.187, "min_samples": 12},
        }

        result = _summary(period, frame[frame["cluster"] == "Cluster 0"], "Cluster 0")

        self.assertEqual(result["filters"]["cluster"], "Cluster 0")
        self.assertEqual(result["kpi"]["total_observasi"], 1)
        self.assertEqual(result["charts"]["cluster"]["labels"], ["Cluster 0"])



if __name__ == "__main__":
    unittest.main()

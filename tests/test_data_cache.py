"""Small regression check for the shared dashboard data cache."""

import unittest
from unittest.mock import patch

import pandas as pd

from utils import data_loader


class DataCacheTests(unittest.TestCase):
    def setUp(self):
        data_loader.invalidate_data_cache()

    def test_cache_reuses_data_and_invalidation_reloads_it(self):
        frame = pd.DataFrame([{
            "Nama Narasumber": "Contoh",
            "Kecamatan": "Klojen",
            "Kelurahan": "Klojen",
            "Alamat": "Jalan Contoh",
            "Sub Sektor": "8) Kuliner",
            "lat": -7.98,
            "lon": 112.63,
        }])
        with patch.object(data_loader, "_load_from_database", return_value=frame) as load:
            first, _ = data_loader.load_data()
            first.loc[0, "Kecamatan"] = "Diubah oleh pemanggil"
            second, _ = data_loader.load_data()
            self.assertEqual(load.call_count, 1)
            self.assertEqual(second.loc[0, "Kecamatan"], "Klojen")

            data_loader.invalidate_data_cache()
            data_loader.load_data()
            self.assertEqual(load.call_count, 2)


if __name__ == "__main__":
    unittest.main()

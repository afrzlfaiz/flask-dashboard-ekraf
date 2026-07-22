"""Memuat dan membersihkan data dari PostgreSQL."""

from threading import Lock
from time import monotonic
from typing import Tuple

import pandas as pd

from config import DATABASE_URL
from utils.database import connection

_CACHE_SECONDS = 20
_cache_lock = Lock()
_cache: tuple[float, pd.DataFrame, dict] | None = None

def _load_from_database(database_url: str) -> pd.DataFrame:
    with connection(database_url) as conn:
        rows = conn.execute("SELECT * FROM pelaku_ekraf WHERE is_active = 1").fetchall()
        return pd.DataFrame([dict(row) for row in rows])


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Pembersihan: drop baris tanpa Kecamatan/Nama, koordinat numeric, whitespace."""
    df = df.dropna(subset=["Kecamatan"])

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    str_cols = ["Nama Narasumber", "Alamat", "Kelurahan", "Kecamatan", "Sub Sektor"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df = df.dropna(subset=["Nama Narasumber"])
    df = df[df["Nama Narasumber"] != ""]
    df = df[df["Nama Narasumber"] != "nan"]

    return df.reset_index(drop=True)


def _meta_for(df: pd.DataFrame) -> dict:
    total_baris = len(df)
    geocoded = df["lat"].notna().sum() if "lat" in df.columns else 0
    geocoding_rate = (geocoded / total_baris * 100) if total_baris > 0 else 0.0
    return {
        "total_baris": total_baris,
        "geocoded_count": int(geocoded),
        "geocoding_rate": geocoding_rate,
    }


def load_data(database_url: str | None = None) -> Tuple[pd.DataFrame, dict]:
    """Baca data aktif dari PostgreSQL dan kembalikan DataFrame beserta metadata."""
    global _cache
    url = database_url or DATABASE_URL
    now = monotonic()
    with _cache_lock:
        if url == DATABASE_URL and _cache and now - _cache[0] < _CACHE_SECONDS:
            return _cache[1].copy(), dict(_cache[2])

        df = _clean(_load_from_database(url))
        meta = _meta_for(df)
        if url == DATABASE_URL:
            _cache = (now, df, meta)
        return df.copy(), dict(meta)


def invalidate_data_cache() -> None:
    """Pastikan perubahan CRUD/import langsung terlihat pada request berikutnya."""
    global _cache
    with _cache_lock:
        _cache = None

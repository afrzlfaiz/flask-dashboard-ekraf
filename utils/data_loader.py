"""Memuat dan membersihkan data dari PostgreSQL."""

from typing import Tuple

import pandas as pd

from config import DATABASE_URL
from utils.database import connect_db

def _load_from_database(database_url: str) -> pd.DataFrame:
    conn = connect_db(database_url)
    try:
        rows = conn.execute("SELECT * FROM pelaku_ekraf WHERE is_active = 1").fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        conn.close()


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
    df = _clean(_load_from_database(database_url or DATABASE_URL))
    return df, _meta_for(df)

"""
Memuat dan membersihkan data dari SQLite (fallback: Excel multi-sheet).
Mengikuti pola dari main.ipynb cell 1.
"""

import os
import sqlite3
from pathlib import Path
from typing import Tuple

import pandas as pd

from config import DB_PATH

EXCEL_PATH = "data/ekraf.xlsx"

# ponytail: cache DataFrame bersih di memori, invalidasi via mtime file DB.
# Semua mutasi lewat SQLite (CRUD/impor) → mtime berubah saat commit → reload.
_df_cache: pd.DataFrame | None = None
_df_mtime: float | None = None


def _load_from_sqlite(db_path: str) -> pd.DataFrame:
    """Baca data dari SQLite. Hanya baris aktif (is_active = 1)."""
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql("SELECT * FROM pelaku_ekraf WHERE is_active = 1", conn)
    finally:
        conn.close()


def _load_from_excel(filepath: str) -> pd.DataFrame:
    """Baca semua sheet dari Excel (dinamis)."""
    sheets = pd.read_excel(filepath, sheet_name=None)
    dfs: list[pd.DataFrame] = []
    for name, df_sheet in sheets.items():
        df_sheet["Sheet"] = name
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)


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


def load_data(filepath: str | None = None) -> Tuple[pd.DataFrame, dict]:
    """Baca data dari SQLite (default) atau Excel (fallback), bersihkan, kembalikan DataFrame + metadata."""
    global _df_cache, _df_mtime
    if filepath is None:
        filepath = DB_PATH

    # Cache hanya untuk sumber SQLite default; Excel fallback selalu baca ulang.
    if filepath.endswith(".db") and Path(filepath).exists():
        mtime = os.path.getmtime(filepath)
        if _df_cache is not None and _df_mtime == mtime:
            # Sumber sama persis — kembalikan copy agar pemanggil bebas mutasi tanpa mengontaminasi cache.
            return _df_cache.copy(), _meta_for(_df_cache)

        df = _clean(_load_from_sqlite(filepath))
        if filepath == DB_PATH:
            _df_cache = df.copy()
            _df_mtime = mtime
        return df, _meta_for(df)

    if Path(EXCEL_PATH).exists():
        df = _clean(_load_from_excel(EXCEL_PATH))
    else:
        df = _clean(_load_from_excel(filepath))  # user-provided path
    return df, _meta_for(df)

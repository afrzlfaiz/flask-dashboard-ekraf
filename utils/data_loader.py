"""
Memuat dan membersihkan data dari SQLite (fallback: Excel multi-sheet).
Mengikuti pola dari main.ipynb cell 1.
"""

import sqlite3
from pathlib import Path
from typing import Tuple

import pandas as pd

from config import DB_PATH

EXCEL_PATH = "data/ekraf.xlsx"


def _load_from_sqlite(db_path: str) -> pd.DataFrame:
    """Baca data dari SQLite."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM pelaku_ekraf", conn)
    conn.close()
    return df


def _load_from_excel(filepath: str) -> pd.DataFrame:
    """Baca semua sheet dari Excel (dinamis)."""
    sheets = pd.read_excel(filepath, sheet_name=None)
    dfs: list[pd.DataFrame] = []
    for name, df_sheet in sheets.items():
        df_sheet["Sheet"] = name
        dfs.append(df_sheet)
    return pd.concat(dfs, ignore_index=True)


def load_data(filepath: str | None = None) -> Tuple[pd.DataFrame, dict]:
    """Baca data dari SQLite (default) atau Excel (fallback), bersihkan, kembalikan DataFrame + metadata."""
    if filepath is None:
        filepath = DB_PATH

    if filepath.endswith(".db") and Path(filepath).exists():
        df = _load_from_sqlite(filepath)
    elif Path(EXCEL_PATH).exists():
        df = _load_from_excel(EXCEL_PATH)
    else:
        df = _load_from_excel(filepath)  # user-provided path

    # ── Cleaning ───────────────────────────────────────────
    # Drop baris tanpa Kecamatan
    df = df.dropna(subset=["Kecamatan"])

    # Konversi koordinat ke numeric
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    # Bersihkan whitespace di kolom string
    str_cols = ["Nama Narasumber", "Alamat", "Kelurahan", "Kecamatan", "Sub Sektor"]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Drop baris kosong (Nama Narasumber kosong / NaN)
    df = df.dropna(subset=["Nama Narasumber"])
    df = df[df["Nama Narasumber"] != ""]
    df = df[df["Nama Narasumber"] != "nan"]

    # Reset index setelah concat + drop
    df = df.reset_index(drop=True)

    # ── Metadata ───────────────────────────────────────────
    total_baris = len(df)
    geocoded = df["lat"].notna().sum()
    geocoding_rate = (geocoded / total_baris * 100) if total_baris > 0 else 0.0

    meta = {
        "total_baris": total_baris,
        "geocoded_count": geocoded,
        "geocoding_rate": geocoding_rate,
    }

    return df, meta

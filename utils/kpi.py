"""KPI metric calculations — return dict for API consumption."""

import pandas as pd


def get_kpi_metrics(df: pd.DataFrame) -> dict:
    """Return KPI metrics dict from filtered DataFrame."""
    total_pelaku = len(df)
    total_kecamatan = df["Kecamatan"].dropna().nunique() if "Kecamatan" in df.columns else 0
    total_kelurahan = df["Kelurahan"].dropna().nunique() if "Kelurahan" in df.columns else 0
    total_subsektor = df["Sub Sektor"].dropna().nunique() if "Sub Sektor" in df.columns else 0
    total_valid = df.dropna(subset=["lat", "lon"]).shape[0] if "lat" in df.columns and "lon" in df.columns else 0

    return {
        "total_pelaku": total_pelaku,
        "total_kecamatan": total_kecamatan,
        "total_kelurahan": total_kelurahan,
        "total_subsektor": total_subsektor,
        "total_valid": total_valid,
    }

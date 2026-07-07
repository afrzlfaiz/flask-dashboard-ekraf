"""
DBSCAN clustering untuk pelaku ekonomi kreatif.
Mengikuti pola dari main.ipynb cells e71804fa, aae82afb, ba726cf2.
"""

from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from config import DBSCAN_EPS, DBSCAN_MIN_SAMPLES, DBSCAN_METRIC


def run_dbscan(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Jalankan DBSCAN clustering pada data yang memiliki koordinat valid.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame dengan kolom lat, lon

    Returns
    -------
    data : pd.DataFrame
        DataFrame dengan kolom tambahan 'cluster' (-1 = noise)
    stats : dict
        n_clusters, n_noise, n_total
    """
    data = df.dropna(subset=["lat", "lon"]).copy()

    if data.empty:
        return data, {"n_clusters": 0, "n_noise": 0, "n_total": 0}

    coords = np.radians(data[["lat", "lon"]].values)

    dbscan = DBSCAN(
        eps=DBSCAN_EPS,
        min_samples=DBSCAN_MIN_SAMPLES,
        metric=DBSCAN_METRIC,
    )
    data["cluster"] = dbscan.fit_predict(coords)

    n_clusters = data["cluster"].nunique() - (1 if -1 in data["cluster"].unique() else 0)
    n_noise = (data["cluster"] == -1).sum()

    stats = {
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "n_total": len(data),
    }

    return data, stats


def get_cluster_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Buat ringkasan statistik per cluster (tanpa noise).

    Parameters
    ----------
    data : pd.DataFrame
        Output dari run_dbscan (memiliki kolom 'cluster')

    Returns
    -------
    pd.DataFrame
        Kolom: Jumlah, Kecamatan, Kelurahan, Latitude, Longitude, Subsektor Dominan
    """
    clustered = data[data["cluster"] != -1]

    if clustered.empty:
        return pd.DataFrame()

    summary = (
        clustered.groupby("cluster")
        .agg(
            Jumlah=("cluster", "size"),
            Kecamatan=("Kecamatan", lambda x: x.mode().iloc[0] if not x.mode().empty else ""),
            Kelurahan=("Kelurahan", lambda x: x.mode().iloc[0] if not x.mode().empty else ""),
            Latitude=("lat", "mean"),
            Longitude=("lon", "mean"),
        )
        .sort_values("Jumlah", ascending=False)
    )

    subsektor = (
        clustered.groupby("cluster")["Sub Sektor"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "")
    )

    summary["Subsektor Dominan"] = subsektor

    # Format koordinat
    summary["Latitude"] = summary["Latitude"].round(6)
    summary["Longitude"] = summary["Longitude"].round(6)

    return summary


"""
Sistem filter real-time untuk dashboard.
Seluruh filter diterapkan pada DataFrame, hasilnya digunakan oleh semua komponen.
"""

import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    kecamatan_list: list[str] | None = None,
    kelurahan_list: list[str] | None = None,
    subsektor_list: list[str] | None = None,
    search_text: str = "",
) -> pd.DataFrame:
    """Terapkan seluruh filter pada DataFrame dan kembalikan hasil yang sudah difilter.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame sumber (full data)
    kecamatan_list : list[str] or None
        Daftar kecamatan terpilih (multi-select). [] atau None berarti semua.
    kelurahan_list : list[str] or None
        Daftar kelurahan terpilih (multi-select). [] atau None berarti semua.
    subsektor_list : list[str] or None
        Daftar subsektor terpilih (multi-select). [] atau None berarti semua.
    search_text : str
        Teks pencarian nama narasumber (case-insensitive)

    Returns
    -------
    pd.DataFrame
        DataFrame hasil filter
    """
    filtered = df.copy()

    # ── Filter Kecamatan (multi-select) ────────────────────
    if kecamatan_list:
        filtered = filtered[filtered["Kecamatan"].isin(kecamatan_list)]

    # ── Filter Kelurahan (multi-select) ────────────────────
    if kelurahan_list:
        filtered = filtered[filtered["Kelurahan"].isin(kelurahan_list)]

    # ── Filter Subsektor (multi-select) ────────────────────
    if subsektor_list:
        filtered = filtered[filtered["Sub Sektor"].isin(subsektor_list)]

    # ── Filter Nama Narasumber (text search) ───────────────
    if search_text:
        filtered = filtered[
            filtered["Nama Narasumber"]
            .str.contains(search_text, case=False, na=False)
        ]

    return filtered

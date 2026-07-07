"""
Utilitas umum: filter info text, kelurahan options, row serialization.
"""

import pandas as pd


def row_to_dict(row: pd.Series) -> dict:
    """Convert a DataFrame row to the standard API dict format."""
    nama_usaha = row.get("Nama Usaha", "")
    if pd.isna(nama_usaha) or str(nama_usaha).strip() == "" or str(nama_usaha) == "nan":
        nama_usaha = row.get("Nama Narasumber", "")

    tahun_berdiri = row.get("Tahun Berdiri")
    if pd.notna(tahun_berdiri) and str(tahun_berdiri).strip() != "" and str(tahun_berdiri) != "nan":
        try:
            tahun_berdiri = int(float(tahun_berdiri))
        except ValueError:
            tahun_berdiri = ""
    else:
        tahun_berdiri = ""

    return {
        "id": int(row.get("id", 0)) if row.get("id") is not None else 0,
        "nama_narasumber": str(row.get("Nama Narasumber", "")),
        "nama_usaha": str(nama_usaha),
        "kecamatan": str(row.get("Kecamatan", "")),
        "kelurahan": str(row.get("Kelurahan", "")),
        "alamat": str(row.get("Alamat", "")),
        "latitude": float(row["lat"]) if row.get("lat") and not pd.isna(row["lat"]) else None,
        "longitude": float(row["lon"]) if row.get("lon") and not pd.isna(row["lon"]) else None,
        "subsektor": str(row.get("Sub Sektor", "")),
        "kategori_usaha": str(row.get("Kategori Usaha", "")) if pd.notna(row.get("Kategori Usaha")) and str(row.get("Kategori Usaha")) != "nan" else "",
        "tahun_berdiri": tahun_berdiri,
        "no_hp": str(row.get("No Telp", "")) if pd.notna(row.get("No Telp")) and str(row.get("No Telp")) != "nan" else "",
        "email": str(row.get("Email", "")) if pd.notna(row.get("Email")) and str(row.get("Email")) != "nan" else "",
    }


def get_kelurahan_options(df: pd.DataFrame, kecamatan_list: list[str] | None = None) -> list[str]:
    """Daftar kelurahan unik (diurutkan), difilter berdasarkan kecamatan jika dipilih."""
    if kecamatan_list:
        filtered = df[df["Kecamatan"].isin(kecamatan_list)]
    else:
        filtered = df
    return sorted(filtered["Kelurahan"].dropna().unique().tolist())


def format_filter_info(n_filtered: int, n_total: int) -> str:
    """Teks informasi: 'Menampilkan 78 dari 312 pelaku'."""
    return f"Menampilkan {n_filtered} dari {n_total} pelaku"

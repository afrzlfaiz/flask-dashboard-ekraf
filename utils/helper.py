"""
Utilitas umum: filter info text, kelurahan options, row serialization.
"""

import pandas as pd


def row_to_dict(row: pd.Series, public: bool = False, can_view_pii: bool = True) -> dict:
    """Convert a DataFrame row to the standard API dict format.

    Parameters
    ----------
    row : pd.Series
    public : bool
        If True, strip all identity fields (name, address, phone, email) for public endpoints.
    can_view_pii : bool
        If False, strip phone and email for viewer-role users who can see names/addresses
        but not contact details. Ignored when ``public`` is True.
    """
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

    result = {
        "kecamatan": str(row.get("Kecamatan", "")),
        "kelurahan": str(row.get("Kelurahan", "")),
        "subsektor": str(row.get("Sub Sektor", "")),
        "kategori_usaha": str(row.get("Kategori Usaha", "")) if pd.notna(row.get("Kategori Usaha")) and str(row.get("Kategori Usaha")) != "nan" else "",
        "tahun_berdiri": tahun_berdiri,
    }

    # Record-level identity and precise coordinates are internal-only.
    if not public:
        result["id"] = int(row.get("id", 0)) if row.get("id") is not None else 0
        result["nama_narasumber"] = str(row.get("Nama Narasumber", ""))
        result["nama_usaha"] = str(nama_usaha)
        result["latitude"] = float(row["lat"]) if row.get("lat") and not pd.isna(row["lat"]) else None
        result["longitude"] = float(row["lon"]) if row.get("lon") and not pd.isna(row["lon"]) else None
        result["alamat"] = str(row.get("Alamat", ""))
        if can_view_pii:
            result["no_hp"] = str(row.get("No Telp", "")) if pd.notna(row.get("No Telp")) and str(row.get("No Telp")) != "nan" else ""
            result["email"] = str(row.get("Email", "")) if pd.notna(row.get("Email")) and str(row.get("Email")) != "nan" else ""

    return result


def get_kelurahan_options(df: pd.DataFrame, kecamatan_list: list[str] | None = None) -> list[str]:
    """Daftar kelurahan unik (diurutkan), difilter berdasarkan kecamatan jika dipilih."""
    if kecamatan_list:
        filtered = df[df["Kecamatan"].isin(kecamatan_list)]
    else:
        filtered = df
    return sorted(filtered["Kelurahan"].dropna().unique().tolist())


def get_location_options(
    df: pd.DataFrame, kecamatan_list: list[str] | None = None
) -> list[dict[str, str]]:
    """Pasangan kecamatan-kelurahan untuk pilihan lokasi berkelompok."""
    if kecamatan_list:
        df = df[df["Kecamatan"].isin(kecamatan_list)]

    return (
        df[["Kecamatan", "Kelurahan"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["Kecamatan", "Kelurahan"])
        .rename(columns={"Kecamatan": "kecamatan", "Kelurahan": "kelurahan"})
        .to_dict("records")
    )


def format_filter_info(n_filtered: int, n_total: int) -> str:
    """Teks informasi: 'Menampilkan 78 dari 312 pelaku'."""
    return f"Menampilkan {n_filtered} dari {n_total} pelaku"

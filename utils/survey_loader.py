"""Load and prepare the annual Ekraf survey used by the survey panel."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler

from config import SURVEY_SHEET_NAME


MODEL_FEATURES = [
    "log_penjualan",
    "margin_profit",
    "log_tenaga_kerja",
    "log_barang_tetap",
    "rasio_bahan_baku",
    "rasio_utilitas",
    "rasio_penggajian",
]

FEATURE_LABELS = {
    "log_penjualan": "Skala penjualan",
    "margin_profit": "Margin profit",
    "log_tenaga_kerja": "Penyerapan tenaga kerja",
    "log_barang_tetap": "Kapasitas aset",
    "rasio_bahan_baku": "Intensitas bahan baku",
    "rasio_utilitas": "Beban utilitas",
    "rasio_penggajian": "Intensitas penggajian",
}

# Parameter final yang sudah dipilih pada notebook 7 fitur + RobustScaler.
FINAL_EPS = 2.187
FINAL_MIN_SAMPLES = 12
ANALYSIS_VERSION = "ekraf-7fitur-robustscaler-dbscan-v2"

_RENAME_MAP = {
    "Nama Usaha": "nama_usaha",
    "Apa jenis usaha Anda": "subsektor",
    "Klasifikasi UMKM": "klasifikasi_umkm",
    "Jenis Kelamin": "jenis_kelamin",
    "Usia": "usia",
    "Kelurahan": "kelurahan",
    "Kecamatan": "kecamatan",
    "Hasil Penjualan Tahunan Perusahaan": "penjualan_tahunan",
    "Konsumsi Antara": "konsumsi_antara",
    "Profit": "profit",
    "Jumlah Tenaga Kerja": "tenaga_kerja",
    "Bahan Baku Utama per Tahun": "bahan_baku_utama",
    "Bahan Baku Tambahan per Tahun": "bahan_baku_tambahan",
    "Barang Tetap": "barang_tetap",
    "Bahan Bakar per Tahun": "bahan_bakar",
    "Listrik per Tahun": "listrik",
    "Tagihan Air per Tahun": "air",
    "Gaji Seluruh Karyawan setiap bulan (Termasuk lembur, bonus, tunjangan, asuransi, dll)": "gaji_karyawan_bulanan",
    "Sewa Bangunan per Tahun": "sewa_bangunan",
    "Besaran bunga atas pinjaman/pajak/royalti dan lainlain": "bunga_pajak_royalti",
    "Kualifikasi pendidikan karyawan": "pendidikan_karyawan",
}

SURVEY_TEMPLATE_COLUMNS = list(_RENAME_MAP)

_REQUIRED_COLUMNS = {
    "nama_usaha",
    "subsektor",
    "klasifikasi_umkm",
    "kelurahan",
    "kecamatan",
    "penjualan_tahunan",
    "konsumsi_antara",
    "profit",
    "tenaga_kerja",
    "bahan_baku_utama",
    "bahan_baku_tambahan",
    "barang_tetap",
    "bahan_bakar",
    "listrik",
    "air",
    "gaji_karyawan_bulanan",
}

_NUMERIC_COLUMNS = [
    "usia",
    "penjualan_tahunan",
    "konsumsi_antara",
    "profit",
    "tenaga_kerja",
    "bahan_baku_utama",
    "bahan_baku_tambahan",
    "barang_tetap",
    "bahan_bakar",
    "listrik",
    "air",
    "gaji_karyawan_bulanan",
    "sewa_bangunan",
    "bunga_pajak_royalti",
]

STORAGE_COLUMNS = [
    "nama_usaha",
    "subsektor",
    "klasifikasi_umkm",
    "jenis_kelamin",
    "usia",
    "kelurahan",
    "kecamatan",
    "penjualan_tahunan",
    "konsumsi_antara",
    "profit",
    "tenaga_kerja",
    "bahan_baku_utama",
    "bahan_baku_tambahan",
    "barang_tetap",
    "bahan_bakar",
    "listrik",
    "air",
    "gaji_karyawan_bulanan",
    "sewa_bangunan",
    "bunga_pajak_royalti",
    "pendidikan_karyawan",
]

_PROFILE_COLUMNS = [
    "penjualan_tahunan",
    "margin_profit",
    "tenaga_kerja",
    "barang_tetap",
    "rasio_bahan_baku",
    "rasio_utilitas",
    "rasio_penggajian",
    "rasio_barang_tetap",
    "tekanan_biaya_terpilih",
]

_cache_lock = Lock()
_cache: dict[int, dict] = {}


class SurveyPeriodExistsError(ValueError):
    """Raised when a survey year or source file is already stored."""


def _normalise_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename and clean workbook fields before deriving model features."""
    frame = raw.copy()
    frame.columns = frame.columns.astype(str).str.strip()
    df = frame.rename(columns=_RENAME_MAP).copy()
    missing = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Kolom survei wajib tidak ditemukan: {', '.join(missing)}")

    for column in [
        "nama_usaha", "subsektor", "klasifikasi_umkm", "jenis_kelamin",
        "kelurahan", "kecamatan", "pendidikan_karyawan",
    ]:
        if column in df:
            df[column] = df[column].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()

    for column in _NUMERIC_COLUMNS:
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in [
        "penjualan_tahunan", "tenaga_kerja", "bahan_baku_utama", "bahan_baku_tambahan",
        "barang_tetap", "bahan_bakar", "listrik", "air", "gaji_karyawan_bulanan",
        "sewa_bangunan", "bunga_pajak_royalti",
    ]:
        if column in df:
            df.loc[df[column] < 0, column] = np.nan

    for column in STORAGE_COLUMNS:
        if column not in df:
            df[column] = pd.NA
    df["subsektor_ringkas"] = df["subsektor"].str.replace(r"\s*\(.*$", "", regex=True).str.strip()
    return df


def _json_scalar(value: Any):
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _storage_records(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    df = _normalise_frame(raw)
    records = [
        {column: _json_scalar(row[column]) for column in STORAGE_COLUMNS}
        for _, row in df[STORAGE_COLUMNS].iterrows()
    ]
    return df, records


def _profile_level(value: float, reference: pd.Series) -> str:
    if pd.isna(value):
        return "tidak tersedia"
    q1, q2 = reference.quantile([1 / 3, 2 / 3]).values
    if value < q1:
        return "rendah"
    if value <= q2:
        return "sedang"
    return "tinggi"


def _classify_policy(cluster_name: str, row: pd.Series) -> tuple[str, str]:
    if cluster_name == "Noise":
        return (
            "Usaha dengan karakteristik khusus",
            "Telaah individual diperlukan karena observasi ini berbeda dari kepadatan cluster utama.",
        )

    sales = row["level_penjualan"]
    margin = row["level_margin"]
    labor = row["level_tenaga_kerja"]
    asset = row["level_aset"]
    cost = row["level_tekanan_biaya"]
    sales_rank = row.get("rank_penjualan_cluster", 0)
    margin_rank = row.get("rank_margin_cluster", 0)
    labor_rank = row.get("rank_tk_cluster", 0)

    if sales in {"sedang", "tinggi"} and margin in {"sedang", "tinggi"} and asset == "rendah" and sales_rank >= 0.80 and margin_rank >= 0.80:
        return (
            "Usaha produktif berbasis aset ringan",
            "Perluas akses pasar, jejaring, dan digitalisasi tanpa memaksakan investasi aset fisik.",
        )
    if sales == "tinggi" and margin == "tinggi":
        if labor == "tinggi" or labor_rank >= 0.80:
            return (
                "Usaha unggulan penyerap tenaga kerja",
                "Fasilitasi ekspansi pasar, kemitraan, dan peningkatan produktivitas tenaga kerja.",
            )
        return (
            "Usaha unggulan efisien",
            "Fasilitasi perluasan pasar dan kemitraan secara berkelanjutan.",
        )
    if sales == "rendah" and margin == "tinggi" and cost != "tinggi":
        return (
            "Usaha skala kecil berpotensi berkembang",
            "Prioritaskan pengembangan kapasitas, akses pasar, promosi, digitalisasi, dan permodalan.",
        )
    if margin == "rendah" and cost == "tinggi":
        return (
            "Usaha prioritas peningkatan efisiensi",
            "Fokus pada efisiensi bahan baku, utilitas, penggajian, dan pendampingan manajemen.",
        )
    if sales == "rendah" and margin == "rendah":
        return (
            "Usaha prioritas penguatan",
            "Perkuat pengelolaan usaha, akses pasar, efisiensi biaya, kualitas produk, dan kapasitas.",
        )
    if labor == "tinggi" and sales in {"sedang", "tinggi"}:
        return (
            "Usaha berkembang padat karya",
            "Dorong produktivitas tenaga kerja, kompetensi, efisiensi produksi, dan perluasan pasar.",
        )
    return (
        "Usaha berkembang stabil",
        "Pertahankan kinerja dan dorong peningkatan kapasitas secara bertahap.",
    )


def _build_profiles(data: pd.DataFrame, reference: pd.DataFrame, cluster_order: list[str]) -> list[dict]:
    if data.empty:
        return []

    medians = data.groupby("cluster")[_PROFILE_COLUMNS].median().reindex(cluster_order)
    counts = data["cluster"].value_counts().reindex(cluster_order, fill_value=0)
    non_noise = [
        cluster for cluster in cluster_order
        if cluster != "Noise" and int(counts.get(cluster, 0)) > 0
    ]

    profile = medians.copy()
    for source_col, rank_col in [
        ("penjualan_tahunan", "rank_penjualan_cluster"),
        ("margin_profit", "rank_margin_cluster"),
        ("tenaga_kerja", "rank_tk_cluster"),
    ]:
        profile[rank_col] = np.nan
        if non_noise:
            profile.loc[non_noise, rank_col] = profile.loc[non_noise, source_col].rank(pct=True)

    rows = []
    total = len(data)
    for cluster in cluster_order:
        if cluster not in profile.index or int(counts.get(cluster, 0)) == 0:
            continue
        row = profile.loc[cluster].copy()
        row["level_penjualan"] = _profile_level(row["penjualan_tahunan"], reference["penjualan_tahunan"])
        row["level_margin"] = _profile_level(row["margin_profit"], reference["margin_profit"])
        row["level_tenaga_kerja"] = _profile_level(row["tenaga_kerja"], reference["tenaga_kerja"])
        row["level_aset"] = _profile_level(row["barang_tetap"], reference["barang_tetap"])
        row["level_tekanan_biaya"] = _profile_level(row["tekanan_biaya_terpilih"], reference["tekanan_biaya_terpilih"])
        typology, policy = _classify_policy(cluster, row)
        size = int(counts.get(cluster, 0))
        rows.append({
            "cluster": cluster,
            "jumlah_usaha": size,
            "persentase": round(size / total * 100, 1) if total else 0,
            "tipologi_usaha": typology,
            "arah_kebijakan": policy,
            "penjualan_tahunan": float(row["penjualan_tahunan"]),
            "margin_profit": float(row["margin_profit"]),
            "tenaga_kerja": float(row["tenaga_kerja"]),
            "barang_tetap": float(row["barang_tetap"]),
            "rasio_bahan_baku": float(row["rasio_bahan_baku"]),
            "rasio_utilitas": float(row["rasio_utilitas"]),
            "rasio_penggajian": float(row["rasio_penggajian"]),
            "tekanan_biaya_terpilih": float(row["tekanan_biaya_terpilih"]),
        })
    return rows


def _prepare(raw: pd.DataFrame, path: Path, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    df = _normalise_frame(raw)
    if "survey_response_id" not in df:
        df["survey_response_id"] = np.arange(1, len(df) + 1, dtype=int)
    if "survey_row_number" not in df:
        df["survey_row_number"] = np.arange(2, len(df) + 2, dtype=int)

    df["biaya_bahan_baku"] = df["bahan_baku_utama"].fillna(0) + df["bahan_baku_tambahan"].fillna(0)
    df["biaya_utilitas"] = df["bahan_bakar"].fillna(0) + df["listrik"].fillna(0) + df["air"].fillna(0)
    df["gaji_tahunan"] = df["gaji_karyawan_bulanan"].fillna(0) * 12
    valid_sales = df["penjualan_tahunan"] > 0
    df["margin_profit"] = np.where(valid_sales, df["profit"] / df["penjualan_tahunan"], np.nan)
    df["log_penjualan"] = np.log1p(df["penjualan_tahunan"])
    df["log_tenaga_kerja"] = np.log1p(df["tenaga_kerja"])
    df["log_barang_tetap"] = np.log1p(df["barang_tetap"])
    df["rasio_bahan_baku"] = np.where(valid_sales, df["biaya_bahan_baku"] / df["penjualan_tahunan"], np.nan)
    df["rasio_utilitas"] = np.where(valid_sales, df["biaya_utilitas"] / df["penjualan_tahunan"], np.nan)
    df["rasio_penggajian"] = np.where(valid_sales, df["gaji_tahunan"] / df["penjualan_tahunan"], np.nan)
    df["rasio_barang_tetap"] = np.where(valid_sales, df["barang_tetap"].fillna(0) / df["penjualan_tahunan"], np.nan)
    df["tekanan_biaya_terpilih"] = df[["rasio_bahan_baku", "rasio_utilitas", "rasio_penggajian"]].sum(axis=1, min_count=1)

    model_df = df.dropna(subset=MODEL_FEATURES).copy()
    if model_df.empty:
        raise ValueError("Tidak ada observasi survei yang lengkap untuk 7 fitur model.")

    scaler = RobustScaler()
    X = scaler.fit_transform(model_df[MODEL_FEATURES].to_numpy(dtype=float))
    labels = DBSCAN(eps=FINAL_EPS, min_samples=FINAL_MIN_SAMPLES).fit_predict(X)
    model_df["cluster_id"] = labels
    model_df["cluster"] = np.where(labels == -1, "Noise", "Cluster " + labels.astype(str))

    cluster_order = [f"Cluster {cluster}" for cluster in sorted(set(labels) - {-1})]
    if -1 in labels:
        cluster_order.append("Noise")

    pca = PCA(n_components=2)
    coordinates = pca.fit_transform(X)
    model_df["pc1"] = coordinates[:, 0]
    model_df["pc2"] = coordinates[:, 1]
    non_noise = labels != -1
    n_clusters = len(set(labels) - {-1})
    silhouette = float(silhouette_score(X[non_noise], labels[non_noise])) if n_clusters >= 2 else None

    return {
        "df": df,
        "model_df": model_df,
        "cluster_order": cluster_order,
        "profiles": _build_profiles(model_df, model_df, cluster_order),
        "silhouette": silhouette,
        "pca_explained": [float(value) for value in pca.explained_variance_ratio_],
        "source_path": metadata.get("source_path", str(path)),
        "source_name": metadata.get("source_filename", path.name),
        "sheet_name": metadata.get("source_sheet", SURVEY_SHEET_NAME),
        "source_rows": int(len(df)),
        "model_rows": int(len(model_df)),
        "period_id": int(metadata["id"]) if metadata.get("id") is not None else None,
        "survey_year": int(metadata["survey_year"]) if metadata.get("survey_year") is not None else None,
        "survey_label": metadata.get("label"),
    }


def _period_payload(row) -> dict:
    analysis_meta = row.get("analysis_meta_json")
    try:
        analysis_meta = json.loads(analysis_meta) if analysis_meta else {}
    except (TypeError, json.JSONDecodeError):
        analysis_meta = {}
    return {
        "id": int(row["id"]),
        "survey_year": int(row["survey_year"]),
        "label": row["label"],
        "source_filename": row["source_filename"],
        "source_sheet": row["source_sheet"],
        "status": row["status"],
        "rows": int(row["total_rows"]),
        "valid_rows": int(row["valid_rows"]),
        "created_at": row["created_at"],
        "analysis_status": row.get("analysis_status") or "pending",
        "analysis_version": row.get("analysis_version"),
        "analysis_meta": analysis_meta,
        "analysis_completed_at": row.get("analysis_completed_at"),
        "analysis_error": row.get("analysis_error"),
    }


def load_survey_periods() -> list[dict]:
    """Return active periods newest-first without loading survey rows."""
    from utils.database import connection

    with connection() as conn:
        rows = conn.execute(
            """SELECT id, survey_year, label, source_filename, source_sheet,
                      file_sha256, status, total_rows, valid_rows, created_at,
                      analysis_status, analysis_version, analysis_meta_json,
                      analysis_completed_at, analysis_error
               FROM survey_periods
               WHERE status = 'active'
               ORDER BY survey_year DESC, id DESC"""
        ).fetchall()
    return [_period_payload(row) for row in rows]


def invalidate_survey_cache(period_id: int | None = None) -> None:
    with _cache_lock:
        if period_id is None:
            _cache.clear()
        else:
            _cache.pop(int(period_id), None)


def _analysis_meta(prepared: dict) -> dict:
    return {
        "name": "7 fitur + RobustScaler + DBSCAN",
        "eps": FINAL_EPS,
        "min_samples": FINAL_MIN_SAMPLES,
        "silhouette": prepared["silhouette"],
        "pca_explained": prepared["pca_explained"],
    }


def _analysis_records(prepared: dict, response_rows) -> list[dict]:
    response_by_row = {
        int(row["row_number"]): int(row["id"])
        for row in response_rows
    }
    modeled_by_row = {
        int(row["survey_row_number"]): row
        for _, row in prepared["model_df"].iterrows()
    }

    records = []
    for _, source in prepared["df"].iterrows():
        row_number = int(source["survey_row_number"])
        response_id = response_by_row.get(row_number)
        if response_id is None:
            raise ValueError(f"Respons survei untuk baris {row_number} tidak ditemukan.")

        model = modeled_by_row.get(row_number)
        if model is None:
            cluster_id = None
            cluster_label = "Tidak terpetakan"
            status = "Data tidak lengkap"
        else:
            cluster_id = int(model["cluster_id"])
            cluster_label = str(model["cluster"])
            status = "Noise" if cluster_id == -1 else "Terpetakan"

        records.append({
            "response_id": response_id,
            "row_number": row_number,
            "nama_usaha": _json_scalar(source.get("nama_usaha")),
            "subsektor": _json_scalar(source.get("subsektor_ringkas")),
            "klasifikasi_umkm": _json_scalar(source.get("klasifikasi_umkm")),
            "kecamatan": _json_scalar(source.get("kecamatan")),
            "kelurahan": _json_scalar(source.get("kelurahan")),
            "cluster_id": cluster_id,
            "cluster_label": cluster_label,
            "status": status,
            "pc1": _json_scalar(model.get("pc1")) if model is not None else None,
            "pc2": _json_scalar(model.get("pc2")) if model is not None else None,
            "penjualan_tahunan": _json_scalar(model.get("penjualan_tahunan")) if model is not None else None,
            "margin_profit": _json_scalar(model.get("margin_profit")) if model is not None else None,
            "tenaga_kerja": _json_scalar(model.get("tenaga_kerja")) if model is not None else None,
            "barang_tetap": _json_scalar(model.get("barang_tetap")) if model is not None else None,
            "rasio_barang_tetap": _json_scalar(model.get("rasio_barang_tetap")) if model is not None else None,
            "rasio_bahan_baku": _json_scalar(model.get("rasio_bahan_baku")) if model is not None else None,
            "rasio_utilitas": _json_scalar(model.get("rasio_utilitas")) if model is not None else None,
            "rasio_penggajian": _json_scalar(model.get("rasio_penggajian")) if model is not None else None,
            "tekanan_biaya_terpilih": _json_scalar(model.get("tekanan_biaya_terpilih")) if model is not None else None,
        })
    return records


def _persist_analysis_results(conn, period_id: int, prepared: dict, response_rows, now: str) -> None:
    records = _analysis_records(prepared, response_rows)
    conn.execute("DELETE FROM survey_analysis_results WHERE period_id = %s", (period_id,))
    with conn.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO survey_analysis_results
               (period_id, response_id, row_number, nama_usaha, subsektor,
                klasifikasi_umkm, kecamatan, kelurahan, cluster_id, cluster_label,
                status, pc1, pc2, penjualan_tahunan, margin_profit, tenaga_kerja,
                barang_tetap, rasio_barang_tetap, rasio_bahan_baku, rasio_utilitas, rasio_penggajian,
                tekanan_biaya_terpilih, analysis_version, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    period_id,
                    record["response_id"],
                    record["row_number"],
                    record["nama_usaha"],
                    record["subsektor"],
                    record["klasifikasi_umkm"],
                    record["kecamatan"],
                    record["kelurahan"],
                    record["cluster_id"],
                    record["cluster_label"],
                    record["status"],
                    record["pc1"],
                    record["pc2"],
                    record["penjualan_tahunan"],
                    record["margin_profit"],
                    record["tenaga_kerja"],
                    record["barang_tetap"],
                    record["rasio_barang_tetap"],
                    record["rasio_bahan_baku"],
                    record["rasio_utilitas"],
                    record["rasio_penggajian"],
                    record["tekanan_biaya_terpilih"],
                    ANALYSIS_VERSION,
                    now,
                )
                for record in records
            ],
        )

    conn.execute(
        """UPDATE survey_periods
           SET analysis_status = 'ready', analysis_version = %s,
               analysis_meta_json = %s, analysis_completed_at = %s,
               analysis_error = NULL, updated_at = %s
           WHERE id = %s""",
        (
            ANALYSIS_VERSION,
            json.dumps(_analysis_meta(prepared), ensure_ascii=False),
            now,
            now,
            period_id,
        ),
    )


def get_survey_period(survey_year: int) -> dict:
    period = next(
        (item for item in load_survey_periods() if item["survey_year"] == int(survey_year)),
        None,
    )
    if period is None:
        raise LookupError(f"Periode survei tahun {survey_year} tidak ditemukan.")
    return period


def ensure_survey_analysis(period_id: int) -> dict:
    """Backfill one legacy period once, then return its metadata."""
    period = next(
        (item for item in load_survey_periods() if item["id"] == int(period_id)),
        None,
    )
    if period is None:
        raise LookupError("Periode survei tidak ditemukan.")
    if (
        period["analysis_status"] == "ready"
        and period.get("analysis_version") == ANALYSIS_VERSION
    ):
        return period
    if period["analysis_status"] == "failed":
        detail = period.get("analysis_error") or "alasan tidak tersedia"
        raise LookupError(f"Analisis periode {period['survey_year']} gagal: {detail}")

    try:
        from utils.database import transaction, utcnow

        with transaction() as conn:
            current = conn.execute(
                """SELECT id, survey_year, analysis_status, analysis_version, analysis_error FROM survey_periods
                   WHERE id = %s FOR UPDATE""",
                (period_id,),
            ).fetchone()
            if current is None:
                raise LookupError("Periode survei tidak ditemukan.")
            if (
                current["analysis_status"] == "ready"
                and current["analysis_version"] == ANALYSIS_VERSION
            ):
                pass
            elif current["analysis_status"] == "failed":
                raise LookupError(
                    f"Analisis periode {current['survey_year']} gagal: "
                    f"{current['analysis_error'] or 'alasan tidak tersedia'}"
                )
            else:
                # Keep the row lock while building the legacy result so a
                # parallel summary/actors request cannot run the model twice.
                prepared = load_survey_data(period_id)
                response_rows = conn.execute(
                    """SELECT id, row_number FROM survey_responses
                       WHERE period_id = %s ORDER BY row_number""",
                    (period_id,),
                ).fetchall()
                _persist_analysis_results(conn, period_id, prepared, response_rows, utcnow())
        return get_survey_period(period["survey_year"])
    except Exception as error:
        from utils.database import transaction, utcnow

        with transaction() as conn:
            conn.execute(
                """UPDATE survey_periods
                   SET analysis_status = 'failed', analysis_error = %s, updated_at = %s
                   WHERE id = %s AND analysis_status <> 'ready'""",
                (str(error)[:1000], utcnow(), period_id),
            )
        raise


def load_analysis_dataframe(period_id: int, cluster: str = "") -> pd.DataFrame:
    from utils.database import connection

    query = """SELECT response_id, row_number, nama_usaha, subsektor,
                      klasifikasi_umkm, kecamatan, kelurahan, cluster_id,
                      cluster_label, status, pc1, pc2, penjualan_tahunan,
                      margin_profit, tenaga_kerja, barang_tetap, rasio_barang_tetap,
                      rasio_bahan_baku, rasio_utilitas, rasio_penggajian,
                      tekanan_biaya_terpilih
               FROM survey_analysis_results
               WHERE period_id = %s"""
    params: list = [period_id]
    if cluster:
        query += " AND cluster_label = %s"
        params.append(cluster)
    query += " ORDER BY row_number"

    with connection() as conn:
        rows = conn.execute(query, params).fetchall()
    if not rows:
        return pd.DataFrame(columns=[
            "survey_response_id", "survey_row_number", "nama_usaha", "subsektor_ringkas",
            "klasifikasi_umkm", "kecamatan", "kelurahan", "cluster_id", "cluster",
            "status", "pc1", "pc2", "penjualan_tahunan", "margin_profit", "tenaga_kerja",
            "barang_tetap", "rasio_barang_tetap", "rasio_bahan_baku", "rasio_utilitas", "rasio_penggajian",
            "tekanan_biaya_terpilih",
        ])

    frame = pd.DataFrame([dict(row) for row in rows])
    return frame.rename(columns={
        "response_id": "survey_response_id",
        "row_number": "survey_row_number",
        "subsektor": "subsektor_ringkas",
        "cluster_label": "cluster",
    })


def load_analysis_page(
    period_id: int,
    *,
    cluster: str = "",
    page: int = 1,
    per_page: int = 50,
) -> dict:
    from utils.database import connection

    page = max(1, int(page))
    per_page = min(50, max(1, int(per_page)))
    where = "WHERE period_id = %s"
    params: list = [period_id]
    if cluster:
        where += " AND cluster_label = %s"
        params.append(cluster)

    with connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM survey_analysis_results {where}", params
        ).fetchone()["total"]
        total = int(total)
        pages = (total + per_page - 1) // per_page if total else 0
        page = min(page, pages) if pages else 1
        rows = conn.execute(
            f"""SELECT response_id, row_number, nama_usaha, subsektor,
                       klasifikasi_umkm, kecamatan, kelurahan,
                       cluster_id, cluster_label, status, penjualan_tahunan,
                       margin_profit, tenaga_kerja
                FROM survey_analysis_results {where}
                ORDER BY row_number LIMIT %s OFFSET %s""",
            [*params, per_page, (page - 1) * per_page],
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        item["cluster"] = item.pop("cluster_label")
        item["response_id"] = int(item["response_id"])
        items.append(item)
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }


def import_survey_period(
    raw: pd.DataFrame,
    *,
    survey_year: int,
    label: str,
    source_filename: str,
    source_sheet: str,
    file_sha256: str,
    user_id: int | None = None,
) -> dict:
    """Validate and atomically store one survey year in the database."""
    try:
        survey_year = int(survey_year)
    except (TypeError, ValueError) as error:
        raise ValueError("Tahun survei harus berupa angka.") from error
    if not 2000 <= survey_year <= 2100:
        raise ValueError("Tahun survei harus berada pada rentang 2000–2100.")
    if not file_sha256:
        raise ValueError("Hash file survei tidak tersedia.")

    source_filename = Path(str(source_filename or f"survey-{survey_year}.xlsx")).name
    source_sheet = str(source_sheet or SURVEY_SHEET_NAME).strip() or SURVEY_SHEET_NAME
    label = str(label or f"Survei Tahunan Ekraf {survey_year}").strip()
    if not label:
        label = f"Survei Tahunan Ekraf {survey_year}"

    normalised, records = _storage_records(raw)
    if not records:
        raise ValueError("File survei tidak berisi baris data.")
    prepared = _prepare(
        normalised,
        Path(source_filename),
        metadata={"source_filename": source_filename, "source_sheet": source_sheet},
    )

    from utils.database import transaction, utcnow

    with transaction() as conn:
        existing = conn.execute(
            """SELECT id, survey_year, file_sha256 FROM survey_periods
               WHERE survey_year = %s OR file_sha256 = %s
               LIMIT 1""",
            (survey_year, file_sha256),
        ).fetchone()
        if existing:
            if int(existing["survey_year"]) == survey_year:
                raise SurveyPeriodExistsError(
                    f"Periode survei tahun {survey_year} sudah tersimpan."
                )
            raise SurveyPeriodExistsError("File survei yang sama sudah tersimpan pada periode lain.")

        now = utcnow()
        period = conn.execute(
            """INSERT INTO survey_periods
               (survey_year, label, source_filename, source_sheet, file_sha256,
                status, total_rows, valid_rows, created_at, created_by)
               VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s)
               RETURNING id, survey_year, label, source_filename, source_sheet,
                         file_sha256, status, total_rows, valid_rows, created_at""",
            (
                survey_year,
                label,
                source_filename,
                source_sheet,
                file_sha256,
                len(records),
                prepared["model_rows"],
                now,
                user_id,
            ),
        ).fetchone()
        period_id = int(period["id"])
        with conn.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO survey_responses
                   (period_id, row_number, data_json, created_at, created_by)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (
                        period_id,
                        index,
                        json.dumps(record, ensure_ascii=False, default=str),
                        now,
                        user_id,
                    )
                    for index, record in enumerate(records, start=2)
                ],
            )
        response_rows = conn.execute(
            """SELECT id, row_number FROM survey_responses
               WHERE period_id = %s ORDER BY row_number""",
            (period_id,),
        ).fetchall()
        _persist_analysis_results(conn, period_id, prepared, response_rows, now)
        period = conn.execute(
            """SELECT id, survey_year, label, source_filename, source_sheet,
                      file_sha256, status, total_rows, valid_rows, created_at,
                      analysis_status, analysis_version, analysis_meta_json,
                      analysis_completed_at, analysis_error
               FROM survey_periods WHERE id = %s""",
            (period_id,),
        ).fetchone()

    invalidate_survey_cache(period_id)
    return _period_payload(period)


def load_survey_data(period_id: int | None = None) -> dict:
    """Load exactly one survey period from the database and cache its analysis."""
    from utils.database import connection

    periods = load_survey_periods()
    if not periods:
        raise LookupError("Belum ada periode survei yang tersimpan di database.")
    if period_id is None:
        period = periods[0]
    else:
        try:
            requested_id = int(period_id)
        except (TypeError, ValueError) as error:
            raise LookupError("Periode survei tidak valid.") from error
        period = next((item for item in periods if item["id"] == requested_id), None)
        if period is None:
            raise LookupError("Periode survei tidak ditemukan.")

    selected_id = period["id"]
    with _cache_lock:
        cached = _cache.get(selected_id)
    if cached is not None:
        return cached

    with connection() as conn:
        rows = conn.execute(
            """SELECT id, row_number, data_json FROM survey_responses
               WHERE period_id = %s ORDER BY row_number""",
            (selected_id,),
        ).fetchall()
    if not rows:
        raise LookupError("Periode survei tidak memiliki baris jawaban.")

    records = []
    for row in rows:
        record = json.loads(row["data_json"])
        record["survey_response_id"] = int(row["id"])
        record["survey_row_number"] = int(row["row_number"])
        records.append(record)
    raw = pd.DataFrame(records)
    prepared = _prepare(
        raw,
        Path(period["source_filename"]),
        metadata={
            **period,
            "source_path": f"database://survey-period/{selected_id}",
        },
    )
    with _cache_lock:
        _cache[selected_id] = prepared
    return prepared


def prepare_survey_frame(
    raw: pd.DataFrame,
    *,
    source_name: str = "survey.xlsx",
    sheet_name: str = SURVEY_SHEET_NAME,
) -> dict:
    """Prepare a frame without persistence; useful for validation and scripts."""
    return _prepare(
        raw,
        Path(source_name),
        metadata={"source_filename": Path(source_name).name, "source_sheet": sheet_name},
    )


def filter_survey_data(
    df: pd.DataFrame,
    *,
    kecamatan: str = "",
    subsektor: str = "",
    klasifikasi_umkm: str = "",
    cluster: str = "",
) -> pd.DataFrame:
    """Filter survey rows without changing the cached source frame."""
    filtered = df
    if kecamatan:
        filtered = filtered[filtered["kecamatan"] == kecamatan]
    if subsektor:
        filtered = filtered[filtered["subsektor_ringkas"] == subsektor]
    if klasifikasi_umkm:
        filtered = filtered[filtered["klasifikasi_umkm"] == klasifikasi_umkm]
    if cluster and "cluster" in filtered.columns:
        filtered = filtered[filtered["cluster"] == cluster]
    return filtered.copy()

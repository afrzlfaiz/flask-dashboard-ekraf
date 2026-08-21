"""API endpoints for the annual Ekraf survey panel."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pandas as pd
from flask import current_app, g, jsonify, request
from flask_login import current_user

from api import api_bp
from api.upload import _valid_xlsx_container
from auth import role_required
from config import ALLOWED_UPLOAD_MIMES, MAX_UPLOAD_ROWS, MAX_UPLOAD_SIZE_MB, SURVEY_SHEET_NAME
from utils.database import record_audit, transaction
from utils.survey_loader import (
    FINAL_EPS,
    FINAL_MIN_SAMPLES,
    SurveyPeriodExistsError,
    _build_profiles,
    filter_survey_data,
    import_survey_period,
    load_survey_periods,
    load_survey_data,
)


def _error_response(error: Exception):
    if isinstance(error, ValueError):
        return jsonify({"success": False, "message": str(error)}), 400
    if isinstance(error, LookupError):
        message = str(error)
        status = 404 if "tidak ditemukan" in message.lower() else 503
        return jsonify({"success": False, "message": message}), status
    current_app.logger.exception("Survey API error")
    return jsonify({
        "success": False,
        "message": "Data survei belum dapat dimuat. Periksa konfigurasi database atau hubungi administrator.",
    }), 500


def _filters():
    return {
        "kecamatan": request.args.get("kecamatan", "").strip(),
        "subsektor": request.args.get("subsektor", "").strip(),
        "klasifikasi_umkm": request.args.get("klasifikasi_umkm", "").strip(),
        "cluster": request.args.get("cluster", "").strip(),
    }


def _period_id_arg():
    value = request.args.get("period_id", "").strip()
    if not value:
        return None
    try:
        period_id = int(value)
    except ValueError as error:
        raise ValueError("ID periode survei tidak valid.") from error
    if period_id <= 0:
        raise ValueError("ID periode survei tidak valid.")
    return period_id


def _distribution(series: pd.Series, limit: int | None = None) -> dict:
    counts = series.dropna().value_counts()
    if limit:
        counts = counts.head(limit)
    return {"labels": [str(value) for value in counts.index], "values": [int(value) for value in counts.values]}


def _kecamatan_summary(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    grouped = df.groupby("kecamatan", dropna=True).agg(
        jumlah_usaha=("kecamatan", "size"),
        total_penjualan=("penjualan_tahunan", "sum"),
        median_margin=("margin_profit", "median"),
        total_tenaga_kerja=("tenaga_kerja", "sum"),
    ).sort_values("jumlah_usaha", ascending=False)
    return [
        {
            "kecamatan": str(index),
            "jumlah_usaha": int(row["jumlah_usaha"]),
            "total_penjualan": float(row["total_penjualan"]),
            "median_margin": float(row["median_margin"]),
            "total_tenaga_kerja": float(row["total_tenaga_kerja"]),
        }
        for index, row in grouped.iterrows()
    ]


def _text_value(value, fallback="—") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    return str(value)


def _number_value(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _actor_rows(source: pd.DataFrame, modeled: pd.DataFrame) -> list[dict]:
    """Return one cluster result per surveyed actor for the selected period."""
    model_by_id = {}
    for _, row in modeled.iterrows():
        response_id = _number_value(row.get("survey_response_id"))
        if response_id is not None:
            model_by_id[int(response_id)] = row

    actors = []
    for _, row in source.iterrows():
        response_id = _number_value(row.get("survey_response_id"))
        response_key = int(response_id) if response_id is not None else None
        model = model_by_id.get(response_key)
        cluster = _text_value(model.get("cluster")) if model is not None else "Tidak terpetakan"
        cluster_id = int(model["cluster_id"]) if model is not None and _number_value(model.get("cluster_id")) is not None else None
        status = "Noise" if cluster == "Noise" else ("Terpetakan" if model is not None else "Data tidak lengkap")
        actors.append({
            "response_id": response_key,
            "row_number": int(_number_value(row.get("survey_row_number")) or 0),
            "nama_usaha": _text_value(row.get("nama_usaha")),
            "subsektor": _text_value(row.get("subsektor_ringkas")),
            "kecamatan": _text_value(row.get("kecamatan")),
            "kelurahan": _text_value(row.get("kelurahan")),
            "klasifikasi_umkm": _text_value(row.get("klasifikasi_umkm")),
            "cluster": cluster,
            "cluster_id": cluster_id,
            "status": status,
            "penjualan_tahunan": _number_value(model.get("penjualan_tahunan")) if model is not None else None,
            "margin_profit": _number_value(model.get("margin_profit")) if model is not None else None,
            "tenaga_kerja": _number_value(model.get("tenaga_kerja")) if model is not None else None,
        })
    return actors


def _summary(bundle: dict, filtered: pd.DataFrame, source_filtered: pd.DataFrame) -> dict:
    cluster_order = bundle["cluster_order"]
    labels = filtered["cluster"].value_counts().reindex(cluster_order, fill_value=0)
    non_noise = [label for label in cluster_order if label != "Noise"]
    profiles = _build_profiles(filtered, bundle["model_df"], cluster_order)
    points = [
        {"x": round(float(row["pc1"]), 5), "y": round(float(row["pc2"]), 5), "cluster": str(row["cluster"])}
        for _, row in filtered.iterrows()
    ]
    return {
        "success": True,
        "source": {
            "period_id": bundle["period_id"],
            "year": bundle["survey_year"],
            "label": bundle["survey_label"],
            "file": Path(bundle["source_name"]).name,
            "sheet": bundle["sheet_name"],
            "rows": bundle["source_rows"],
            "model_rows": bundle["model_rows"],
        },
        "filters": {
            "total_rows": int(len(filtered)),
        },
        "kpi": {
            "total_observasi": int(len(filtered)),
            "total_penjualan": float(filtered["penjualan_tahunan"].sum()),
            "median_margin": float(filtered["margin_profit"].median()) if not filtered.empty else 0,
            "total_tenaga_kerja": float(filtered["tenaga_kerja"].sum()),
            "usaha_tercluster": int(filtered["cluster"].isin(non_noise).sum()),
            "noise": int((filtered["cluster"] == "Noise").sum()),
        },
        "model": {
            "name": "7 fitur + RobustScaler",
            "eps": FINAL_EPS,
            "min_samples": FINAL_MIN_SAMPLES,
            "n_clusters": int(sum(int(labels.get(label, 0) > 0) for label in non_noise)),
            "silhouette": bundle["silhouette"],
            "noise_percent": round(float(labels.get("Noise", 0)) / len(filtered) * 100, 2) if len(filtered) else 0,
            "pca_explained": bundle["pca_explained"],
        },
        "charts": {
            "cluster": {"labels": list(labels.index), "values": [int(value) for value in labels.values]},
            "subsektor": _distribution(filtered["subsektor_ringkas"]),
            "kecamatan": _distribution(filtered["kecamatan"]),
            "umkm": _distribution(filtered["klasifikasi_umkm"]),
        },
        "profiles": profiles,
        "actors": _actor_rows(source_filtered, filtered),
        "kecamatan_summary": _kecamatan_summary(filtered),
        "pca": points,
    }


@api_bp.route("/survey/periods")
@role_required("admin")
def survey_periods():
    try:
        periods = load_survey_periods()
        return jsonify({
            "success": True,
            "periods": periods,
            "default_period_id": periods[0]["id"] if periods else None,
        })
    except Exception as error:
        return _error_response(error)


@api_bp.route("/survey/options")
@role_required("admin")
def survey_options():
    try:
        periods = load_survey_periods()
        bundle = load_survey_data(_period_id_arg())
        df = bundle["model_df"]
        return jsonify({
            "success": True,
            "periods": periods,
            "default_period_id": periods[0]["id"] if periods else None,
            "selected_period_id": bundle["period_id"],
            "options": {
                "kecamatan": sorted(df["kecamatan"].dropna().unique().tolist()),
                "subsektor": sorted(df["subsektor_ringkas"].dropna().unique().tolist()),
                "klasifikasi_umkm": sorted(df["klasifikasi_umkm"].dropna().unique().tolist()),
                "cluster": [cluster for cluster in bundle["cluster_order"] if cluster in set(df["cluster"].dropna())],
            },
            "source": {
                "period_id": bundle["period_id"],
                "year": bundle["survey_year"],
                "label": bundle["survey_label"],
                "file": bundle["source_name"],
                "sheet": bundle["sheet_name"],
                "rows": bundle["source_rows"],
            },
        })
    except Exception as error:
        return _error_response(error)


@api_bp.route("/survey/summary")
@role_required("admin")
def survey_summary():
    try:
        bundle = load_survey_data(_period_id_arg())
        filters = _filters()
        filtered = filter_survey_data(bundle["model_df"], **filters)
        source_filters = {key: value for key, value in filters.items() if key != "cluster"}
        source_filtered = filter_survey_data(bundle["df"], **source_filters)
        if filters["cluster"]:
            response_ids = set(filtered["survey_response_id"].dropna().astype(int))
            source_filtered = source_filtered[source_filtered["survey_response_id"].isin(response_ids)]
        return jsonify(_summary(bundle, filtered, source_filtered))
    except Exception as error:
        return _error_response(error)


@api_bp.route("/survey/import", methods=["POST"])
@role_required("admin")
def survey_import():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "Tidak ada file survei yang diunggah."}), 400

    file = request.files["file"]
    filename = (file.filename or "").strip()
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension != ".xlsx":
        return jsonify({"success": False, "message": "Hanya file .xlsx yang diterima untuk survei."}), 400
    if file.mimetype not in ALLOWED_UPLOAD_MIMES:
        return jsonify({"success": False, "message": "MIME type file tidak sesuai format XLSX."}), 400

    try:
        survey_year = int((request.form.get("survey_year") or "").strip())
    except ValueError:
        return jsonify({"success": False, "message": "Tahun survei wajib berupa angka."}), 422
    sheet_name = (request.form.get("sheet_name") or SURVEY_SHEET_NAME).strip() or SURVEY_SHEET_NAME
    label = (request.form.get("label") or f"Survei Tahunan Ekraf {survey_year}").strip()

    raw_bytes = file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return jsonify({"success": False, "message": f"Ukuran file melebihi {MAX_UPLOAD_SIZE_MB} MB."}), 413
    if not raw_bytes.startswith(b"PK\x03\x04") or not _valid_xlsx_container(raw_bytes):
        return jsonify({"success": False, "message": "Isi file bukan dokumen XLSX yang valid."}), 422

    try:
        dataframe = pd.read_excel(BytesIO(raw_bytes), sheet_name=sheet_name, engine="openpyxl")
    except ValueError:
        return jsonify({"success": False, "message": f"Sheet survei '{sheet_name}' tidak ditemukan."}), 422
    except Exception:
        return jsonify({"success": False, "message": "File XLSX rusak atau tidak dapat dibaca."}), 422
    if dataframe.empty:
        return jsonify({"success": False, "message": "File survei tidak berisi data."}), 422
    if len(dataframe) > MAX_UPLOAD_ROWS:
        return jsonify({
            "success": False,
            "message": f"Jumlah baris survei melebihi batas {MAX_UPLOAD_ROWS}.",
        }), 422

    digest = hashlib.sha256(raw_bytes).hexdigest()
    try:
        period = import_survey_period(
            dataframe,
            survey_year=survey_year,
            label=label,
            source_filename=filename,
            source_sheet=sheet_name,
            file_sha256=digest,
            user_id=int(current_user.id),
        )
    except SurveyPeriodExistsError as error:
        return jsonify({"success": False, "message": str(error)}), 409
    except ValueError as error:
        return jsonify({"success": False, "message": str(error)}), 422
    except Exception:
        current_app.logger.exception("Survey period import failed")
        return jsonify({
            "success": False,
            "message": "Import periode survei gagal. Perubahan tidak disimpan.",
        }), 500

    with transaction() as conn:
        record_audit(
            conn,
            action="survey_period_import",
            entity="survey_period",
            entity_id=period["id"],
            user_id=current_user.id,
            new_value={
                "survey_year": period["survey_year"],
                "label": period["label"],
                "source_filename": period["source_filename"],
                "rows": period["rows"],
                "valid_rows": period["valid_rows"],
            },
            ip_address=request.remote_addr,
            request_id=getattr(g, "request_id", None),
        )

    return jsonify({
        "success": True,
        "message": f"Survei tahun {period['survey_year']} berhasil disimpan sebagai periode terpisah.",
        "period": period,
    }), 201

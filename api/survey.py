"""Lightweight, admin-only APIs for annual Ekraf survey periods."""
from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd
from flask import current_app, g, jsonify, request, send_file
from flask_login import current_user

from api import api_bp
from api.upload import _valid_xlsx_container
from auth import role_required
from config import ALLOWED_UPLOAD_MIMES, MAX_UPLOAD_ROWS, MAX_UPLOAD_SIZE_MB, SURVEY_SHEET_NAME
from utils.database import record_audit, transaction
from utils.survey_loader import (
    ANALYSIS_VERSION,
    FINAL_EPS,
    FINAL_MIN_SAMPLES,
    SurveyPeriodExistsError,
    _build_profiles,
    ensure_survey_analysis,
    get_survey_period,
    import_survey_period,
    load_analysis_dataframe,
    load_analysis_page,
    load_survey_periods,
    SURVEY_TEMPLATE_COLUMNS,
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


def _survey_template_file(fmt: str) -> tuple[BytesIO, str]:
    dataframe = pd.DataFrame(columns=SURVEY_TEMPLATE_COLUMNS)
    buffer = BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name=SURVEY_SHEET_NAME)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        buffer.write(dataframe.to_csv(index=False).encode("utf-8-sig"))
        mimetype = "text/csv"
    buffer.seek(0)
    return buffer, mimetype


def _cluster_arg() -> str:
    return request.args.get("cluster", "").strip()


def _page_arg(name: str, default: int, *, maximum: int | None = None) -> int:
    value = request.args.get(name, str(default)).strip()
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"Parameter {name} harus berupa angka.") from error
    if parsed < 1:
        raise ValueError(f"Parameter {name} harus lebih besar dari 0.")
    return min(parsed, maximum) if maximum else parsed


def _ready_period(survey_year: int) -> dict:
    period = get_survey_period(survey_year)
    status = period.get("analysis_status") or "pending"
    if status == "failed":
        detail = period.get("analysis_error") or "alasan tidak tersedia"
        raise LookupError(f"Analisis periode {survey_year} gagal: {detail}")
    if status != "ready" or period.get("analysis_version") != ANALYSIS_VERSION:
        period = ensure_survey_analysis(period["id"])
    if period.get("analysis_status") != "ready":
        raise LookupError(f"Analisis periode {survey_year} belum siap digunakan.")
    return period


def _cluster_order(frame: pd.DataFrame) -> list[str]:
    labels = {str(value) for value in frame.get("cluster", pd.Series(dtype=str)).dropna()}
    cluster_ids = []
    for label in labels:
        if label.startswith("Cluster "):
            try:
                cluster_ids.append((int(label.split(" ", 1)[1]), label))
            except ValueError:
                continue
    ordered = [label for _, label in sorted(cluster_ids)]
    if "Noise" in labels:
        ordered.append("Noise")
    return ordered


def _number(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _summary(period: dict, frame: pd.DataFrame, cluster: str) -> dict:
    modeled = frame[frame["status"].isin(["Terpetakan", "Noise"])].copy()
    order = _cluster_order(modeled)
    counts = modeled["cluster"].value_counts().reindex(order, fill_value=0)
    non_noise = [label for label in order if label != "Noise"]
    meta = period.get("analysis_meta") or {}
    total = len(modeled)

    kpi = {
        "total_observasi": int(total),
        "total_responses": int(len(frame)),
        "data_tidak_lengkap": int((frame["status"] == "Data tidak lengkap").sum()),
        "total_penjualan": _number(modeled["penjualan_tahunan"].sum()) if total else 0,
        "median_margin": _number(modeled["margin_profit"].median()) if total else 0,
        "total_tenaga_kerja": _number(modeled["tenaga_kerja"].sum()) if total else 0,
        "usaha_tercluster": int(modeled["cluster"].isin(non_noise).sum()),
        "noise": int((modeled["cluster"] == "Noise").sum()),
    }
    profiles = _build_profiles(modeled, modeled, order)
    return {
        "success": True,
        "source": {
            "period_id": period["id"],
            "year": period["survey_year"],
            "label": period["label"],
            "file": period["source_filename"],
            "sheet": period["source_sheet"],
            "rows": period["rows"],
            "valid_rows": period["valid_rows"],
            "model_rows": int(total),
        },
        "filters": {
            "cluster": cluster or None,
            "total_rows": int(len(frame)),
            "model_rows": int(total),
        },
        "kpi": kpi,
        "model": {
            "name": meta.get("name", "7 fitur + RobustScaler + DBSCAN"),
            "version": period.get("analysis_version") or ANALYSIS_VERSION,
            "eps": _number(meta.get("eps"), FINAL_EPS),
            "min_samples": int(meta.get("min_samples") or FINAL_MIN_SAMPLES),
            "n_clusters": int(sum(int(counts.get(label, 0) > 0) for label in non_noise)),
            "silhouette": meta.get("silhouette"),
            "noise_percent": round(kpi["noise"] / total * 100, 2) if total else 0,
            "pca_explained": meta.get("pca_explained") or [],
        },
        "charts": {
            "cluster": {
                "labels": list(counts.index),
                "values": [int(value) for value in counts.values],
            },
        },
        "profiles": profiles,
    }


@api_bp.route("/survey/template")
@role_required("admin")
def survey_template():
    fmt = request.args.get("format", "xlsx").lower()
    if fmt not in {"csv", "xlsx"}:
        return jsonify({"success": False, "message": "Format template harus csv atau xlsx."}), 400
    buffer, mimetype = _survey_template_file(fmt)
    return send_file(
        buffer,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"template-survei-ekraf.{fmt}",
    )


@api_bp.route("/survey/periods")
@role_required("admin")
def survey_periods():
    try:
        periods = load_survey_periods()
        for period in periods:
            period["url"] = f"/survei/periode-{period['survey_year']}"
        return jsonify({"success": True, "periods": periods})
    except Exception as error:
        return _error_response(error)


@api_bp.route("/survey/periods/<int:survey_year>/summary")
@role_required("admin")
def survey_period_summary(survey_year: int):
    try:
        period = _ready_period(survey_year)
        cluster = _cluster_arg()
        frame = load_analysis_dataframe(period["id"], cluster=cluster)
        return jsonify(_summary(period, frame, cluster))
    except Exception as error:
        return _error_response(error)


@api_bp.route("/survey/periods/<int:survey_year>/actors")
@role_required("admin")
def survey_period_actors(survey_year: int):
    try:
        period = _ready_period(survey_year)
        cluster = _cluster_arg()
        page = _page_arg("page", 1)
        per_page = _page_arg("per_page", 50, maximum=50)
        result = load_analysis_page(
            period["id"], cluster=cluster, page=page, per_page=per_page
        )
        return jsonify({"success": True, "period": period, **result})
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
                "analysis_status": period["analysis_status"],
            },
            ip_address=request.remote_addr,
            request_id=getattr(g, "request_id", None),
        )

    return jsonify({
        "success": True,
        "message": f"Survei tahun {period['survey_year']} berhasil disimpan sebagai periode terpisah.",
        "period": period,
    }), 201

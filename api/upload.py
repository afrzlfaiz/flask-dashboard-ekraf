"""Staged XLSX import, preview/commit/rollback, error report, and protected export."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import uuid
from io import BytesIO, StringIO
from zipfile import BadZipFile, ZipFile

import pandas as pd
from flask import g, jsonify, request, send_file
from flask_login import current_user

from api import api_bp
from api.crud import validate_actor_payload
from auth import role_required
from config import (
    ALLOWED_UPLOAD_MIMES,
    DB_PATH,
    MAX_UPLOAD_ROWS,
    MAX_UPLOAD_UNCOMPRESSED_MB,
)
from utils.backup import create_backup
from utils.data_loader import load_data
from utils.database import connect_db, record_audit, transaction, utcnow
from utils.filtering import apply_filters

ALLOWED_EXTENSIONS = {".xlsx"}
REQUIRED_COLUMNS = ["Nama Narasumber", "Nama Usaha", "Alamat", "Kecamatan", "Kelurahan", "Sub Sektor", "lat", "lon"]
BUSINESS_COLUMNS = [
    "Nama Narasumber", "Nama Usaha", "Alamat", "Kecamatan", "Kelurahan",
    "No Telp", "Sub Sektor", "Kategori Usaha", "Tahun Berdiri", "Email", "lat", "lon",
]


def _audit_context():
    return {
        "user_id": int(current_user.id),
        "ip_address": request.remote_addr,
        "request_id": getattr(g, "request_id", None),
    }


def _normalize_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _dedup_key(data: dict) -> tuple[str, str, str]:
    business_name = data.get("Nama Usaha") or data.get("Nama Narasumber")
    phone = re.sub(r"\D", "", str(data.get("No Telp") or ""))
    return (
        _normalize_text(business_name),
        _normalize_text(data.get("Sub Sektor")),
        phone,
    )


def _clean_excel_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def _valid_xlsx_container(raw: bytes) -> bool:
    """Reject malformed/oversized ZIP containers before openpyxl expands them."""
    try:
        with ZipFile(BytesIO(raw)) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            total_uncompressed = sum(member.file_size for member in members)
            return (
                len(members) <= 10_000
                and total_uncompressed <= MAX_UPLOAD_UNCOMPRESSED_MB * 1024 * 1024
                and {"[Content_Types].xml", "xl/workbook.xml"} <= names
            )
    except (BadZipFile, OSError):
        return False


def _spreadsheet_safe(value):
    """Neutralize spreadsheet formulas in exported user-controlled text."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _batch_access(conn, batch_id: str):
    batch = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
    if not batch:
        return None, (jsonify({"success": False, "message": "Batch import tidak ditemukan."}), 404)
    if int(batch["uploaded_by"]) != int(current_user.id) and not current_user.has_role("validator"):
        return None, (jsonify({"success": False, "message": "Anda tidak memiliki akses ke batch ini."}), 403)
    return batch, None


def _serialize_batch(batch) -> dict:
    return {
        "id": batch["id"],
        "filename": batch["filename"],
        "status": batch["status"],
        "total": batch["total_rows"],
        "valid": batch["valid_rows"],
        "errors": batch["error_rows"],
        "duplicates": batch["duplicate_rows"],
        "created_at": batch["created_at"],
        "committed_at": batch["committed_at"],
        "rolled_back_at": batch["rolled_back_at"],
    }


def _preview_rows(conn, batch_id: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT row_number, data_json, validation_status, errors_json, duplicate_of
           FROM import_staging WHERE batch_id = ? ORDER BY row_number LIMIT ?""",
        (batch_id, limit),
    ).fetchall()
    result = []
    for row in rows:
        data = json.loads(row["data_json"])
        result.append({
            "row": row["row_number"],
            "status": row["validation_status"],
            "errors": json.loads(row["errors_json"] or "[]"),
            "duplicate_of": row["duplicate_of"],
            "nama_narasumber": data.get("Nama Narasumber", ""),
            "nama_usaha": data.get("Nama Usaha", ""),
            "kecamatan": data.get("Kecamatan", ""),
            "kelurahan": data.get("Kelurahan", ""),
            "subsektor": data.get("Sub Sektor", ""),
        })
    return result


@api_bp.route("/upload", methods=["POST"])
@role_required("operator")
def upload_excel():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "Tidak ada file yang diunggah."}), 400
    file = request.files["file"]
    filename = (file.filename or "").strip()
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "message": "Hanya file .xlsx yang diterima."}), 400
    if file.mimetype not in ALLOWED_UPLOAD_MIMES:
        return jsonify({"success": False, "message": "MIME type file tidak sesuai format XLSX."}), 400

    raw = file.read()
    if not raw.startswith(b"PK\x03\x04") or not _valid_xlsx_container(raw):
        return jsonify({"success": False, "message": "Isi file bukan dokumen XLSX yang valid."}), 400
    digest = hashlib.sha256(raw).hexdigest()

    try:
        workbook = pd.ExcelFile(BytesIO(raw), engine="openpyxl")
        frames = []
        for sheet_name in workbook.sheet_names:
            sheet = workbook.parse(sheet_name=sheet_name)
            sheet = sheet.loc[:, [
                column for column in sheet.columns
                if column not in {"No.", "Unnamed: 0"} and not str(column).startswith("Unnamed")
            ]].copy()
            sheet["Sheet"] = sheet_name
            frames.append(sheet)
        dataframe = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    except Exception:
        return jsonify({"success": False, "message": "File XLSX rusak atau tidak dapat dibaca."}), 422

    if dataframe.empty:
        return jsonify({"success": False, "message": "File XLSX tidak berisi data."}), 422
    missing = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing:
        return jsonify({
            "success": False,
            "message": f"Kolom wajib tidak ditemukan: {', '.join(missing)}.",
        }), 422
    if len(dataframe) > MAX_UPLOAD_ROWS:
        return jsonify({
            "success": False,
            "message": f"Jumlah baris melebihi batas {MAX_UPLOAD_ROWS}.",
        }), 422

    batch_id = uuid.uuid4().hex
    now = utcnow()
    counts = {"valid": 0, "error": 0, "duplicate": 0}
    with transaction() as conn:
        existing_rows = conn.execute(
            'SELECT id, "Nama Narasumber", "Nama Usaha", "No Telp", "Sub Sektor" '
            'FROM pelaku_ekraf WHERE is_active = 1'
        ).fetchall()
        existing = {_dedup_key(dict(row)): row["id"] for row in existing_rows}
        seen: dict[tuple[str, str, str], int | None] = dict(existing)

        conn.execute(
            """INSERT INTO import_batches
               (id, filename, file_sha256, uploaded_by, status, total_rows, created_at)
               VALUES (?, ?, ?, ?, 'preview', ?, ?)""",
            (batch_id, filename, digest, current_user.id, len(dataframe), now),
        )
        for index, series in dataframe.iterrows():
            original = {str(key): _clean_excel_value(value) for key, value in series.items()}
            clean, errors = validate_actor_payload(original, conn)
            clean["Sheet"] = original.get("Sheet") or clean.get("Kecamatan", "")
            key = _dedup_key(clean)
            duplicate_of = None
            status = "valid"
            if errors:
                status = "error"
            elif not key[0] or not key[1]:
                status = "error"
                errors.append("Kunci deduplikasi nama usaha dan subsektor tidak lengkap.")
            elif key in seen:
                status = "duplicate"
                duplicate_of = seen[key]
            else:
                seen[key] = None
            counts[status] += 1
            conn.execute(
                """INSERT INTO import_staging
                   (batch_id, row_number, data_json, validation_status, errors_json,
                    duplicate_of, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    batch_id, index + 2, json.dumps(clean, ensure_ascii=False, default=str),
                    status, json.dumps(errors, ensure_ascii=False), duplicate_of, now,
                ),
            )
        conn.execute(
            """UPDATE import_batches SET valid_rows = ?, error_rows = ?, duplicate_rows = ?,
               summary_json = ? WHERE id = ?""",
            (
                counts["valid"], counts["error"], counts["duplicate"],
                json.dumps(counts), batch_id,
            ),
        )
        record_audit(
            conn, action="upload_preview", entity="import_batch", entity_id=batch_id,
            new_value={"filename": filename, **counts}, **_audit_context(),
        )
        batch = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        preview = _preview_rows(conn, batch_id)

    return jsonify({
        "success": True,
        "message": "File berhasil divalidasi. Periksa preview sebelum melakukan commit.",
        "batch": _serialize_batch(batch),
        "preview": preview,
    }), 201


@api_bp.route("/upload/<batch_id>", methods=["GET"])
@role_required("operator")
def import_preview(batch_id):
    conn = connect_db()
    try:
        batch, error = _batch_access(conn, batch_id)
        if error:
            return error
        return jsonify({
            "success": True,
            "batch": _serialize_batch(batch),
            "preview": _preview_rows(conn, batch_id),
        })
    finally:
        conn.close()


@api_bp.route("/upload/<batch_id>/commit", methods=["POST"])
@role_required("operator")
def import_commit(batch_id):
    access_conn = connect_db()
    try:
        batch, error = _batch_access(access_conn, batch_id)
        if error:
            return error
        if batch["status"] != "preview":
            return jsonify({"success": False, "message": "Batch tidak berada pada status preview."}), 409
    finally:
        access_conn.close()

    backup_path = create_backup(f"pre-import-{batch_id[:8]}")
    with transaction() as conn:
        batch = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        if not batch or batch["status"] != "preview":
            return jsonify({"success": False, "message": "Status batch berubah. Muat ulang preview."}), 409
        staged = conn.execute(
            """SELECT id, data_json FROM import_staging
               WHERE batch_id = ? AND validation_status = 'valid' ORDER BY row_number""",
            (batch_id,),
        ).fetchall()
        inserted = 0
        for row in staged:
            data = json.loads(row["data_json"])
            data.update({
                "created_at": utcnow(),
                "created_by": current_user.id,
                "import_batch_id": batch_id,
                "is_active": 1,
            })
            columns = list(data)
            quoted = ", ".join(f'"{column}"' for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            cursor = conn.execute(
                f"INSERT INTO pelaku_ekraf ({quoted}) VALUES ({placeholders})",
                tuple(data[column] for column in columns),
            )
            conn.execute(
                "UPDATE import_staging SET committed_record_id = ? WHERE id = ?",
                (cursor.lastrowid, row["id"]),
            )
            inserted += 1
        conn.execute(
            """UPDATE import_batches SET status = 'committed', committed_at = ?,
               committed_by = ?, backup_path = ? WHERE id = ?""",
            (utcnow(), current_user.id, str(backup_path), batch_id),
        )
        record_audit(
            conn, action="import_commit", entity="import_batch", entity_id=batch_id,
            new_value={"inserted": inserted, "backup": backup_path.name}, **_audit_context(),
        )
    return jsonify({
        "success": True,
        "message": f"{inserted} data valid berhasil diimpor.",
        "inserted": inserted,
        "errors": batch["error_rows"],
        "duplicates": batch["duplicate_rows"],
    })


@api_bp.route("/upload/<batch_id>/cancel", methods=["POST"])
@role_required("operator")
def import_cancel(batch_id):
    with transaction() as conn:
        batch, error = _batch_access(conn, batch_id)
        if error:
            return error
        if batch["status"] != "preview":
            return jsonify({"success": False, "message": "Hanya batch preview yang dapat dibatalkan."}), 409
        conn.execute("UPDATE import_batches SET status = 'cancelled' WHERE id = ?", (batch_id,))
        record_audit(
            conn, action="import_cancel", entity="import_batch", entity_id=batch_id,
            old_value=_serialize_batch(batch), **_audit_context(),
        )
    return jsonify({"success": True, "message": "Batch import dibatalkan."})


@api_bp.route("/upload/<batch_id>/rollback", methods=["POST"])
@role_required("admin")
def import_rollback(batch_id):
    with transaction() as conn:
        batch, error = _batch_access(conn, batch_id)
        if error:
            return error
        if batch["status"] != "committed":
            return jsonify({"success": False, "message": "Hanya batch committed yang dapat di-rollback."}), 409
        rows = conn.execute(
            "SELECT id FROM pelaku_ekraf WHERE import_batch_id = ? AND is_active = 1", (batch_id,)
        ).fetchall()
        now = utcnow()
        conn.execute(
            """UPDATE pelaku_ekraf SET is_active = 0, deleted_at = ?, deleted_by = ?,
               updated_at = ?, updated_by = ? WHERE import_batch_id = ? AND is_active = 1""",
            (now, current_user.id, now, current_user.id, batch_id),
        )
        conn.execute(
            """UPDATE import_batches SET status = 'rolled_back', rolled_back_at = ?,
               rolled_back_by = ? WHERE id = ?""",
            (now, current_user.id, batch_id),
        )
        record_audit(
            conn, action="import_rollback", entity="import_batch", entity_id=batch_id,
            old_value={"record_ids": [row["id"] for row in rows]}, **_audit_context(),
        )
    return jsonify({"success": True, "message": f"Rollback selesai: {len(rows)} data dinonaktifkan."})


@api_bp.route("/upload/<batch_id>/errors", methods=["GET"])
@role_required("operator")
def import_errors(batch_id):
    conn = connect_db()
    try:
        batch, error = _batch_access(conn, batch_id)
        if error:
            return error
        rows = conn.execute(
            """SELECT row_number, validation_status, errors_json, data_json
               FROM import_staging WHERE batch_id = ? AND validation_status != 'valid'
               ORDER BY row_number""",
            (batch_id,),
        ).fetchall()
    finally:
        conn.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["baris", "status", "kesalahan", "data"])
    for row in rows:
        writer.writerow([
            row["row_number"], row["validation_status"],
            "; ".join(json.loads(row["errors_json"] or "[]")), row["data_json"],
        ])
    payload = BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(
        payload, mimetype="text/csv", as_attachment=True,
        download_name=f"import-errors-{batch_id[:8]}.csv",
    )


@api_bp.route("/export")
@role_required("viewer")
def export_data():
    fmt = request.args.get("format", "csv").lower()
    if fmt not in {"csv", "xlsx"}:
        return jsonify({"success": False, "message": "Format ekspor harus csv atau xlsx."}), 400
    dataframe, _ = load_data(DB_PATH)
    dataframe = apply_filters(
        dataframe,
        kecamatan_list=request.args.getlist("kecamatan") or None,
        kelurahan_list=request.args.getlist("kelurahan") or None,
        subsektor_list=request.args.getlist("subsektor") or None,
        search_text=request.args.get("search", ""),
    )
    columns = [column for column in BUSINESS_COLUMNS if column in dataframe.columns]
    dataframe = dataframe[columns].apply(lambda column: column.map(_spreadsheet_safe))
    buffer = BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Data Ekraf")
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        buffer.write(dataframe.to_csv(index=False).encode("utf-8-sig"))
        mimetype = "text/csv"
    buffer.seek(0)
    with transaction() as conn:
        record_audit(
            conn, action="export", entity="pelaku_ekraf", new_value={"format": fmt, "rows": len(dataframe)},
            **_audit_context(),
        )
    return send_file(
        buffer, mimetype=mimetype, as_attachment=True,
        download_name=f"sebaran_ekraf_malang.{fmt}",
    )

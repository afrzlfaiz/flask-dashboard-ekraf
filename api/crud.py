"""Validated CRUD, audit history, soft delete, restore, and guarded purge."""

from __future__ import annotations

import re
from datetime import datetime

from flask import g, jsonify, request
from flask_login import current_user, login_required

from api import api_bp
from auth import role_required
from config import KECAMATAN_LIST, SUBSECTOR_COLORS
from utils.database import connect_db, record_audit, row_as_dict, transaction, utcnow

API_TO_DB = {
    "nama_narasumber": "Nama Narasumber",
    "nama_usaha": "Nama Usaha",
    "alamat": "Alamat",
    "kecamatan": "Kecamatan",
    "kelurahan": "Kelurahan",
    "no_hp": "No Telp",
    "subsektor": "Sub Sektor",
    "kategori_usaha": "Kategori Usaha",
    "tahun_berdiri": "Tahun Berdiri",
    "email": "Email",
    "latitude": "lat",
    "longitude": "lon",
}
LEGACY_TO_API = {db_name: api_name for api_name, db_name in API_TO_DB.items()}
REQUIRED_FIELDS = {
    "nama_narasumber": "Nama narasumber",
    "nama_usaha": "Nama usaha",
    "alamat": "Alamat",
    "kecamatan": "Kecamatan",
    "kelurahan": "Kelurahan",
    "subsektor": "Subsektor",
    "latitude": "Latitude",
    "longitude": "Longitude",
}
MAX_LENGTHS = {
    "nama_narasumber": 200,
    "nama_usaha": 250,
    "alamat": 1000,
    "kecamatan": 100,
    "kelurahan": 100,
    "no_hp": 30,
    "subsektor": 150,
    "kategori_usaha": 150,
    "email": 254,
}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _canonical_payload(body: dict) -> dict:
    result = {}
    for key, value in body.items():
        api_key = LEGACY_TO_API.get(key, key)
        if api_key in API_TO_DB:
            result[api_key] = value
    return result


def _reference_values(conn):
    kelurahan_rows = conn.execute(
        'SELECT DISTINCT "Kecamatan", "Kelurahan" FROM pelaku_ekraf '
        'WHERE is_active = 1 AND "Kelurahan" IS NOT NULL'
    ).fetchall()
    kelurahan_by_kecamatan: dict[str, set[str]] = {}
    for row in kelurahan_rows:
        kelurahan_by_kecamatan.setdefault(str(row["Kecamatan"]).strip(), set()).add(
            str(row["Kelurahan"]).strip()
        )
    subsektor = set(SUBSECTOR_COLORS)
    subsektor.update(
        str(row["subsektor"]).strip() for row in conn.execute(
            'SELECT DISTINCT "Sub Sektor" AS subsektor FROM pelaku_ekraf '
            'WHERE is_active = 1 AND "Sub Sektor" IS NOT NULL'
        )
    )
    return kelurahan_by_kecamatan, subsektor


def validate_actor_payload(body: dict, conn) -> tuple[dict, list[str]]:
    """Return normalized DB-column values and human-readable validation errors."""
    payload = _canonical_payload(body)

    # ponytail: jika hanya satu dari nama usaha/narasumber yang diisi, samakan nilainya.
    nn = (payload.get("nama_narasumber") or "").strip()
    nu = (payload.get("nama_usaha") or "").strip()
    if nn and not nu:
        payload["nama_usaha"] = nn
    elif nu and not nn:
        payload["nama_narasumber"] = nu

    errors = []

    for field, label in REQUIRED_FIELDS.items():
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{label} wajib diisi.")

    for field, max_length in MAX_LENGTHS.items():
        if field in payload and payload[field] is not None:
            payload[field] = str(payload[field]).strip()
            if len(payload[field]) > max_length:
                errors.append(f"{field.replace('_', ' ').title()} maksimal {max_length} karakter.")

    for field, label in (("latitude", "Latitude"), ("longitude", "Longitude")):
        if payload.get(field) not in (None, ""):
            try:
                payload[field] = float(payload[field])
            except (TypeError, ValueError):
                errors.append(f"{label} harus berupa angka.")

    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if isinstance(latitude, (int, float)) and not -90 <= latitude <= 90:
        errors.append("Latitude harus berada di antara -90 dan 90.")
    if isinstance(longitude, (int, float)) and not -180 <= longitude <= 180:
        errors.append("Longitude harus berada di antara -180 dan 180.")
    if latitude == 0 or longitude == 0:
        errors.append("Koordinat tidak boleh bernilai nol.")

    year = payload.get("tahun_berdiri")
    if year not in (None, ""):
        try:
            payload["tahun_berdiri"] = int(year)
            if not 1800 <= payload["tahun_berdiri"] <= datetime.now().year + 1:
                errors.append("Tahun berdiri berada di luar rentang yang diizinkan.")
        except (TypeError, ValueError):
            errors.append("Tahun berdiri harus berupa angka.")
    else:
        payload["tahun_berdiri"] = None

    email = payload.get("email", "")
    if email and not EMAIL_RE.fullmatch(email):
        errors.append("Format email tidak valid.")
    phone = re.sub(r"[\s()+.-]", "", (payload.get("no_hp") or ""))
    if phone and (not phone.isdigit() or not 8 <= len(phone) <= 16):
        errors.append("Format nomor HP/WA tidak valid.")

    kelurahan_by_kecamatan, subsektor_values = _reference_values(conn)
    kecamatan = payload.get("kecamatan", "")
    kelurahan = payload.get("kelurahan", "")
    if kecamatan and kecamatan not in KECAMATAN_LIST:
        errors.append("Kecamatan tidak terdapat pada referensi Kota Malang.")
    if kecamatan in kelurahan_by_kecamatan and kelurahan:
        if kelurahan not in kelurahan_by_kecamatan[kecamatan]:
            errors.append("Kelurahan tidak sesuai dengan kecamatan yang dipilih.")
    if payload.get("subsektor") and payload["subsektor"] not in subsektor_values:
        errors.append("Subsektor tidak terdapat pada referensi resmi.")

    db_values = {
        API_TO_DB[field]: value for field, value in payload.items() if field in API_TO_DB
    }
    return db_values, errors


def serialize_actor(row) -> dict:
    return {
        "id": row["id"],
        "nama_narasumber": row["Nama Narasumber"] or "",
        "nama_usaha": row["Nama Usaha"] or "",
        "alamat": row["Alamat"] or "",
        "kecamatan": row["Kecamatan"] or "",
        "kelurahan": row["Kelurahan"] or "",
        "no_hp": row["No Telp"] or "",
        "subsektor": row["Sub Sektor"] or "",
        "kategori_usaha": row["Kategori Usaha"] or "",
        "tahun_berdiri": row["Tahun Berdiri"],
        "email": row["Email"] or "",
        "latitude": row["lat"],
        "longitude": row["lon"],
        "is_active": bool(row["is_active"]),
        "deleted_at": row["deleted_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "import_batch_id": row["import_batch_id"],
    }


def _audit_context():
    return {
        "user_id": int(current_user.id),
        "ip_address": request.remote_addr,
        "request_id": getattr(g, "request_id", None),
    }


@api_bp.route("/crud", methods=["GET"])
@role_required("operator")
def crud_list():
    include_inactive = request.args.get("include_inactive") == "1" and current_user.has_role("admin")
    where = "1 = 1" if include_inactive else "is_active = 1"
    conn = connect_db()
    try:
        rows = conn.execute(
            f"SELECT * FROM pelaku_ekraf WHERE {where} ORDER BY is_active DESC, id DESC"
        ).fetchall()
    finally:
        conn.close()
    return jsonify({"data": [serialize_actor(row) for row in rows]})


@api_bp.route("/crud", methods=["POST"])
@role_required("operator")
def crud_create():
    body = request.get_json(silent=True) or {}
    with transaction() as conn:
        clean, errors = validate_actor_payload(body, conn)
        if errors:
            return jsonify({"success": False, "message": "Validasi gagal.", "errors": errors}), 422
        clean["Sheet"] = clean.get("Kecamatan", "")
        clean["created_at"] = utcnow()
        clean["created_by"] = current_user.id
        columns = list(clean)
        quoted = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("%s" for _ in columns)
        cursor = conn.execute(
            f"INSERT INTO pelaku_ekraf ({quoted}) VALUES ({placeholders}) RETURNING id",
            tuple(clean[column] for column in columns),
        )
        new_id = cursor.fetchone()["id"]
        record_audit(
            conn, action="create", entity="pelaku_ekraf", entity_id=new_id,
            new_value=clean, **_audit_context(),
        )
    return jsonify({"success": True, "id": new_id, "message": "Data berhasil ditambahkan."}), 201


@api_bp.route("/crud/<int:actor_id>", methods=["PUT"])
@role_required("operator")
def crud_update(actor_id):
    body = request.get_json(silent=True) or {}
    with transaction() as conn:
        old = conn.execute(
            "SELECT * FROM pelaku_ekraf WHERE id = %s AND is_active = 1", (actor_id,)
        ).fetchone()
        if not old:
            return jsonify({"success": False, "message": "Data aktif tidak ditemukan."}), 404
        clean, errors = validate_actor_payload(body, conn)
        if errors:
            return jsonify({"success": False, "message": "Validasi gagal.", "errors": errors}), 422
        clean["updated_at"] = utcnow()
        clean["updated_by"] = current_user.id
        set_clause = ", ".join(f'"{column}" = %s' for column in clean)
        conn.execute(
            f"UPDATE pelaku_ekraf SET {set_clause} WHERE id = %s AND is_active = 1",
            tuple(clean.values()) + (actor_id,),
        )
        record_audit(
            conn, action="update", entity="pelaku_ekraf", entity_id=actor_id,
            old_value=row_as_dict(old), new_value=clean, **_audit_context(),
        )
    return jsonify({"success": True, "message": "Data berhasil diperbarui."})


@api_bp.route("/crud/<int:actor_id>", methods=["DELETE"])
@role_required("admin")
def crud_delete(actor_id):
    with transaction() as conn:
        old = conn.execute(
            "SELECT * FROM pelaku_ekraf WHERE id = %s AND is_active = 1", (actor_id,)
        ).fetchone()
        if not old:
            return jsonify({"success": False, "message": "Data aktif tidak ditemukan."}), 404
        conn.execute(
            """UPDATE pelaku_ekraf SET is_active = 0, deleted_at = %s, deleted_by = %s,
               updated_at = %s, updated_by = %s WHERE id = %s""",
            (utcnow(), current_user.id, utcnow(), current_user.id, actor_id),
        )
        record_audit(
            conn, action="soft_delete", entity="pelaku_ekraf", entity_id=actor_id,
            old_value=row_as_dict(old), **_audit_context(),
        )
    return jsonify({"success": True, "message": "Data berhasil dinonaktifkan."})


@api_bp.route("/crud/<int:actor_id>/restore", methods=["POST"])
@role_required("admin")
def crud_restore(actor_id):
    with transaction() as conn:
        old = conn.execute(
            "SELECT * FROM pelaku_ekraf WHERE id = %s AND is_active = 0", (actor_id,)
        ).fetchone()
        if not old:
            return jsonify({"success": False, "message": "Data nonaktif tidak ditemukan."}), 404
        conn.execute(
            """UPDATE pelaku_ekraf SET is_active = 1, deleted_at = NULL, deleted_by = NULL,
               updated_at = %s, updated_by = %s WHERE id = %s""",
            (utcnow(), current_user.id, actor_id),
        )
        record_audit(
            conn, action="restore", entity="pelaku_ekraf", entity_id=actor_id,
            old_value=row_as_dict(old), **_audit_context(),
        )
    return jsonify({"success": True, "message": "Data berhasil dipulihkan."})


@api_bp.route("/crud/<int:actor_id>/purge", methods=["DELETE"])
@role_required("admin")
def crud_purge(actor_id):
    body = request.get_json(silent=True) or {}
    if body.get("confirm") != "PURGE":
        return jsonify({
            "success": False,
            "message": "Penghapusan permanen memerlukan konfirmasi PURGE.",
        }), 400
    with transaction() as conn:
        old = conn.execute(
            "SELECT * FROM pelaku_ekraf WHERE id = %s AND is_active = 0", (actor_id,)
        ).fetchone()
        if not old:
            return jsonify({"success": False, "message": "Hanya data nonaktif yang dapat dihapus permanen."}), 409
        record_audit(
            conn, action="purge", entity="pelaku_ekraf", entity_id=actor_id,
            old_value=row_as_dict(old), **_audit_context(),
        )
        conn.execute("DELETE FROM pelaku_ekraf WHERE id = %s", (actor_id,))
    return jsonify({"success": True, "message": "Data dihapus permanen melalui prosedur khusus."})

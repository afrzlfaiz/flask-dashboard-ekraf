"""CRUD endpoints — GET/POST/PUT/DELETE /api/crud."""
import sqlite3

from flask import jsonify, request

from api import api_bp
from config import DB_PATH


@api_bp.route("/crud", methods=["GET"])
def crud_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM pelaku_ekraf ORDER BY id").fetchall()
    conn.close()

    data = []
    for r in rows:
        data.append({
            "id": r["id"],
            "nama_narasumber": r["Nama Narasumber"] or "",
            "nama_usaha": r["Nama Usaha"] or r["Nama Narasumber"] or "",
            "kecamatan": r["Kecamatan"] or "",
            "kelurahan": r["Kelurahan"] or "",
            "alamat": r["Alamat"] or "",
            "latitude": r["lat"],
            "longitude": r["lon"],
            "subsektor": r["Sub Sektor"] or "",
            "kategori_usaha": r["Kategori Usaha"] or "",
            "tahun_berdiri": r["Tahun Berdiri"] if r["Tahun Berdiri"] is not None else "",
            "no_hp": r["No Telp"] or "",
            "email": r["Email"] or "",
        })
    return jsonify({"data": data})


@api_bp.route("/crud", methods=["POST"])
def crud_create():
    body = request.get_json(force=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO pelaku_ekraf ("Nama Narasumber", "Nama Usaha", "Alamat", "Kecamatan", "Kelurahan",
                                   "No Telp", "Sub Sektor", "Kategori Usaha", "Tahun Berdiri", "Email", "lat", "lon", "Sheet")
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        body.get("nama_narasumber", ""),
        body.get("nama_usaha", ""),
        body.get("alamat", ""),
        body.get("kecamatan", ""),
        body.get("kelurahan", ""),
        body.get("no_hp", ""),
        body.get("subsektor", ""),
        body.get("kategori_usaha", ""),
        body.get("tahun_berdiri"),
        body.get("email", ""),
        body.get("latitude"),
        body.get("longitude"),
        body.get("kecamatan", ""),  # Sheet = kecamatan
    ))
    conn.commit()
    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({"id": new_id, "message": "Data berhasil ditambahkan."}), 201


@api_bp.route("/crud/<int:id>", methods=["PUT"])
def crud_update(id):
    body = request.get_json(force=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE pelaku_ekraf SET
            "Nama Narasumber" = ?, "Nama Usaha" = ?, "Alamat" = ?, "Kecamatan" = ?, "Kelurahan" = ?,
            "No Telp" = ?, "Sub Sektor" = ?, "Kategori Usaha" = ?, "Tahun Berdiri" = ?, "Email" = ?, "lat" = ?, "lon" = ?
        WHERE id = ?
    """, (
        body.get("nama_narasumber", ""),
        body.get("nama_usaha", ""),
        body.get("alamat", ""),
        body.get("kecamatan", ""),
        body.get("kelurahan", ""),
        body.get("no_hp", ""),
        body.get("subsektor", ""),
        body.get("kategori_usaha", ""),
        body.get("tahun_berdiri"),
        body.get("email", ""),
        body.get("latitude"),
        body.get("longitude"),
        id,
    ))
    conn.commit()
    conn.close()
    return jsonify({"message": "Data berhasil diperbarui."})


@api_bp.route("/crud/<int:id>", methods=["DELETE"])
def crud_delete(id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM pelaku_ekraf WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Data berhasil dihapus."})

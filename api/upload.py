"""POST /api/upload — import Excel. GET /api/export — download CSV/XLSX."""
from io import BytesIO

import pandas as pd
from flask import jsonify, request, send_file

from api import api_bp
from config import DB_PATH


@api_bp.route("/upload", methods=["POST"])
def upload_excel():
    if "file" not in request.files:
        return jsonify({"error": "Tidak ada file yang diunggah."}), 400

    file = request.files["file"]
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        return jsonify({"error": "Format file tidak didukung. Gunakan .xlsx, .xls, atau .csv."}), 400

    import sqlite3
    import traceback

    conn = sqlite3.connect(DB_PATH)
    total_imported = 0
    total_skipped = 0

    # Load existing (Nama Narasumber, Sub Sektor) pairs for dedup
    existing = set()
    try:
        cur = conn.execute('SELECT "Nama Narasumber", "Sub Sektor" FROM pelaku_ekraf')
        for row in cur.fetchall():
            existing.add((str(row[0] or "").strip(), str(row[1] or "").strip()))
    except Exception:
        pass  # table might not exist yet on first import

    # Read file into memory once — Flask FileStorage stream is not re-readable
    file_bytes = BytesIO(file.read())
    filename = file.filename

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_bytes)
            df["Sheet"] = "CSV Import"
        else:
            xl = pd.ExcelFile(file_bytes)
            dfs = []
            for sheet in xl.sheet_names:
                df_sheet = xl.parse(sheet_name=sheet)
                df_sheet["Sheet"] = sheet
                skip_cols = ["No.", "Unnamed: 0"]
                keep = [c for c in df_sheet.columns if c not in skip_cols and not str(c).startswith("Unnamed")]
                dfs.append(df_sheet[keep].copy())
            df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        if df.empty:
            conn.close()
            return jsonify({"message": "0 baris diimport (file kosong).", "count": 0, "skipped": 0})

        # Clean
        df = df.dropna(subset=["Nama Narasumber"]) if "Nama Narasumber" in df.columns else df
        for col in ["lat", "lon"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Dedup: filter out rows where (Nama Narasumber, Sub Sektor) already exists
        df["_dedup_key"] = df.apply(
            lambda r: (str(r.get("Nama Narasumber", "")).strip(),
                       str(r.get("Sub Sektor", "")).strip()), axis=1)
        mask_new = ~df["_dedup_key"].isin(existing)
        df_new = df[mask_new].drop(columns=["_dedup_key"])
        total_skipped = int((~mask_new).sum())

        if len(df_new) > 0:
            # Use raw SQLite insert — pandas to_sql doesn't quote column names with spaces
            table_cols = [row[1] for row in conn.execute("PRAGMA table_info(pelaku_ekraf)").fetchall()
                          if row[1] != "id"]  # skip auto-increment id
            # Only keep columns that exist in the table
            insert_cols = [c for c in df_new.columns if c in table_cols]
            placeholders = ", ".join(["?"] * len(insert_cols))
            quoted = ", ".join(f'"{c}"' for c in insert_cols)
            sql = f'INSERT INTO pelaku_ekraf ({quoted}) VALUES ({placeholders})'
            rows = [tuple(row[c] if not pd.isna(row[c]) else None for c in insert_cols)
                    for _, row in df_new.iterrows()]
            conn.executemany(sql, rows)
            total_imported = len(rows)

        conn.commit()
    except Exception:
        conn.close()
        traceback.print_exc()
        return jsonify({"error": f"Gagal memproses file: {traceback.format_exc()}"}), 500

    conn.close()
    return jsonify({
        "message": f"{total_imported} baris baru diimport, {total_skipped} duplikat dilewati.",
        "count": total_imported,
        "skipped": total_skipped,
    })


@api_bp.route("/export")
def export_data():
    fmt = request.args.get("format", "csv")
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM pelaku_ekraf", conn)
    conn.close()

    buf = BytesIO()
    if fmt == "xlsx":
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data Ekraf")
        buf.seek(0)
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name="sebaran_ekraf_malang.xlsx")
    else:
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="sebaran_ekraf_malang.csv")

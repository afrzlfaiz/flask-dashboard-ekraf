"""GET /api/table — return a bounded PostgreSQL page for DataTables."""
from __future__ import annotations

from typing import Any

from flask import jsonify, request
from flask_login import current_user

from api import api_bp
from utils.database import connect_db


MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 10
SORT_COLUMNS = {
    "id": '"id"',
    "no": '"id"',
    "nama_narasumber": '"Nama Narasumber"',
    "nama_usaha": 'COALESCE(NULLIF(TRIM("Nama Usaha"), \'\'), "Nama Narasumber")',
    "subsektor": '"Sub Sektor"',
    "kecamatan": '"Kecamatan"',
    "kelurahan": '"Kelurahan"',
    "tahun_berdiri": '"Tahun Berdiri"',
    "kontak": '"No Telp"',
}
QUICK_SEARCH_COLUMNS = (
    '"Nama Narasumber"',
    '"Nama Usaha"',
    '"Sub Sektor"',
    '"Kecamatan"',
    '"Kelurahan"',
    'CAST("Tahun Berdiri" AS TEXT)',
    '"No Telp"',
    '"Email"',
)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _like_pattern(value: str) -> str:
    """Treat LIKE wildcard characters from user input as literal text."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _append_in_filter(
    clauses: list[str], params: list[Any], column: str, values: list[str]
) -> None:
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        return
    placeholders = ", ".join("%s" for _ in cleaned)
    clauses.append(f'{column} IN ({placeholders})')
    params.extend(cleaned)


def _serialize_row(row, number: int, can_view_pii: bool = True) -> dict[str, Any]:
    business_name = row["Nama Usaha"] or row["Nama Narasumber"] or ""
    year = row["Tahun Berdiri"]
    if year not in (None, ""):
        try:
            year = int(float(year))
        except (TypeError, ValueError):
            year = ""
    else:
        year = ""

    result = {
        "no": number,
        "id": int(row["id"]),
        "nama_narasumber": row["Nama Narasumber"] or "",
        "nama_usaha": business_name,
        "alamat": row["Alamat"] or "",
        "kecamatan": row["Kecamatan"] or "",
        "kelurahan": row["Kelurahan"] or "",
        "subsektor": row["Sub Sektor"] or "",
        "kategori_usaha": row["Kategori Usaha"] or "",
        "tahun_berdiri": year,
        "latitude": row["lat"],
        "longitude": row["lon"],
    }
    if can_view_pii:
        result["no_hp"] = row["No Telp"] or ""
        result["email"] = row["Email"] or ""
    return result


@api_bp.route("/table")
def table_data():
    page = _bounded_int("page", 1, 1, 2_147_483_647)
    per_page = _bounded_int("per_page", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    draw = _bounded_int("draw", 0, 0, 2_147_483_647)
    sort_key = request.args.get("sort", "id")
    sort_column = SORT_COLUMNS.get(sort_key, SORT_COLUMNS["id"])
    direction = request.args.get("direction", "asc").lower()
    if direction not in {"asc", "desc"}:
        direction = "asc"

    clauses = ["is_active = 1"]
    params: list[Any] = []
    _append_in_filter(clauses, params, '"Kecamatan"', request.args.getlist("kecamatan"))
    _append_in_filter(clauses, params, '"Kelurahan"', request.args.getlist("kelurahan"))
    _append_in_filter(clauses, params, '"Sub Sektor"', request.args.getlist("subsektor"))

    dashboard_search = request.args.get("search", "").strip()[:200]
    if dashboard_search:
        clauses.append('COALESCE("Nama Narasumber", \'\') LIKE %s ESCAPE \'\\\'')
        params.append(_like_pattern(dashboard_search))

    quick_search = request.args.get("quick_search", "").strip()[:200]
    if quick_search:
        pattern = _like_pattern(quick_search)
        clauses.append(
            "(" + " OR ".join(
                f"COALESCE({column}, '') LIKE %s ESCAPE '\\'"
                for column in QUICK_SEARCH_COLUMNS
            ) + ")"
        )
        params.extend(pattern for _ in QUICK_SEARCH_COLUMNS)

    where_sql = " AND ".join(clauses)
    offset = (page - 1) * per_page
    tie_breaker = "" if sort_key in {"id", "no"} else ', "id" ASC'
    data_sql = f"""
        SELECT id, "Nama Narasumber", "Nama Usaha", "Alamat", "Kecamatan",
               "Kelurahan", "No Telp", "Sub Sektor", "Kategori Usaha",
               "Tahun Berdiri", "Email", lat, lon
        FROM pelaku_ekraf
        WHERE {where_sql}
        ORDER BY {sort_column} {direction.upper()}{tie_breaker}
        LIMIT %s OFFSET %s
    """

    conn = connect_db()
    try:
        records_total = conn.execute(
            "SELECT COUNT(*) AS total FROM pelaku_ekraf WHERE is_active = 1"
        ).fetchone()["total"]
        records_filtered = conn.execute(
            f"SELECT COUNT(*) AS total FROM pelaku_ekraf WHERE {where_sql}", params
        ).fetchone()["total"]
        page_rows = conn.execute(data_sql, [*params, per_page, offset]).fetchall()
    finally:
        conn.close()

    can_view_pii = current_user.is_authenticated and current_user.has_role("operator")
    rows = [_serialize_row(row, offset + index + 1, can_view_pii=can_view_pii) for index, row in enumerate(page_rows)]
    return jsonify({
        "draw": draw,
        "data": rows,
        "page": page,
        "per_page": per_page,
        "total": records_filtered,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
    })

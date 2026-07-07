"""GET /api/table — return paginated data for DataTables."""
from flask import jsonify, request

from api import api_bp
from config import DB_PATH
from utils.data_loader import load_data
from utils.filtering import apply_filters
from utils.helper import row_to_dict


@api_bp.route("/table")
def table_data():
    df, _ = load_data(DB_PATH)
    filtered = apply_filters(
        df,
        kecamatan_list=request.args.getlist("kecamatan") or None,
        kelurahan_list=request.args.getlist("kelurahan") or None,
        subsektor_list=request.args.getlist("subsektor") or None,
        search_text=request.args.get("search", ""),
    )

    rows = []
    for _, row in filtered.iterrows():
        rows.append(row_to_dict(row))

    return jsonify({"data": rows, "total": len(rows)})

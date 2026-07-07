"""POST /api/filter — return filtered data + dropdown options."""
import pandas as pd
from flask import jsonify, request

from api import api_bp
from config import DB_PATH
from utils.data_loader import load_data
from utils.filtering import apply_filters
from utils.helper import get_kelurahan_options, row_to_dict


@api_bp.route("/filter", methods=["POST"])
def filter_data():
    body = request.get_json(silent=True) or {}
    # Accept single value or list for kecamatan & kelurahan (multi-select)
    kecamatan_raw = body.get("kecamatan", [])
    if isinstance(kecamatan_raw, str):
        kecamatan_list = [kecamatan_raw] if kecamatan_raw else []
    else:
        kecamatan_list = kecamatan_raw or []

    kelurahan_raw = body.get("kelurahan", [])
    if isinstance(kelurahan_raw, str):
        kelurahan_list = [kelurahan_raw] if kelurahan_raw else []
    else:
        kelurahan_list = kelurahan_raw or []

    subsektor_list = body.get("subsektor", []) or None
    search_text = body.get("search", "")

    df, _ = load_data(DB_PATH)
    filtered = apply_filters(df, kecamatan_list or None, kelurahan_list or None, subsektor_list, search_text)

    # Build row list for frontend
    rows = []
    for _, row in filtered.iterrows():
        rows.append(row_to_dict(row))

    # Dropdown options — dynamic from actual data
    kelurahan_options = get_kelurahan_options(df, kecamatan_list or None)
    dynamic_kecamatan = sorted(df["Kecamatan"].dropna().unique().tolist())
    dynamic_subsektor = sorted(df["Sub Sektor"].dropna().unique().tolist())

    return jsonify({
        "data": rows,
        "total": len(filtered),
        "total_db": len(df),
        "options": {
            "kecamatan": dynamic_kecamatan,
            "subsektor": dynamic_subsektor,
            "kelurahan": kelurahan_options,
        },
    })

"""POST /api/filter — return filtered data + dropdown options."""
from flask import jsonify, request
from flask_login import current_user

from api import api_bp
from config import DATABASE_URL
from utils.data_loader import load_data
from utils.filtering import apply_filters
from utils.helper import get_kelurahan_options


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
    search_text = body.get("search", "") if current_user.is_authenticated else ""

    df, _ = load_data(DATABASE_URL)
    filtered = apply_filters(df, kecamatan_list or None, kelurahan_list or None, subsektor_list, search_text)

    # Dropdown options — dynamic from actual data
    kelurahan_options = get_kelurahan_options(df, kecamatan_list or None)
    dynamic_kecamatan = sorted(df["Kecamatan"].dropna().unique().tolist())
    dynamic_subsektor = sorted(df["Sub Sektor"].dropna().unique().tolist())

    return jsonify({
        "total": len(filtered),
        "total_db": len(df),
        "options": {
            "kecamatan": dynamic_kecamatan,
            "subsektor": dynamic_subsektor,
            "kelurahan": kelurahan_options,
        },
    })

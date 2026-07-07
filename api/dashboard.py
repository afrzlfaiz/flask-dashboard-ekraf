"""GET /api/kpi — KPI metrics. GET /api/map — map markers + boundaries GeoJSON."""
import json
import os

from flask import jsonify, request

from api import api_bp
from config import DB_PATH, GEOJSON_DIR, KECAMATAN_GEOJSON_PATHS
from utils.data_loader import load_data
from utils.filtering import apply_filters
from utils.helper import row_to_dict
from utils.kpi import get_kpi_metrics


def _parse_filters():
    """Extract filter params from query string."""
    return {
        "kecamatan_list": request.args.getlist("kecamatan") or None,
        "kelurahan_list": request.args.getlist("kelurahan") or None,
        "subsektor_list": request.args.getlist("subsektor") or None,
        "search_text": request.args.get("search", ""),
    }


@api_bp.route("/kpi")
def kpi():
    df, _ = load_data(DB_PATH)
    filters = _parse_filters()
    filtered = apply_filters(df, **filters)
    metrics = get_kpi_metrics(filtered)
    return jsonify(metrics)


@api_bp.route("/map")
def map_data():
    df, _ = load_data(DB_PATH)
    filters = _parse_filters()
    filtered = apply_filters(df, **filters)

    # Only rows with valid coords
    map_df = filtered.dropna(subset=["lat", "lon"])

    markers = [row_to_dict(row) for _, row in map_df.iterrows()]

    # Load GeoJSON boundaries
    boundaries = {"kota": None, "kecamatan": {}}
    kota_path = os.path.join(GEOJSON_DIR, "Kota Malang.geojson")
    if os.path.exists(kota_path):
        with open(kota_path) as f:
            boundaries["kota"] = json.load(f)

    for kec, filename in KECAMATAN_GEOJSON_PATHS.items():
        path = os.path.join(GEOJSON_DIR, filename)
        if os.path.exists(path):
            with open(path) as f:
                boundaries["kecamatan"][kec] = json.load(f)

    return jsonify({"markers": markers, "boundaries": boundaries})

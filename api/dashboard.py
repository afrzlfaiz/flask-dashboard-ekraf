"""GET /api/kpi — KPI metrics. GET /api/map — map markers. GET /api/boundaries — GeoJSON batas wilayah."""
import json
import os

from flask import jsonify, request
from flask_login import current_user

from api import api_bp
from config import DB_PATH, GEOJSON_DIR, KECAMATAN_GEOJSON_PATHS
from utils.data_loader import load_data
from utils.filtering import apply_filters
from utils.helper import row_to_dict
from utils.kpi import get_kpi_metrics

# ponytail: boundaries statis — cache sepanjang proses, tidak bergantung filter/login.
_boundaries_cache = None


def _parse_filters():
    """Extract filter params from query string."""
    return {
        "kecamatan_list": request.args.getlist("kecamatan") or None,
        "kelurahan_list": request.args.getlist("kelurahan") or None,
        "subsektor_list": request.args.getlist("subsektor") or None,
        "search_text": request.args.get("search", "") if current_user.is_authenticated else "",
    }


@api_bp.route("/kpi")
def kpi():
    df, _ = load_data(DB_PATH)
    filters = _parse_filters()
    filtered = apply_filters(df, **filters)
    metrics = get_kpi_metrics(filtered)
    return jsonify(metrics)


def _load_boundaries():
    """Muat GeoJSON batas kota + kecamatan, cache sepanjang proses (statis)."""
    global _boundaries_cache
    if _boundaries_cache is not None:
        return _boundaries_cache

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

    _boundaries_cache = boundaries
    return boundaries


@api_bp.route("/map")
def map_data():
    df, _ = load_data(DB_PATH)
    filters = _parse_filters()
    filtered = apply_filters(df, **filters)

    # Only rows with valid coords
    map_df = filtered.dropna(subset=["lat", "lon"])

    if current_user.is_authenticated:
        markers = [row_to_dict(row, public=False) for _, row in map_df.iterrows()]
    else:
        # Public map uses ~1 km grid aggregation. It never exposes identities or exact points.
        public_df = map_df.copy()
        public_df["lat_grid"] = public_df["lat"].round(2)
        public_df["lon_grid"] = public_df["lon"].round(2)
        grouped = (
            public_df.groupby(["lat_grid", "lon_grid"], dropna=True)
            .agg(
                count=("lat", "size"),
                kecamatan=("Kecamatan", lambda values: values.mode().iloc[0] if not values.mode().empty else ""),
                subsektor=("Sub Sektor", lambda values: values.mode().iloc[0] if not values.mode().empty else ""),
            )
            .reset_index()
        )
        markers = [
            {
                "latitude": float(row["lat_grid"]),
                "longitude": float(row["lon_grid"]),
                "count": int(row["count"]),
                "kecamatan": str(row["kecamatan"]),
                "subsektor": str(row["subsektor"]),
                "is_aggregate": True,
            }
            for _, row in grouped.iterrows()
        ]

    return jsonify({"markers": markers})


@api_bp.route("/boundaries")
def boundaries():
    """GeoJSON batas wilayah kota + kecamatan (statis, di-cache klien)."""
    return jsonify(_load_boundaries())

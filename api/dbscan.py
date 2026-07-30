"""DBSCAN spatial clustering API.

POST /api/dbscan runs DBSCAN with an epsilon radius expressed in meters.
POST /api/dbscan/optimal searches epsilon candidates expressed in meters.

Coordinates and epsilon must be angular radians for Haversine. User-facing
epsilon values are meters and are converted by dividing by Earth's radius.
"""
from math import isfinite

from flask import jsonify, request

from api import api_bp
from config import DATABASE_URL
from utils.data_loader import load_data
from utils.filtering import apply_filters

EARTH_RADIUS_METERS = 6_371_008.8
EPS_VALUES_METERS = (
    100, 150, 200, 250, 300, 400, 500, 650, 800, 1000,
    1250, 1500, 2000, 2500, 3000,
)
MIN_SAMPLES_VALUES = (4, 5, 6, 8, 10, 12, 15, 20)


def _meters_to_radians(eps_meters):
    return eps_meters / EARTH_RADIUS_METERS


def _parse_dbscan_parameters(body):
    raw_eps = body.get("eps", 800.0)
    raw_min_samples = body.get("min_samples", 4)

    try:
        if isinstance(raw_eps, bool):
            raise ValueError
        eps_meters = float(raw_eps)
    except (TypeError, ValueError):
        raise ValueError("Parameter eps harus berupa angka.") from None

    if not isfinite(eps_meters) or not 1 <= eps_meters <= 10_000:
        raise ValueError(
            "Parameter eps harus berada pada rentang 1 sampai 10000 meter."
        )

    try:
        if isinstance(raw_min_samples, bool):
            raise ValueError
        min_samples_number = float(raw_min_samples)
    except (TypeError, ValueError):
        raise ValueError(
            "Parameter min_samples harus berupa bilangan bulat minimal 2."
        ) from None

    if (
        not isfinite(min_samples_number)
        or not min_samples_number.is_integer()
        or min_samples_number < 2
    ):
        raise ValueError(
            "Parameter min_samples harus berupa bilangan bulat minimal 2."
        )

    return eps_meters, int(min_samples_number)


@api_bp.route("/dbscan", methods=["POST"])
def dbscan():
    body = request.get_json(silent=True) or {}

    # Parse filter params if provided (multi-select = lists)
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

    filters = {
        "kecamatan_list": kecamatan_list or None,
        "kelurahan_list": kelurahan_list or None,
        "subsektor_list": body.get("subsektor", []) or None,
        "search_text": body.get("search", ""),
    }

    try:
        eps_meters, min_samples = _parse_dbscan_parameters(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    eps_radians = _meters_to_radians(eps_meters)
    parameters = {
        "eps_meters": eps_meters,
        "min_samples": min_samples,
        "distance_metric": "haversine",
    }

    df, _ = load_data(DATABASE_URL)
    filtered = apply_filters(df, **filters)

    import numpy as np

    data = filtered.dropna(subset=["lat", "lon"]).copy()
    if data.empty:
        return jsonify({
            "n_clusters": 0,
            "n_noise": 0,
            "n_total": 0,
            "n_clustered": 0,
            "points": [],
            "summary": [],
            "cluster_details": [],
            "parameters": parameters,
        })

    coords = np.radians(data[["lat", "lon"]].values)

    from sklearn.cluster import DBSCAN
    dbscan_model = DBSCAN(eps=eps_radians, min_samples=min_samples, metric="haversine")
    data["cluster"] = dbscan_model.fit_predict(coords)

    n_clusters = data["cluster"].nunique() - (1 if -1 in data["cluster"].unique() else 0)
    n_noise = int((data["cluster"] == -1).sum())

    # Build points list for frontend map
    points = []
    for _, row in data.iterrows():
        points.append({
            "id": int(row.get("id", 0)) if row.get("id") is not None else 0,
            "latitude": float(row["lat"]),
            "longitude": float(row["lon"]),
            "cluster": int(row["cluster"]),
            "is_noise": int(row["cluster"]) == -1,
            "nama_usaha": str(row.get("Nama Narasumber", "")),
            "nama_narasumber": str(row.get("Nama Narasumber", "")),
            "subsektor": str(row.get("Sub Sektor", "")),
            "kecamatan": str(row.get("Kecamatan", "")),
            "kelurahan": str(row.get("Kelurahan", "")),
            "alamat": str(row.get("Alamat", "")),
        })

    # Build cluster details with dominant characteristics
    cluster_details = []
    for cid in range(n_clusters):
        cdata = data[data["cluster"] == cid]
        csize = len(cdata)

        # dominant kecamatan
        kec_counts = cdata["Kecamatan"].value_counts()
        dom_kec = kec_counts.index[0] if len(kec_counts) > 0 else "-"
        dom_kec_count = int(kec_counts.iloc[0]) if len(kec_counts) > 0 else 0

        # dominant kelurahan
        kel_counts = cdata["Kelurahan"].value_counts()
        dom_kel = kel_counts.index[0] if len(kel_counts) > 0 else "-"
        dom_kel_count = int(kel_counts.iloc[0]) if len(kel_counts) > 0 else 0

        # dominant subsektor
        sub_counts = cdata["Sub Sektor"].value_counts()
        dom_sub = sub_counts.index[0] if len(sub_counts) > 0 else "-"
        dom_sub_count = int(sub_counts.iloc[0]) if len(sub_counts) > 0 else 0

        # centroid
        centroid_lat = float(cdata["lat"].mean())
        centroid_lon = float(cdata["lon"].mean())

        cluster_details.append({
            "cluster_id": cid,
            "size": csize,
            "percentage": round(csize / len(data) * 100, 1),
            "dominant_kecamatan": {
                "name": str(dom_kec),
                "count": dom_kec_count,
                "percentage": round(dom_kec_count / csize * 100, 1),
            },
            "dominant_kelurahan": {
                "name": str(dom_kel),
                "count": dom_kel_count,
                "percentage": round(dom_kel_count / csize * 100, 1),
            },
            "dominant_subsektor": {
                "name": str(dom_sub),
                "count": dom_sub_count,
                "percentage": round(dom_sub_count / csize * 100, 1),
            },
            "centroid": {
                "lat": round(centroid_lat, 6),
                "lon": round(centroid_lon, 6),
            },
        })

    return jsonify({
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "n_total": len(data),
        "n_clustered": len(data) - n_noise,
        "points": points,
        "cluster_details": cluster_details,
        "parameters": parameters,
    })


@api_bp.route("/dbscan/optimal", methods=["POST"])
def dbscan_optimal():
    """Return the five best balanced DBSCAN parameter combinations."""
    import itertools

    import numpy as np
    from sklearn.cluster import DBSCAN
    from sklearn.metrics import silhouette_score

    body = request.get_json(silent=True) or {}

    # ── Parse filters (same as /dbscan) ─────────────────────────
    kecamatan_raw = body.get("kecamatan", [])
    kecamatan_list = [kecamatan_raw] if isinstance(kecamatan_raw, str) else (kecamatan_raw or [])

    kelurahan_raw = body.get("kelurahan", [])
    kelurahan_list = [kelurahan_raw] if isinstance(kelurahan_raw, str) else (kelurahan_raw or [])

    filters = {
        "kecamatan_list": kecamatan_list or None,
        "kelurahan_list": kelurahan_list or None,
        "subsektor_list": body.get("subsektor", []) or None,
        "search_text": body.get("search", ""),
    }

    df, _ = load_data(DATABASE_URL)
    filtered = apply_filters(df, **filters)
    data = filtered.dropna(subset=["lat", "lon"]).copy()

    if data.empty:
        return jsonify({
            "total_points": 0,
            "combinations_evaluated": 0,
            "candidates": [],
        })

    coords = np.radians(data[["lat", "lon"]].values)
    n = len(coords)

    # ── Search grid ─────────────────────────────────────────────
    MAX_NOISE_RATIO = 0.5
    MAX_CLUSTERS = 25

    candidates = []

    for eps_meters, min_samples in itertools.product(
        EPS_VALUES_METERS,
        MIN_SAMPLES_VALUES,
    ):
        eps_radians = _meters_to_radians(eps_meters)
        model = DBSCAN(
            eps=eps_radians,
            min_samples=min_samples,
            metric="haversine",
        )
        labels = model.fit_predict(coords)

        mask = labels != -1
        clustered_labels = labels[mask]
        unique_clustered_labels = np.unique(clustered_labels)
        n_clusters = len(unique_clustered_labels)
        n_noise = int((labels == -1).sum())
        noise_ratio = n_noise / n if n > 0 else 0

        if (
            not 2 <= n_clusters <= MAX_CLUSTERS
            or noise_ratio > MAX_NOISE_RATIO
            or mask.sum() <= len(unique_clustered_labels)
        ):
            continue

        try:
            silhouette = float(silhouette_score(coords[mask], labels[mask], metric="haversine"))
        except ValueError:
            continue

        if silhouette > 0:
            candidates.append({
                "eps_meters": eps_meters,
                "min_samples": min_samples,
                "n_clusters": n_clusters,
                "n_noise": n_noise,
                "noise_ratio": noise_ratio,
                "silhouette": silhouette,
                "balanced_score": silhouette * (1 - noise_ratio),
            })

    candidates.sort(key=lambda item: (
        -item["balanced_score"],
        -item["silhouette"],
        item["n_noise"],
        item["eps_meters"],
        item["min_samples"],
    ))
    top_candidates = [{
        "rank": rank,
        # Compatibility field: eps is now expressed in meters.
        "eps": item["eps_meters"],
        "eps_meters": item["eps_meters"],
        "eps_kilometers": round(item["eps_meters"] / 1000, 3),
        "min_samples": item["min_samples"],
        "silhouette": round(item["silhouette"], 4),
        "balanced_score": round(item["balanced_score"], 4),
        "n_clusters": item["n_clusters"],
        "n_noise": item["n_noise"],
        "noise_ratio": round(item["noise_ratio"], 4),
        "noise_percent": round(item["noise_ratio"] * 100, 1),
    } for rank, item in enumerate(candidates[:5], start=1)]

    return jsonify({
        "total_points": n,
        "combinations_evaluated": len(EPS_VALUES_METERS) * len(MIN_SAMPLES_VALUES),
        "candidates": top_candidates,
    })

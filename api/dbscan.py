"""POST /api/dbscan — run DBSCAN clustering with user params. POST /api/dbscan/optimal — grid search best eps & min_samples via silhouette score."""
import math

from flask import jsonify, request

from api import api_bp
from config import DB_PATH
from utils.data_loader import load_data
from utils.filtering import apply_filters


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

    # Parse DBSCAN params — user enters eps in degrees, convert to radians for haversine
    eps_degrees = float(body.get("eps", 0.008))
    eps_radians = math.radians(eps_degrees)
    min_samples = int(body.get("min_samples", 4))

    df, _ = load_data(DB_PATH)
    filtered = apply_filters(df, **filters)

    # Override DBSCAN params temporarily
    import utils.clustering as cl
    import numpy as np

    data = filtered.dropna(subset=["lat", "lon"]).copy()
    if data.empty:
        return jsonify({"n_clusters": 0, "n_noise": 0, "n_total": 0, "points": [], "summary": [], "cluster_details": []})

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
    })


@api_bp.route("/dbscan/optimal", methods=["POST"])
def dbscan_optimal():
    """Grid search eps × min_samples maximizing silhouette score (haversine)."""
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

    df, _ = load_data(DB_PATH)
    filtered = apply_filters(df, **filters)
    data = filtered.dropna(subset=["lat", "lon"]).copy()

    if data.empty:
        return jsonify({"best_eps": 0.008, "best_min_samples": 4, "best_score": 0, "best_n_clusters": 0, "results": []})

    coords = np.radians(data[["lat", "lon"]].values)
    n = len(coords)

    # ── Search grid ─────────────────────────────────────────────
    eps_values = [round(v, 4) for v in np.linspace(0.0005, 0.04, 25)]  # degrees (~55m – 4.4km)
    min_samples_values = [2, 3, 4, 5, 6, 7, 8, 10, 12, 15]
    MAX_NOISE_RATIO = 0.5   # reject combos where > 50% points are noise
    MAX_CLUSTERS = 15       # reject combos with too many tiny clusters

    best = {"eps": 0.008, "min_samples": 4, "score": -1, "n_clusters": 0}
    all_results = []

    for eps_deg, ms in itertools.product(eps_values, min_samples_values):
        eps_rad = math.radians(eps_deg)
        model = DBSCAN(eps=eps_rad, min_samples=ms, metric="haversine")
        labels = model.fit_predict(coords)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = int((labels == -1).sum())
        n_clustered = n - n_noise
        noise_ratio = n_noise / n if n > 0 else 0

        # only score combos with 2–15 clusters, ≥ 2 clustered points, and noise ≤ 50%
        score = None
        if 2 <= n_clusters <= MAX_CLUSTERS and n_clustered >= 2 and noise_ratio <= MAX_NOISE_RATIO:
            mask = labels != -1
            score = float(silhouette_score(coords[mask], labels[mask], metric="haversine"))

        result = {
            "eps": eps_deg,
            "min_samples": ms,
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "noise_ratio": round(noise_ratio, 3),
            "silhouette": round(score, 4) if score is not None else None,
        }
        all_results.append(result)

        if score is not None and score > best["score"]:
            best = {"eps": eps_deg, "min_samples": ms, "score": score, "n_clusters": n_clusters}

    return jsonify({
        "best_eps": best["eps"],
        "best_min_samples": best["min_samples"],
        "best_score": round(best["score"], 4),
        "best_n_clusters": best["n_clusters"],
        "results": all_results,
    })

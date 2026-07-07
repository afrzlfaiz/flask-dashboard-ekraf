"""GET /api/chart/<type> — return chart data for frontend Plotly.js."""
from flask import jsonify, request

from api import api_bp
from config import DB_PATH, KECAMATAN_LIST
from utils.data_loader import load_data
from utils.filtering import apply_filters

KOTA_MALANG = set(KECAMATAN_LIST)


def _get_filtered():
    df, _ = load_data(DB_PATH)
    return apply_filters(
        df,
        kecamatan_list=request.args.getlist("kecamatan") or None,
        kelurahan_list=request.args.getlist("kelurahan") or None,
        subsektor_list=request.args.getlist("subsektor") or None,
        search_text=request.args.get("search", ""),
    )


@api_bp.route("/chart/kecamatan")
def chart_kecamatan():
    df = _get_filtered()
    counts = df.groupby("Kecamatan").size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False)
    # Only Malang city kecamatans in donut; rest grouped as "Lainnya"
    labels, values = [], []
    lainnya = 0
    for _, row in counts.iterrows():
        if row["Kecamatan"] in KOTA_MALANG:
            labels.append(row["Kecamatan"])
            values.append(int(row["Jumlah"]))
        else:
            lainnya += int(row["Jumlah"])
    if lainnya > 0:
        labels.append("Lainnya")
        values.append(lainnya)
    return jsonify({"labels": labels, "values": values})


@api_bp.route("/chart/kelurahan")
def chart_kelurahan():
    df = _get_filtered()
    counts = df.groupby("Kelurahan").size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False).head(10)
    return jsonify({
        "labels": counts["Kelurahan"].tolist(),
        "values": counts["Jumlah"].tolist(),
    })


@api_bp.route("/chart/subsektor")
def chart_subsektor():
    df = _get_filtered()
    counts = df.groupby("Sub Sektor").size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False)
    return jsonify({
        "labels": counts["Sub Sektor"].tolist(),
        "values": counts["Jumlah"].tolist(),
    })

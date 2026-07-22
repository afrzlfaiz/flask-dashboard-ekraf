"""GET /api/chart/<type> — return chart data for frontend Plotly.js."""
from flask import jsonify, request
from flask_login import current_user

from api import api_bp
from config import DATABASE_URL, KECAMATAN_LIST
from utils.data_loader import load_data
from utils.filtering import apply_filters

KOTA_MALANG = set(KECAMATAN_LIST)


def _get_filtered():
    df, _ = load_data(DATABASE_URL)
    return apply_filters(
        df,
        kecamatan_list=request.args.getlist("kecamatan") or None,
        kelurahan_list=request.args.getlist("kelurahan") or None,
        subsektor_list=request.args.getlist("subsektor") or None,
        search_text=request.args.get("search", "") if current_user.is_authenticated else "",
    )


def _kecamatan_data(df):
    counts = df.groupby("Kecamatan").size().reset_index(name="Jumlah").sort_values("Jumlah", ascending=False)
    labels, values, lainnya = [], [], 0
    for _, row in counts.iterrows():
        if row["Kecamatan"] in KOTA_MALANG:
            labels.append(row["Kecamatan"])
            values.append(int(row["Jumlah"]))
        else:
            lainnya += int(row["Jumlah"])
    if lainnya:
        labels.append("Lainnya")
        values.append(lainnya)
    return {"labels": labels, "values": values}


def _group_data(df, column, limit=None):
    counts = df.groupby(column).size().sort_values(ascending=False)
    if limit:
        counts = counts.head(limit)
    return {"labels": counts.index.tolist(), "values": counts.astype(int).tolist()}


@api_bp.route("/charts")
def charts():
    df = _get_filtered()
    return jsonify({
        "kecamatan": _kecamatan_data(df),
        "kelurahan": _group_data(df, "Kelurahan", 10),
        "subsektor": _group_data(df, "Sub Sektor"),
    })


@api_bp.route("/chart/kecamatan")
def chart_kecamatan():
    return jsonify(_kecamatan_data(_get_filtered()))


@api_bp.route("/chart/kelurahan")
def chart_kelurahan():
    return jsonify(_group_data(_get_filtered(), "Kelurahan", 10))


@api_bp.route("/chart/subsektor")
def chart_subsektor():
    return jsonify(_group_data(_get_filtered(), "Sub Sektor"))

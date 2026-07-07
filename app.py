"""
Dashboard Spasial Ekonomi Kreatif Kota Malang
Flask + Bootstrap 5 + Leaflet.js + Plotly.js + DataTables
"""
from flask import Flask, render_template
from flask_cors import CORS

from api import api_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Register API blueprint
    app.register_blueprint(api_bp)

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    # Clean URLs for SPA navigation
    for page in ["peta", "clustering", "statistik", "tabel", "kelola", "tentang"]:
        app.add_url_rule(f"/{page}", f"page_{page}", lambda p=page: render_template("dashboard.html", page=p))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)

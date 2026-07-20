"""API Blueprint — JSON endpoints for the dashboard frontend."""
from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

from api import dashboard, filter, dbscan, chart, table, crud, upload, auth  # noqa: E402, F401

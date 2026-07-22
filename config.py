"""
Konstanta global untuk Dashboard Spasial Ekonomi Kreatif Kota Malang.
Tema mengikuti DESIGN.md — "Spatial Creative Index" design system.

Konfigurasi sensitif dibaca dari environment variables (.env).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(value: str) -> str:
    """Resolve a project-relative filesystem path."""
    path = Path(value)
    return str(path if path.is_absolute() else PROJECT_ROOT / path)

# ── Flask Core ─────────────────────────────────────────────────
FLASK_ENV = os.getenv("FLASK_ENV", "production").strip().lower()
IS_PRODUCTION = FLASK_ENV == "production"
DEBUG = _env_bool("FLASK_DEBUG", False)
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY wajib diisi melalui environment atau file .env.")
if IS_PRODUCTION and (DEBUG or SECRET_KEY.startswith("change-me")):
    raise RuntimeError("Konfigurasi production tidak aman: nonaktifkan debug dan gunakan SECRET_KEY acak.")

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
if not 1 <= SESSION_TIMEOUT_MINUTES <= 1440:
    raise RuntimeError("SESSION_TIMEOUT_MINUTES harus berada pada rentang 1–1440 menit.")
if SESSION_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
    raise RuntimeError("SESSION_COOKIE_SAMESITE harus bernilai Lax, Strict, atau None.")
if IS_PRODUCTION and (len(SECRET_KEY) < 32 or not SESSION_COOKIE_SECURE):
    raise RuntimeError("Production memerlukan SECRET_KEY minimal 32 karakter dan cookie sesi Secure.")

# ── Server ─────────────────────────────────────────────────────
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
# ── Database ────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
    raise RuntimeError("DATABASE_URL PostgreSQL wajib diisi melalui environment atau file .env.")
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "public").strip()
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
if not DATABASE_SCHEMA.replace("_", "").isalnum():
    raise RuntimeError("DATABASE_SCHEMA tidak valid.")
if not 1 <= DATABASE_POOL_SIZE <= 20:
    raise RuntimeError("DATABASE_POOL_SIZE harus berada pada rentang 1–20.")
GEOJSON_DIR = _resolve_path(os.getenv("GEOJSON_DIR", "geojson"))
LOG_DIR = _resolve_path(os.getenv("LOG_DIR", "logs"))

# ── CORS ────────────────────────────────────────────────────────
_origins_value = os.getenv("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = _origins_value or (
    "http://localhost:5000,http://127.0.0.1:5000,http://localhost" if not IS_PRODUCTION else ""
)
CORS_SUPPORTS_CREDENTIALS = _env_bool("CORS_SUPPORTS_CREDENTIALS", False)
if IS_PRODUCTION and "*" in {origin.strip() for origin in ALLOWED_ORIGINS.split(",")}:
    raise RuntimeError("Wildcard CORS tidak diizinkan pada production.")

# ── Upload ──────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_ROWS = int(os.getenv("MAX_UPLOAD_ROWS", "5000"))
MAX_UPLOAD_UNCOMPRESSED_MB = int(os.getenv("MAX_UPLOAD_UNCOMPRESSED_MB", "100"))
if MAX_UPLOAD_SIZE_MB <= 0 or MAX_UPLOAD_ROWS <= 0 or MAX_UPLOAD_UNCOMPRESSED_MB <= 0:
    raise RuntimeError("Batas ukuran upload dan jumlah baris harus lebih besar dari nol.")
ALLOWED_UPLOAD_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
    "application/zip",
    "application/x-zip-compressed",
}

# ── Kecamatan (urutan sesuai spesifikasi PROJECT.md) ───────────
KECAMATAN_LIST = [
    "Klojen",
    "Lowokwaru",
    "Blimbing",
    "Sukun",
    "Kedungkandang",
]

# ── Warna 17 subsektor (palette qualitative distinct) ──────────
SUBSECTOR_COLORS = {
    "1) Arsitektur":              "#1f77b4",  # blue
    "2) Seni Rupa":               "#ff7f0e",  # orange
    "3) Desain Produk":           "#2ca02c",  # green
    "4) Film, Animasi, & Video":  "#d62728",  # red
    "5) Fotografi":               "#9467bd",  # purple
    "6) Musik":                   "#8c564b",  # brown
    "7) Desain Interior":         "#e377c2",  # pink
    "8) Kuliner":                 "#7f7f7f",  # gray
    "9) Fesyen":                  "#bcbd22",  # olive
    "10) DKV":                    "#17becf",  # cyan
    "11) Televisi & Radio":       "#aec7e8",  # light blue
    "12) Kriya":                  "#ffbb78",  # light orange
    "13) Seni Pertunjukan":       "#98df8a",  # light green
    "14) Penerbitan":             "#ff9896",  # light red
    "15) Aplikasi":               "#c5b0d5",  # light purple
    "16) Game Developer":         "#c49c94",  # light brown
    "17) Periklanan":             "#f7b6d2",  # light pink
}

# ── Design System Colors (DESIGN.md) ──────────────────────────
# Surface / Background
SURFACE           = "#F4FAFD"   # Main dashboard background
SURFACE_DIM       = "#D4DBDD"
SURFACE_BRIGHT    = "#F4FAFD"
SURFACE_LOWEST    = "#FFFFFF"   # Card fill, map base
SURFACE_LOW        = "#EEF5F7"
SURFACE_CONTAINER  = "#E8EFF1"  # Sidebar background
SURFACE_CONTAINER_HIGH  = "#E2E9EC"
SURFACE_CONTAINER_HIGHEST = "#DDE4E6"

# On-surface (text)
ON_SURFACE         = "#161D1F"   # Primary text
ON_SURFACE_VARIANT = "#424752"   # Secondary text, labels

# Inverse
INVERSE_SURFACE    = "#2B3234"
INVERSE_ON_SURFACE = "#EBF2F4"

# Outline / Border
OUTLINE         = "#727784"
OUTLINE_VARIANT = "#C2C6D4"
CARD_BORDER     = "#E9ECEF"    # Card border (dari component spec)

# Primary
SURFACE_TINT          = "#115CB9"
PRIMARY               = "#003F87"
ON_PRIMARY            = "#FFFFFF"
PRIMARY_CONTAINER     = "#0056B3"   # High-intent actions, active states
ON_PRIMARY_CONTAINER  = "#BBD0FF"
INVERSE_PRIMARY       = "#ACC7FF"

# Primary fixed
PRIMARY_FIXED       = "#D7E2FF"
PRIMARY_FIXED_DIM   = "#ACC7FF"
ON_PRIMARY_FIXED    = "#001A40"
ON_PRIMARY_FIXED_VARIANT = "#004491"

# Secondary
SECONDARY               = "#5C5F60"
ON_SECONDARY            = "#FFFFFF"
SECONDARY_CONTAINER     = "#E1E3E4"
ON_SECONDARY_CONTAINER  = "#626566"

# Tertiary
TERTIARY               = "#404242"
ON_TERTIARY            = "#FFFFFF"
TERTIARY_CONTAINER     = "#575959"
ON_TERTIARY_CONTAINER  = "#CFD0D0"

# Error
ERROR         = "#BA1A1A"
ON_ERROR      = "#FFFFFF"
ERROR_CONTAINER = "#FFDAD6"
ON_ERROR_CONTAINER = "#93000A"

# ── DBSCAN parameters (main.ipynb cell e71804fa) ──────────────
DBSCAN_EPS = 500 / 6_371_000      # 500 meters in radians
DBSCAN_MIN_SAMPLES = 4
DBSCAN_METRIC = "haversine"

# ── Kecamatan boundary overlay ───────────────────────────────────
KECAMATAN_GEOJSON_PATHS = {
    "Klojen":         "id3573030_klojen.geojson",
    "Lowokwaru":      "id3573050_lowokwaru.geojson",
    "Blimbing":       "id3573040_blimbing.geojson",
    "Sukun":          "id3573020_sukun.geojson",
    "Kedungkandang":  "id3573010_kedungkandang.geojson",
}

"""
Konstanta global untuk Dashboard Spasial Ekonomi Kreatif Kota Malang.
Tema mengikuti DESIGN.md — "Spatial Creative Index" design system.
"""

# ── Database ────────────────────────────────────────────────────
DB_PATH = "data/ekraf.db"
GEOJSON_DIR = "geojson"

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

"""
Migrasi data dari Excel multi-sheet ke SQLite.
Jalankan dari folder project root:
    python data/migrate_to_db.py

Atau dari folder data:
    cd data && python migrate_to_db.py

- Buat / rebuild ekraf.db dari ekraf.xlsx
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Paths relatif terhadap folder data/
DATA_DIR = Path(__file__).parent
PROJECT_ROOT = DATA_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
EXCEL_PATH = DATA_DIR / "ekraf.xlsx"
DB_PATH = DATA_DIR / "ekraf.db"

# Kolom yang tidak disimpan ke DB
EXCLUDE_COLS = ["No.", "url"]

# ── Hapus DB lama jika ada ─────────────────────────────
if DB_PATH.exists():
    DB_PATH.unlink()
    print(f"✓ DB lama dihapus: {DB_PATH}")

# ── Buat tabel ─────────────────────────────────────────
conn = sqlite3.connect(str(DB_PATH))
conn.execute("""
    CREATE TABLE pelaku_ekraf (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        "Nama Narasumber" TEXT,
        "Nama Usaha" TEXT,
        "Alamat" TEXT,
        "Kecamatan" TEXT,
        "Kelurahan" TEXT,
        "No Telp" TEXT,
        "Sub Sektor" TEXT,
        "Kategori Usaha" TEXT,
        "Tahun Berdiri" INTEGER,
        "Email" TEXT,
        "lat" REAL,
        "lon" REAL,
        "Sheet" TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        deleted_at TEXT,
        deleted_by INTEGER,
        created_at TEXT,
        created_by INTEGER,
        updated_at TEXT,
        updated_by INTEGER,
        import_batch_id TEXT
    )
""")

# ── Import semua sheet dari Excel ──────────────────────
sheets = pd.read_excel(EXCEL_PATH, sheet_name=None)
total = 0
for sheet, df in sheets.items():
    df["Sheet"] = sheet
    keep_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    df[keep_cols].to_sql("pelaku_ekraf", conn, if_exists="append", index=False)
    print(f"✓ {sheet}: {len(df)} baris")
    total += len(df)

conn.commit()
conn.close()

# Tambahkan tabel keamanan, audit, dan staging secara idempotent.
from utils.database import initialize_database  # noqa: E402

initialize_database(str(DB_PATH))

print(f"\n✓ Total: {total} baris → {DB_PATH}")

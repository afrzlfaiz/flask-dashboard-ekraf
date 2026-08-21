#!/usr/bin/env python3
"""Import one annual Ekraf survey workbook into its own database period."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from io import BytesIO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402

from config import SURVEY_DATA_PATH, SURVEY_SHEET_NAME  # noqa: E402
from utils.database import initialize_database  # noqa: E402
from utils.survey_loader import SurveyPeriodExistsError, import_survey_period  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=SURVEY_DATA_PATH, help="Lokasi workbook XLSX")
    parser.add_argument("--year", type=int, default=2026, help="Tahun survei")
    parser.add_argument("--sheet", default=SURVEY_SHEET_NAME, help="Nama sheet survei")
    parser.add_argument("--label", default=None, help="Label periode pada dashboard")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"File survei tidak ditemukan: {path}")
    raw_bytes = path.read_bytes()
    try:
        dataframe = pd.read_excel(BytesIO(raw_bytes), sheet_name=args.sheet, engine="openpyxl")
    except ValueError as error:
        raise SystemExit(f"Sheet survei '{args.sheet}' tidak ditemukan.") from error

    initialize_database()
    try:
        period = import_survey_period(
            dataframe,
            survey_year=args.year,
            label=args.label or f"Survei Tahunan Ekraf {args.year}",
            source_filename=path.name,
            source_sheet=args.sheet,
            file_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        )
    except SurveyPeriodExistsError as error:
        raise SystemExit(str(error)) from error
    print(
        f"Periode {period['survey_year']} tersimpan: "
        f"{period['rows']} baris, {period['valid_rows']} observasi model."
    )


if __name__ == "__main__":
    main()

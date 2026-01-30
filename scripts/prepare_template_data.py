#!/usr/bin/env python3
"""Create empty template CSVs for raw inputs with expected headers."""

from __future__ import annotations

import csv
from pathlib import Path


def write_csv(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)


def main() -> int:
    # Zillow templates (monthly columns are not added here)
    write_csv(Path("data/raw/zillow/zhvi_state.csv"), ["RegionName", "2020-01"])
    write_csv(Path("data/raw/zillow/zori_state.csv"), ["RegionName", "2020-01"])

    # HCD APR template
    write_csv(
        Path("data/raw/hcd_apr/apr_raw.csv"),
        ["report_year", "units_completed_total"],
    )

    # DOF E-5 template
    write_csv(
        Path("data/raw/dof_e5/e5_state.csv"),
        ["year", "population", "housing_units"],
    )

    # ACS template
    write_csv(Path("data/raw/acs/acs_state.csv"), ["year", "vacancy_rate", "renter_share"])

    print("Wrote template CSVs to data/raw/*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

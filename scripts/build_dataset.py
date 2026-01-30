#!/usr/bin/env python3
"""Build data/processed/ca_state_annual.csv from raw sources.

This script does not download data. It expects raw CSVs placed in data/raw/*
according to config/data_build.yaml.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


try:
    import yaml
except Exception as exc:  # pragma: no cover - environment dependent
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise


@dataclass
class Config:
    inputs: Dict[str, Path]
    zillow_region_names: List[str]
    zillow_match_columns: List[str]
    zillow_first_match_only: bool
    hcd_apr: Dict[str, str]
    dof_e5: Dict[str, str]
    acs: Dict[str, str]
    output_path: Path
    join_type: str
    min_months: int


def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    inputs = {k: Path(v) for k, v in raw["inputs"].items()}
    return Config(
        inputs=inputs,
        zillow_region_names=raw["zillow"]["region_names"],
        zillow_match_columns=raw["zillow"]["match_columns"],
        zillow_first_match_only=bool(raw["zillow"]["first_match_only"]),
        hcd_apr=raw["hcd_apr"],
        dof_e5=raw["dof_e5"],
        acs=raw["acs"],
        output_path=Path(raw["output"]["path"]),
        join_type=raw["output"]["join"],
        min_months=int(raw["annualize"]["min_months"]),
    )


def read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def parse_month_columns(header: List[str]) -> List[Tuple[str, str]]:
    # Returns list of (year, colname)
    out = []
    for col in header:
        if len(col) == 7 and col[4] == "-":
            year, month = col.split("-")
            if year.isdigit() and month.isdigit():
                out.append((year, col))
        elif len(col) == 10 and col[4] == "-" and col[7] == "-":
            year, month, _day = col.split("-")
            if year.isdigit() and month.isdigit():
                out.append((year, col))
    return out


def zillow_annual(
    path: Path,
    region_names: List[str],
    match_columns: List[str],
    first_match_only: bool,
    min_months: int,
) -> Dict[int, float]:
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"Empty file: {path}")

    header = list(rows[0].keys())
    month_cols = parse_month_columns(header)
    if not month_cols:
        raise ValueError(f"No monthly columns found in {path}")

    matches = []
    for row in rows:
        if any(row.get(col) in region_names for col in match_columns):
            matches.append(row)
            if first_match_only:
                break

    if not matches:
        raise ValueError(
            f"No match in {path} for columns {match_columns} with values {region_names}"
        )

    # If multiple matches, average them
    annual_vals: Dict[int, List[float]] = defaultdict(list)
    for row in matches:
        for year_str, col in month_cols:
            val = row.get(col, "")
            if val == "":
                continue
            annual_vals[int(year_str)].append(float(val))

    annual = {}
    for year, values in annual_vals.items():
        if len(values) < min_months:
            continue
        annual[year] = sum(values) / len(values)
    return annual


def series_from_csv(path: Path, mapping: Dict[str, str], series_name: str) -> Dict[int, float]:
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"Empty file: {path}")

    year_col = mapping["year"]
    value_col = mapping[series_name]

    out = {}
    for row in rows:
        if row.get(year_col, "") == "":
            continue
        year = int(row[year_col])
        value = row.get(value_col, "")
        if value == "":
            continue
        out[year] = float(value)
    return out


def sum_series_from_csv(path: Path, mapping: Dict[str, str], series_name: str) -> Dict[int, float]:
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"Empty file: {path}")

    year_col = mapping["year"]
    value_col = mapping[series_name]

    out: Dict[int, float] = defaultdict(float)
    for row in rows:
        if row.get(year_col, "") == "":
            continue
        year = int(row[year_col])
        value = row.get(value_col, "")
        if value == "":
            continue
        out[year] += float(value)
    return dict(out)


def sum_series_from_csv_cols(path: Path, mapping: Dict[str, Any], cols_key: str) -> Dict[int, float]:
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"Empty file: {path}")

    year_col = mapping["year"]
    value_cols = mapping[cols_key]

    out: Dict[int, float] = defaultdict(float)
    for row in rows:
        raw_year = row.get(year_col, "")
        if raw_year in ("", None, "NULL"):
            continue
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        total = 0.0
        for col in value_cols:
            val = row.get(col, "")
            if val == "":
                continue
            try:
                total += float(val)
            except (TypeError, ValueError):
                # Skip non-numeric entries (e.g., dates)
                continue
        out[year] += total
    return dict(out)


def join_years(series: Dict[str, Dict[int, float]], join_type: str) -> List[int]:
    sets = [set(s.keys()) for s in series.values()]
    if not sets:
        return []
    if join_type == "inner":
        years = set.intersection(*sets)
    elif join_type == "outer":
        years = set.union(*sets)
    else:
        raise ValueError("join must be 'inner' or 'outer'")
    return sorted(years)


def report_series(series: Dict[str, Dict[int, float]]) -> None:
    print("Series coverage report:")
    for name, data in series.items():
        if not data:
            print(f"- {name}: empty")
            continue
        years = sorted(data.keys())
        print(f"- {name}: {years[0]} to {years[-1]} ({len(years)} years)")


def main() -> int:
    cfg = load_config(Path("config/data_build.yaml"))

    zhvi = zillow_annual(
        cfg.inputs["zillow_zhvi"],
        cfg.zillow_region_names,
        cfg.zillow_match_columns,
        cfg.zillow_first_match_only,
        cfg.min_months,
    )
    zori = zillow_annual(
        cfg.inputs["zillow_zori"],
        cfg.zillow_region_names,
        cfg.zillow_match_columns,
        cfg.zillow_first_match_only,
        cfg.min_months,
    )
    if "completions_cols" in cfg.hcd_apr:
        completions = sum_series_from_csv_cols(cfg.inputs["hcd_apr"], cfg.hcd_apr, "completions_cols")
    else:
        completions = sum_series_from_csv(cfg.inputs["hcd_apr"], cfg.hcd_apr, "completions")
    population = series_from_csv(cfg.inputs["dof_e5"], cfg.dof_e5, "population")
    housing_units = series_from_csv(cfg.inputs["dof_e5"], cfg.dof_e5, "housing_units")
    vacancy_rate = series_from_csv(cfg.inputs["acs_state"], cfg.acs, "vacancy_rate")

    series = {
        "zhvi": zhvi,
        "zori": zori,
        "completions": completions,
        "population": population,
        "housing_units": housing_units,
        "vacancy_rate": vacancy_rate,
    }

    report_series(series)
    years = join_years(series, cfg.join_type)
    if not years:
        print("No overlapping years across series", file=sys.stderr)
        return 1

    rows = []
    for year in years:
        rows.append(
            {
                "year": year,
                "zhvi": series["zhvi"].get(year, ""),
                "zori": series["zori"].get(year, ""),
                "completions": series["completions"].get(year, ""),
                "population": series["population"].get(year, ""),
                "housing_units": series["housing_units"].get(year, ""),
                "vacancy_rate": series["vacancy_rate"].get(year, ""),
            }
        )

    cfg.output_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg.output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "year",
                "zhvi",
                "zori",
                "completions",
                "population",
                "housing_units",
                "vacancy_rate",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {cfg.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Calibrate model coefficients via OLS on the processed dataset."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import yaml


def read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def to_float(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    return float(value)


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(path: Path, cfg: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)


def build_regression(rows: List[Dict[str, float]], cols: Dict[str, str]):
    # Build year-over-year logs and lagged vacancy
    data = []
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        try:
            g_rent = math.log(cur["rent"] / prev["rent"])
            g_price = math.log(cur["price"] / prev["price"])
            g_h = math.log(cur["housing_units"] / prev["housing_units"])
            g_pop = math.log(cur["population"] / prev["population"])
        except Exception:
            continue

        vac_lag = prev["vacancy_rate"]
        data.append(
            {
                "g_rent": g_rent,
                "g_price": g_price,
                "g_h": g_h,
                "g_pop": g_pop,
                "vac_lag": vac_lag,
            }
        )

    return data


def ols(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    # Returns beta via least squares
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write calibrated coeffs to config/sim_params.yaml")
    args = parser.parse_args()

    cfg = load_config(Path("config/sim_params.yaml"))
    data_path = Path(cfg["data_path"])
    if not data_path.exists():
        raise SystemExit(f"Missing data file: {data_path}")

    rows_raw = read_csv(data_path)
    cols = cfg["columns"]
    rows = []
    for row in rows_raw:
        rows.append(
            {
                "year": int(row[cols["year"]]),
                "price": to_float(row[cols["price"]]),
                "rent": to_float(row[cols["rent"]]),
                "housing_units": to_float(row[cols["housing_units"]]),
                "population": to_float(row[cols["population"]]),
                "vacancy_rate": to_float(row[cols["vacancy_rate"]]),
            }
        )
    rows.sort(key=lambda r: r["year"])

    data = build_regression(rows, cols)
    if len(data) < 4:
        raise SystemExit("Not enough data to calibrate (need >= 4 years).")

    # Rent equation: g_rent = a0 + a1*g_h + a2*g_pop + a4*vac_lag
    y_r = np.array([d["g_rent"] for d in data])
    X_r = np.column_stack(
        [
            np.ones(len(data)),
            [d["g_h"] for d in data],
            [d["g_pop"] for d in data],
            [d["vac_lag"] for d in data],
        ]
    )
    a0, a1, a2, a4 = ols(y_r, X_r)

    # Price equation: g_price = b0 + b1*g_h + b2*g_pop + b3*g_rent
    y_p = np.array([d["g_price"] for d in data])
    X_p = np.column_stack(
        [
            np.ones(len(data)),
            [d["g_h"] for d in data],
            [d["g_pop"] for d in data],
            [d["g_rent"] for d in data],
        ]
    )
    b0, b1, b2, b3 = ols(y_p, X_p)

    # a3 (tax pass-through) cannot be estimated without a policy shock; keep default.
    a3 = cfg["coeffs"].get("a3", 0.0)

    print("Calibrated coefficients:")
    print(f"a0={a0:.4f}, a1={a1:.4f}, a2={a2:.4f}, a3={a3:.4f}, a4={a4:.4f}")
    print(f"b0={b0:.4f}, b1={b1:.4f}, b2={b2:.4f}, b3={b3:.4f}")

    if args.write:
        cfg["coeffs"]["a0"] = float(a0)
        cfg["coeffs"]["a1"] = float(a1)
        cfg["coeffs"]["a2"] = float(a2)
        cfg["coeffs"]["a3"] = float(a3)
        cfg["coeffs"]["a4"] = float(a4)
        cfg["coeffs"]["b0"] = float(b0)
        cfg["coeffs"]["b1"] = float(b1)
        cfg["coeffs"]["b2"] = float(b2)
        cfg["coeffs"]["b3"] = float(b3)
        save_config(Path("config/sim_params.yaml"), cfg)
        print("Wrote calibrated coeffs to config/sim_params.yaml")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

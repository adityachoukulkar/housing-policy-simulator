#!/usr/bin/env python3
"""Run simple statewide annual housing simulator over a grid of policies."""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any


try:
    import yaml
except Exception as exc:  # pragma: no cover - user environment dependent
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise


@dataclass
class Config:
    data_path: Path
    start_year: int | None
    end_year: int | None
    policy_grid: Dict[str, Any]
    coeffs: Dict[str, float]
    sensitivity: Dict[str, float]
    pass_through: Dict[str, float]
    columns: Dict[str, str]
    output_scenarios: Path
    output_summary: Path


def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    output = raw.get("output", {})
    return Config(
        data_path=Path(raw["data_path"]),
        start_year=raw.get("start_year"),
        end_year=raw.get("end_year"),
        policy_grid=raw["policy_grid"],
        coeffs=raw["coeffs"],
        sensitivity=raw.get("sensitivity", {}),
        pass_through=raw.get("pass_through", {}),
        columns=raw["columns"],
        output_scenarios=Path(output["scenarios"]),
        output_summary=Path(output["summary"]),
    )


def parse_range(value: Any) -> List[float]:
    if isinstance(value, list):
        return [float(v) for v in value]
    if isinstance(value, dict):
        vmin = float(value["min"])
        vmax = float(value["max"])
        step = float(value["step"])
        if step <= 0:
            raise ValueError("step must be positive")
        out = []
        cur = vmin
        # inclusive of max with float tolerance
        while cur <= vmax + 1e-9:
            out.append(round(cur, 10))
            cur += step
        return out
    raise ValueError("policy grid must be a list or a {min,max,step} dict")


def read_csv(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def to_float(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    return float(value)


def annualize_series(rows: List[Dict[str, Any]], cols: Dict[str, str]) -> List[Dict[str, float]]:
    # Expect already-annual data in processed file; just coerce types.
    out = []
    for row in rows:
        out.append(
            {
                "year": int(row[cols["year"]]),
                "price": to_float(row[cols["price"]]),
                "rent": to_float(row[cols["rent"]]),
                "housing_units": to_float(row[cols["housing_units"]]),
                "completions": to_float(row[cols["completions"]]),
                "population": to_float(row[cols["population"]]),
                "vacancy_rate": to_float(row[cols["vacancy_rate"]]),
            }
        )
    out.sort(key=lambda r: r["year"])
    return out


def filter_years(rows: List[Dict[str, float]], start: int | None, end: int | None) -> List[Dict[str, float]]:
    if start is None and end is None:
        return rows
    out = []
    for row in rows:
        if start is not None and row["year"] < start:
            continue
        if end is not None and row["year"] > end:
            continue
        out.append(row)
    return out


def compute_other_change(rows: List[Dict[str, float]]) -> List[float]:
    # Implied change in stock not captured by completions.
    other = [0.0]
    for i in range(1, len(rows)):
        dh = rows[i]["housing_units"] - rows[i - 1]["housing_units"]
        other.append(dh - rows[i]["completions"])
    return other


def simulate(
    rows: List[Dict[str, float]],
    coeffs: Dict[str, float],
    tax_delta: float,
    completions_uplift_pct: float,
    pass_through_cfg: Dict[str, float],
) -> List[Dict[str, float]]:
    if len(rows) < 2:
        raise ValueError("Need at least 2 years of data")

    other_change = compute_other_change(rows)

    a0 = coeffs["a0"]
    a1 = coeffs["a1"]
    a2 = coeffs["a2"]
    a3 = coeffs["a3"]
    a4 = coeffs["a4"]
    b0 = coeffs["b0"]
    b1 = coeffs["b1"]
    b2 = coeffs["b2"]
    b3 = coeffs["b3"]

    # initialize with baseline observed levels
    sim = []
    sim.append(
        {
            "year": rows[0]["year"],
            "price": rows[0]["price"],
            "rent": rows[0]["rent"],
            "housing_units": rows[0]["housing_units"],
        }
    )

    for i in range(1, len(rows)):
        prev = sim[-1]

        # Update housing units with upzoning applied to completions
        completions_adj = rows[i]["completions"] * (1.0 + completions_uplift_pct)
        h_t = prev["housing_units"] + completions_adj + other_change[i]

        # Growth rates
        g_h = math.log(h_t / prev["housing_units"])
        g_pop = math.log(rows[i]["population"] / rows[i - 1]["population"])
        vac_lag = rows[i - 1]["vacancy_rate"]

        # Endogenous pass-through based on vacancy and demand elasticity
        pt_base = pass_through_cfg.get("base", 0.5)
        vac_target = pass_through_cfg.get("vacancy_target", 0.05)
        vac_slope = pass_through_cfg.get("vacancy_slope", 0.0)
        elas_slope = pass_through_cfg.get("elasticity_slope", 0.0)
        demand_elas = pass_through_cfg.get("demand_elasticity", 0.7)

        pt = pt_base + vac_slope * (vac_target - vac_lag) - elas_slope * demand_elas
        pt = max(0.0, min(1.0, pt))

        g_rent = a0 + a1 * g_h + a2 * g_pop + a3 * (pt * tax_delta) + a4 * vac_lag
        g_price = b0 + b1 * g_h + b2 * g_pop + b3 * g_rent

        rent_t = prev["rent"] * math.exp(g_rent)
        price_t = prev["price"] * math.exp(g_price)

        sim.append(
            {
                "year": rows[i]["year"],
                "price": price_t,
                "rent": rent_t,
                "housing_units": h_t,
            }
        )

    return sim


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    cfg = load_config(Path("config/sim_params.yaml"))
    rows_raw = read_csv(cfg.data_path)
    rows = annualize_series(rows_raw, cfg.columns)
    rows = filter_years(rows, cfg.start_year, cfg.end_year)

    if len(rows) < 2:
        print("Not enough data rows after filtering", file=sys.stderr)
        return 1

    tax_values = parse_range(cfg.policy_grid["tax_delta"])
    uplift_values = parse_range(cfg.policy_grid["completions_uplift_pct"])

    # Apply sensitivity multipliers
    pass_through = float(cfg.sensitivity.get("pass_through_rate", 1.0))
    supply_elasticity = float(cfg.sensitivity.get("supply_elasticity", 1.0))
    coeffs = dict(cfg.coeffs)
    coeffs["a3"] = coeffs.get("a3", 0.0) * pass_through
    coeffs["a1"] = coeffs.get("a1", 0.0) * supply_elasticity
    coeffs["b1"] = coeffs.get("b1", 0.0) * supply_elasticity

    # Baseline for deltas
    baseline = simulate(
        rows,
        coeffs,
        tax_delta=0.0,
        completions_uplift_pct=0.0,
        pass_through_cfg=cfg.pass_through,
    )
    baseline_by_year = {r["year"]: r for r in baseline}

    scenario_rows = []
    summary_rows = []

    scenario_id = 0
    for tax in tax_values:
        for uplift in uplift_values:
            scenario_id += 1
            sim = simulate(
                rows,
                coeffs,
                tax_delta=tax,
                completions_uplift_pct=uplift,
                pass_through_cfg=cfg.pass_through,
            )
            for r in sim:
                base = baseline_by_year[r["year"]]
                scenario_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "tax_delta": tax,
                        "completions_uplift_pct": uplift,
                        "year": r["year"],
                        "price": r["price"],
                        "rent": r["rent"],
                        "price_delta_pct": (r["price"] / base["price"] - 1.0) * 100.0,
                        "rent_delta_pct": (r["rent"] / base["rent"] - 1.0) * 100.0,
                    }
                )

            final_year = sim[-1]["year"]
            final = sim[-1]
            base_final = baseline_by_year[final_year]
            summary_rows.append(
                {
                    "scenario_id": scenario_id,
                    "tax_delta": tax,
                    "completions_uplift_pct": uplift,
                    "final_year": final_year,
                    "price": final["price"],
                    "rent": final["rent"],
                    "price_delta_pct": (final["price"] / base_final["price"] - 1.0) * 100.0,
                    "rent_delta_pct": (final["rent"] / base_final["rent"] - 1.0) * 100.0,
                }
            )

    write_csv(
        cfg.output_scenarios,
        scenario_rows,
        [
            "scenario_id",
            "tax_delta",
            "completions_uplift_pct",
            "year",
            "price",
            "rent",
            "price_delta_pct",
            "rent_delta_pct",
        ],
    )
    write_csv(
        cfg.output_summary,
        summary_rows,
        [
            "scenario_id",
            "tax_delta",
            "completions_uplift_pct",
            "final_year",
            "price",
            "rent",
            "price_delta_pct",
            "rent_delta_pct",
        ],
    )

    print(f"Wrote {cfg.output_scenarios} and {cfg.output_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

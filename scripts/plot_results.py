#!/usr/bin/env python3
"""Plot simulator results using Plotly."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

try:
    import pandas as pd
    import plotly.express as px
except Exception as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Missing dependency: plotly/pandas. Install with: pip install plotly pandas") from exc


def read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def to_float(value: str) -> float:
    return float(value) if value not in ("", None) else float("nan")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tax", type=float, default=None, help="Filter to a specific tax_delta")
    parser.add_argument("--uplift", type=float, default=None, help="Filter to a specific completions_uplift_pct")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path("data/processed/scenario_trajectories.csv")
    if not path.exists():
        raise SystemExit("Missing scenario_trajectories.csv. Run simulate.py first.")

    rows = read_csv(path)
    for r in rows:
        r["year"] = int(r["year"])
        r["tax_delta"] = to_float(r["tax_delta"])
        r["completions_uplift_pct"] = to_float(r["completions_uplift_pct"])
        r["price_delta_pct"] = to_float(r["price_delta_pct"])
        r["rent_delta_pct"] = to_float(r["rent_delta_pct"])
        r["tax_delta_label"] = f"{r['tax_delta']*100:.2f}%"
        r["uplift_label"] = f"{r['completions_uplift_pct']*100:.0f}%"

    if args.tax is not None:
        rows = [r for r in rows if abs(r["tax_delta"] - args.tax) < 1e-9]
    if args.uplift is not None:
        rows = [r for r in rows if abs(r["completions_uplift_pct"] - args.uplift) < 1e-9]

    rows_sorted = sorted(rows, key=lambda r: (r["tax_delta"], r["completions_uplift_pct"], r["year"]))

    fig_price = px.line(
        rows_sorted,
        x="year",
        y="price_delta_pct",
        color="tax_delta_label",
        line_dash="uplift_label",
        hover_data={"tax_delta_label": True, "uplift_label": True},
        title="Price % Delta vs Baseline",
    )
    fig_price.update_layout(
        yaxis_tickformat=".1f",
        xaxis_title="year",
        yaxis_title="price_delta_pct (%)",
        legend_title_text="incremental property tax (rentals) / % increase in housing built",
    )
    fig_price.update_traces(
        hovertemplate=(
            "year=%{x}<br>"
            "price_delta=%{y:.2f}%<br>"
            "tax_delta=%{customdata[0]}<br>"
            "% increase in housing built=%{customdata[1]}"
        )
    )
    fig_rent = px.line(
        rows_sorted,
        x="year",
        y="rent_delta_pct",
        color="tax_delta_label",
        line_dash="uplift_label",
        hover_data={"tax_delta_label": True, "uplift_label": True},
        title="Rent % Delta vs Baseline",
    )
    fig_rent.update_layout(
        yaxis_tickformat=".1f",
        xaxis_title="year",
        yaxis_title="rent_delta_pct (%)",
        legend_title_text="incremental property tax (rentals) / % increase in housing built",
    )
    fig_rent.update_traces(
        hovertemplate=(
            "year=%{x}<br>"
            "rent_delta=%{y:.2f}%<br>"
            "tax_delta=%{customdata[0]}<br>"
            "% increase in housing built=%{customdata[1]}"
        )
    )

    out_dir = Path("plots")
    out_dir.mkdir(exist_ok=True)
    fig_price.write_html(out_dir / "price_delta.html")
    fig_rent.write_html(out_dir / "rent_delta.html")

    # Heatmaps from summary (exact grid, no auto-binning)
    summary_path = Path("data/processed/scenario_summary.csv")
    if summary_path.exists():
        srows = read_csv(summary_path)
        for r in srows:
            r["tax_delta"] = to_float(r["tax_delta"])
            r["completions_uplift_pct"] = to_float(r["completions_uplift_pct"])
            r["price_delta_pct"] = to_float(r["price_delta_pct"])
            r["rent_delta_pct"] = to_float(r["rent_delta_pct"])

        df = pd.DataFrame(srows)
        pivot_rent = df.pivot_table(
            index="tax_delta",
            columns="completions_uplift_pct",
            values="rent_delta_pct",
            aggfunc="mean",
        ).sort_index().sort_index(axis=1)
        pivot_price = df.pivot_table(
            index="tax_delta",
            columns="completions_uplift_pct",
            values="price_delta_pct",
            aggfunc="mean",
        ).sort_index().sort_index(axis=1)

        heat_rent = px.imshow(
            pivot_rent,
            labels={"x": "% increase in housing built", "y": "incremental property tax (rentals)", "color": "rent_delta_pct"},
            title="Final-Year Rent % Delta Heatmap",
            aspect="auto",
        )
        heat_rent.update_xaxes(tickformat=".0%")
        heat_rent.update_yaxes(tickformat=".2%")
        heat_rent.update_layout(coloraxis_colorbar_tickformat=".1f")
        heat_rent.update_traces(hovertemplate="uplift=%{x}<br>tax=%{y}<br>rent_delta=%{z:.2f}%")
        heat_price = px.imshow(
            pivot_price,
            labels={"x": "% increase in housing built", "y": "incremental property tax (rentals)", "color": "price_delta_pct"},
            title="Final-Year Price % Delta Heatmap",
            aspect="auto",
        )
        heat_price.update_xaxes(tickformat=".0%")
        heat_price.update_yaxes(tickformat=".2%")
        heat_price.update_layout(coloraxis_colorbar_tickformat=".1f")
        heat_price.update_traces(hovertemplate="uplift=%{x}<br>tax=%{y}<br>price_delta=%{z:.2f}%")
        heat_rent.write_html(out_dir / "rent_heatmap.html")
        heat_price.write_html(out_dir / "price_heatmap.html")

    print("Wrote plots/price_delta.html, plots/rent_delta.html, plots/rent_heatmap.html, plots/price_heatmap.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

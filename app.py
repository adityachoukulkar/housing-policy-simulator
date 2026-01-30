#!/usr/bin/env python3
"""Interactive Streamlit app for the housing policy simulator."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Any, List

import altair as alt
import pandas as pd
import streamlit as st
import yaml


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error(f"Missing data file: {path}. Run build_dataset.py first.")
        st.stop()
    df = pd.read_csv(path)
    return df


def compute_other_change(df: pd.DataFrame) -> List[float]:
    other = [0.0]
    for i in range(1, len(df)):
        dh = df.loc[i, "housing_units"] - df.loc[i - 1, "housing_units"]
        other.append(dh - df.loc[i, "completions"])
    return other


def simulate(df: pd.DataFrame, coeffs: Dict[str, float], policy: Dict[str, float], pass_through: Dict[str, float]) -> pd.DataFrame:
    df = df.sort_values("year").reset_index(drop=True)
    other_change = compute_other_change(df)

    a0 = coeffs["a0"]
    a1 = coeffs["a1"]
    a2 = coeffs["a2"]
    a3 = coeffs["a3"]
    a4 = coeffs["a4"]
    b0 = coeffs["b0"]
    b1 = coeffs["b1"]
    b2 = coeffs["b2"]
    b3 = coeffs["b3"]

    tax_delta = policy["tax_delta"]
    completions_uplift_pct = policy["completions_uplift_pct"]

    rows = []
    rows.append(
        {
            "year": int(df.loc[0, "year"]),
            "price": df.loc[0, "zhvi"],
            "rent": df.loc[0, "zori"],
            "housing_units": df.loc[0, "housing_units"],
        }
    )

    for i in range(1, len(df)):
        prev = rows[-1]

        completions_adj = df.loc[i, "completions"] * (1.0 + completions_uplift_pct)
        h_t = prev["housing_units"] + completions_adj + other_change[i]

        g_h = math.log(h_t / prev["housing_units"])
        g_pop = math.log(df.loc[i, "population"] / df.loc[i - 1, "population"])
        vac_lag = df.loc[i - 1, "vacancy_rate"]

        pt_base = pass_through.get("base", 0.5)
        vac_target = pass_through.get("vacancy_target", 0.05)
        vac_slope = pass_through.get("vacancy_slope", 0.0)
        elas_slope = pass_through.get("elasticity_slope", 0.0)
        demand_elas = pass_through.get("demand_elasticity", 0.7)

        pt = pt_base + vac_slope * (vac_target - vac_lag) - elas_slope * demand_elas
        pt = max(0.0, min(1.0, pt))

        g_rent = a0 + a1 * g_h + a2 * g_pop + a3 * (pt * tax_delta) + a4 * vac_lag
        g_price = b0 + b1 * g_h + b2 * g_pop + b3 * g_rent

        rent_t = prev["rent"] * math.exp(g_rent)
        price_t = prev["price"] * math.exp(g_price)

        rows.append(
            {
                "year": int(df.loc[i, "year"]),
                "price": price_t,
                "rent": rent_t,
                "housing_units": h_t,
                "pass_through": pt,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="Housing Policy Simulator", layout="wide")
    st.title("Housing Policy Simulator (Statewide CA, Annual)")

    cfg = load_config(Path("config/sim_params.yaml"))
    df = read_data(Path(cfg["data_path"]))

    # Sidebar controls
    st.sidebar.header("Policy levers")
    tax_delta = st.sidebar.slider("Tax delta (rental) %", 0.0, 1.0, cfg["policy_grid"]["tax_delta"]["min"] * 100, 0.01) / 100.0
    completions_uplift = st.sidebar.slider("% increase in housing built", 0.0, 50.0, cfg["policy_grid"]["completions_uplift_pct"]["min"] * 100, 1.0) / 100.0

    coeffs = cfg["coeffs"].copy()
    if st.sidebar.checkbox("Show coefficients (advanced)", value=False):
        st.sidebar.header("Coefficients")
        for k in ["a0", "a1", "a2", "a3", "a4", "b0", "b1", "b2", "b3"]:
            coeffs[k] = st.sidebar.number_input(k, value=float(coeffs[k]), format="%.4f")

    st.sidebar.header("Presets")
    preset_options = [
        "High demand elasticity",
        "Low demand elasticity",
        "High pass-through",
        "Low pass-through",
        "Tight market",
        "Slack market",
    ]
    preset_stack = st.sidebar.multiselect("Preset stack", preset_options, default=[])
    apply_presets = st.sidebar.button("Apply presets")
    reset_presets = st.sidebar.button("Reset to defaults")

    st.sidebar.header("Sensitivity")
    pass_through_rate = st.sidebar.slider(
        "Pass-through rate multiplier",
        0.0,
        2.0,
        float(cfg["sensitivity"].get("pass_through_rate", 1.0)),
        0.05,
    )
    supply_elasticity = st.sidebar.slider(
        "Supply elasticity multiplier",
        0.0,
        2.0,
        float(cfg["sensitivity"].get("supply_elasticity", 1.0)),
        0.05,
    )

    coeffs["a3"] *= pass_through_rate
    coeffs["a1"] *= supply_elasticity
    coeffs["b1"] *= supply_elasticity

    st.sidebar.header("Pass-through function")
    pt_cfg = cfg.get("pass_through", {}).copy()
    if reset_presets:
        pt_cfg = cfg.get("pass_through", {}).copy()
    if apply_presets and preset_stack:
        for preset in preset_stack:
            if preset == "High demand elasticity":
                pt_cfg["demand_elasticity"] = 1.2
            elif preset == "Low demand elasticity":
                pt_cfg["demand_elasticity"] = 0.4
            elif preset == "High pass-through":
                pt_cfg["base"] = 0.7
            elif preset == "Low pass-through":
                pt_cfg["base"] = 0.3
            elif preset == "Tight market":
                pt_cfg["vacancy_target"] = 0.04
                pt_cfg["vacancy_slope"] = 3.0
            elif preset == "Slack market":
                pt_cfg["vacancy_target"] = 0.07
                pt_cfg["vacancy_slope"] = 1.0

    pt_cfg["base"] = st.sidebar.slider("Base pass-through", 0.0, 1.0, float(pt_cfg.get("base", 0.5)), 0.01)
    pt_cfg["vacancy_target"] = st.sidebar.slider("Vacancy target", 0.0, 0.2, float(pt_cfg.get("vacancy_target", 0.05)), 0.005)
    pt_cfg["vacancy_slope"] = st.sidebar.slider("Vacancy slope", -5.0, 5.0, float(pt_cfg.get("vacancy_slope", 2.0)), 0.1)
    pt_cfg["elasticity_slope"] = st.sidebar.slider("Elasticity slope", 0.0, 2.0, float(pt_cfg.get("elasticity_slope", 0.1)), 0.05)
    pt_cfg["demand_elasticity"] = st.sidebar.slider("Demand elasticity", 0.0, 2.0, float(pt_cfg.get("demand_elasticity", 0.7)), 0.05)

    policy = {
        "tax_delta": tax_delta,
        "completions_uplift_pct": completions_uplift,
    }

    baseline = simulate(df, coeffs, {"tax_delta": 0.0, "completions_uplift_pct": 0.0}, pt_cfg)
    scenario = simulate(df, coeffs, policy, pt_cfg)

    out = scenario.merge(baseline, on="year", suffixes=("", "_base"))
    out["price_delta_pct"] = (out["price"] / out["price_base"] - 1.0) * 100
    out["rent_delta_pct"] = (out["rent"] / out["rent_base"] - 1.0) * 100

    st.subheader("Scenario deltas vs baseline")
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out["price_delta_pct"] = pd.to_numeric(out["price_delta_pct"], errors="coerce")
    out["rent_delta_pct"] = pd.to_numeric(out["rent_delta_pct"], errors="coerce")

    price_plot = out.dropna(subset=["year", "price_delta_pct"])
    rent_plot = out.dropna(subset=["year", "rent_delta_pct"])

    price_chart = (
        alt.Chart(price_plot, title="Price % Delta vs Baseline")
        .mark_line(point=True)
        .encode(
            x=alt.X("year:Q", title="Year", axis=alt.Axis(format="d")),
            y=alt.Y("price_delta_pct:Q", title="Price delta (%)", axis=alt.Axis(format=".2f")),
        )
        .properties(height=250)
    )
    rent_chart = (
        alt.Chart(rent_plot, title="Rent % Delta vs Baseline")
        .mark_line(point=True)
        .encode(
            x=alt.X("year:Q", title="Year", axis=alt.Axis(format="d")),
            y=alt.Y("rent_delta_pct:Q", title="Rent delta (%)", axis=alt.Axis(format=".2f")),
        )
        .properties(height=250)
    )
    st.altair_chart(price_chart, use_container_width=True)
    st.altair_chart(rent_chart, use_container_width=True)

    st.subheader("Outputs (last year)")
    last = out.iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric("Price delta (%)", f"{last['price_delta_pct']:.2f}")
    col2.metric("Rent delta (%)", f"{last['rent_delta_pct']:.2f}")
    col3.metric("Pass-through (last year)", f"{last['pass_through']:.2f}")

    st.subheader("Underlying series")
    st.dataframe(out[["year", "price", "rent", "price_delta_pct", "rent_delta_pct", "pass_through"]])


if __name__ == "__main__":
    main()

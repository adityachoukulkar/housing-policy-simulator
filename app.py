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


def simulate(
    df: pd.DataFrame,
    coeffs: Dict[str, float],
    policy: Dict[str, float],
    pass_through: Dict[str, float],
    supply_response: Dict[str, float],
    rent_response: Dict[str, float],
) -> pd.DataFrame:
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
    price_model = policy.get("price_model", "growth")
    user_cost = policy.get("user_cost", {})
    uc_real = user_cost.get("real_rate", 0.03)
    uc_tax_base = user_cost.get("property_tax_base", 0.01)
    uc_maint = user_cost.get("maintenance", 0.01)
    uc_dep = user_cost.get("depreciation", 0.01)
    uc_g_r = user_cost.get("expected_rent_growth", 0.02)
    uc_lambda = user_cost.get("rent_capitalization_lambda", 0.0)
    uc_drift = user_cost.get("price_drift", 0.0)
    uc_decay = user_cost.get("momentum_decay", 0.0)
    rr_user_cost = rent_response.get("user_cost_to_rent", 0.0)
    rr_cost_push = rent_response.get("cost_push_to_rent", 0.0)
    sr_elasticity = supply_response.get("price_elasticity", 0.5)
    sr_min = supply_response.get("min_multiplier", 0.8)
    sr_max = supply_response.get("max_multiplier", 1.3)

    rows = []
    rows.append(
        {
            "year": int(df.loc[0, "year"]),
            "price": df.loc[0, "zhvi"],
            "rent": df.loc[0, "zori"],
            "housing_units": df.loc[0, "housing_units"],
        }
    )

    prev_g_price = 0.0
    for i in range(1, len(df)):
        prev = rows[-1]

        supply_mult = 1.0 + sr_elasticity * prev_g_price
        if supply_mult < sr_min:
            supply_mult = sr_min
        if supply_mult > sr_max:
            supply_mult = sr_max
        completions_adj = df.loc[i, "completions"] * (1.0 + completions_uplift_pct) * supply_mult
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

        g_rent_tax = a3 * (pt * tax_delta)
        uc_base = uc_real + uc_tax_base + uc_maint + uc_dep - uc_g_r
        uc_policy = uc_real + (uc_tax_base + tax_delta) + uc_maint + uc_dep - uc_g_r
        uc_delta = uc_policy - uc_base
        cost_push = (uc_tax_base + tax_delta + uc_maint) - (uc_tax_base + uc_maint)
        g_rent = (
            a0
            + a1 * g_h
            + a2 * g_pop
            + g_rent_tax
            + a4 * vac_lag
            + rr_user_cost * uc_delta
            + rr_cost_push * cost_push
        )
        rent_t = prev["rent"] * math.exp(g_rent)
        rent_no_tax = prev["rent"] * math.exp(g_rent - g_rent_tax)
        delta_rent_tax = rent_t - rent_no_tax

        uc = None
        if price_model in ("user_cost", "user_cost_momentum"):
            uc_tax = uc_tax_base + tax_delta
            uc = uc_real + uc_tax + uc_maint + uc_dep - uc_g_r
            if uc <= 0:
                uc = 1e-6
            price_t = rent_t / uc
            if uc_lambda and delta_rent_tax:
                price_t = price_t + uc_lambda * (delta_rent_tax / uc)
            if price_model == "user_cost_momentum":
                kappa0 = user_cost.get("momentum_kappa", 0.0)
                kappa_t = kappa0 * math.exp(-uc_decay * (i - 1))
                price_t = price_t * math.exp(kappa_t * g_rent)
            if uc_drift:
                price_t = price_t * math.exp(uc_drift)
        else:
            g_price = b0 + b1 * g_h + b2 * g_pop + b3 * g_rent
            price_t = prev["price"] * math.exp(g_price)
        prev_g_price = math.log(price_t / prev["price"])

        rows.append(
            {
                "year": int(df.loc[i, "year"]),
                "price": price_t,
                "rent": rent_t,
                "housing_units": h_t,
                "pass_through": pt,
                "user_cost": uc,
                "pr_ratio": price_t / rent_t if rent_t else None,
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
    tax_delta = st.sidebar.slider(
        "Incremental property tax (rentals) (%)",
        0.0,
        3.0,
        cfg["policy_grid"]["tax_delta"]["min"] * 100,
        0.01,
    ) / 100.0
    completions_uplift = st.sidebar.slider(
        "% increase in housing built",
        0.0,
        100.0,
        cfg["policy_grid"]["completions_uplift_pct"]["min"] * 100,
        1.0,
    ) / 100.0

    st.sidebar.header("Price model")
    price_model = st.sidebar.radio(
        "Price model",
        ["user_cost_momentum", "growth"],
        index=0 if cfg.get("price_model", "growth") == "user_cost_momentum" else 1,
    )
    uc_cfg = cfg.get("user_cost", {}).copy()
    if price_model in ("user_cost_momentum",):
        st.sidebar.caption("User-cost parameters (annual)")
        uc_cfg["real_rate"] = st.sidebar.slider("Real interest rate (%)", 0.0, 6.0, float(uc_cfg.get("real_rate", 0.03)) * 100, 0.25) / 100.0
        uc_cfg["property_tax_base"] = st.sidebar.slider("Baseline property tax (%)", 0.8, 2.0, float(uc_cfg.get("property_tax_base", 0.01)) * 100, 0.05) / 100.0
        uc_cfg["maintenance"] = st.sidebar.slider("Maintenance/insurance (%)", 0.5, 3.0, float(uc_cfg.get("maintenance", 0.01)) * 100, 0.05) / 100.0
        uc_cfg["depreciation"] = 0.02
        uc_cfg["expected_rent_growth"] = 0.0
        if price_model == "user_cost_momentum":
            uc_cfg["momentum_kappa"] = st.sidebar.slider("Rent momentum (kappa)", 0.0, 3.0, float(uc_cfg.get("momentum_kappa", 0.0)), 0.1)
            uc_cfg["momentum_decay"] = 0.0
            uc_cfg["price_drift"] = st.sidebar.slider("Price drift (%)", 0.0, 2.0, float(uc_cfg.get("price_drift", 0.003)) * 100, 0.05) / 100.0

        uc_min = uc_cfg["real_rate"] + uc_cfg["property_tax_base"] + uc_cfg["maintenance"] + uc_cfg["depreciation"]
        if uc_cfg["expected_rent_growth"] >= uc_min:
            st.sidebar.error(
                "Expected rent growth is too high relative to carrying costs. "
                "This makes user cost ≤ 0 and breaks the price-to-rent model."
            )
            st.stop()

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
    if "active_presets" not in st.session_state:
        st.session_state.active_presets = set()

    preset_stack = list(st.session_state.active_presets)

    st.sidebar.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            width: 100%;
            border-radius: 6px;
            border: 1px solid #d0d0d0;
            padding: 0.25rem 0.4rem;
            font-size: 0.85rem;
        }
        .reset-button > button {
            background: #f2f4f7;
            color: #1f2937;
            border: 1px solid #cbd5e1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cols = st.sidebar.columns(2)
    for i, preset in enumerate(preset_options):
        col = cols[i % 2]
        is_active = preset in st.session_state.active_presets
        label = f"✅ {preset}" if is_active else preset
        if col.button(label, key=f"preset_{preset}"):
            if is_active:
                st.session_state.active_presets.remove(preset)
            else:
                st.session_state.active_presets.add(preset)
            st.rerun()

    with st.sidebar.container():
        st.markdown('<div class="reset-button">', unsafe_allow_html=True)
        reset_presets = st.button("Reset to defaults")
        st.markdown("</div>", unsafe_allow_html=True)

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
    if preset_stack:
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
        "price_model": price_model,
        "user_cost": uc_cfg,
    }

    baseline = simulate(
        df,
        coeffs,
        {
            "tax_delta": 0.0,
            "completions_uplift_pct": 0.0,
            "price_model": price_model,
            "user_cost": uc_cfg,
        },
        pt_cfg,
        cfg.get("supply_response", {}),
        cfg.get("rent_response", {}),
    )
    scenario = simulate(df, coeffs, policy, pt_cfg, cfg.get("supply_response", {}), cfg.get("rent_response", {}))

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
    if "user_cost" in last and pd.notna(last["user_cost"]):
        st.caption(f"User cost (last year): {last['user_cost']:.3f}")
    if "pr_ratio" in last and pd.notna(last["pr_ratio"]):
        st.caption(f"Price-to-rent (last year): {last['pr_ratio']:.2f}")

    st.subheader("Explainer: pass-through mechanics")
    st.info(
        """
The pass-through rate φ_t is higher when markets are tight (low vacancy) and lower
when demand is more elastic. In this model:

- Tight market (vacancy below target) → higher φ_t
- Slack market (vacancy above target) → lower φ_t
- High demand elasticity → lower φ_t
- Low demand elasticity → higher φ_t

This means tax increases have a larger rent impact in tight, inelastic markets.
"""
    )

    st.subheader("Underlying series")
    display_df = out[["year", "price", "rent", "price_delta_pct", "rent_delta_pct", "pass_through", "user_cost", "pr_ratio"]].copy()
    display_df["year"] = display_df["year"].astype(int).astype(str)
    display_df["rent"] = display_df["rent"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
    display_df["price"] = display_df["price"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
    display_df["price_delta_pct"] = display_df["price_delta_pct"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    display_df["rent_delta_pct"] = display_df["rent_delta_pct"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    display_df["pass_through"] = display_df["pass_through"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    display_df["user_cost"] = display_df["user_cost"].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "")
    display_df["pr_ratio"] = display_df["pr_ratio"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    display_df = display_df.fillna("").astype(str)
    st.code(display_df.to_markdown(index=False), language="markdown")


if __name__ == "__main__":
    main()

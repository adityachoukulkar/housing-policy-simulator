# Structural Upgrade: Endogenous Rental Tax Pass-Through

## Goal
Make rental tax pass-through respond to market tightness (vacancy) and demand elasticity, rather than treating it as a fixed coefficient.

## Definitions
- `dTax_rent`: incremental effective tax rate on rental properties (e.g., 0.002 = +0.20%)
- `Vac_t`: vacancy rate at time t (proxy for market tightness)
- `ε_d`: demand elasticity (higher means renters are more price-sensitive)
- `φ_t`: pass-through rate (0 to 1)

## Pass-Through Function
We model pass-through as a bounded function of vacancy and demand elasticity:

```
φ_t = clamp( φ0 + φ1 * (Vac_target − Vac_t) − φ2 * ε_d , 0, 1 )
```

Where:
- `φ0` = base pass-through rate
- `φ1` > 0 increases pass-through when vacancy is below target (tight market)
- `φ2` > 0 reduces pass-through when demand is more elastic
- `Vac_target` is a reference vacancy rate (e.g., 5%)

## Rent Growth Equation (Updated)
Replace the fixed tax term with an endogenous pass-through term:

```
log(R_t / R_{t-1}) = a0
                    + a1 * log(H_t / H_{t-1})
                    + a2 * log(Pop_t / Pop_{t-1})
                    + a3 * (φ_t * dTax_rent)
                    + a4 * Vac_{t-1}
```

Interpretation:
- If vacancy is low, `φ_t` rises and more of the tax increase is passed to renters.
- If demand is more elastic, `φ_t` falls and pass-through is muted.

## Calibration Guidance (Small Data)
With limited time-series data, calibrate in layers:
1) Fix `ε_d` from literature or choose a plausible range (e.g., 0.3–1.5).
2) Set `Vac_target` to the long-run vacancy average (e.g., 5%).
3) Choose `φ0` as a baseline (0.3–0.6), then test sensitivity using `φ1` and `φ2`.

## Where This Lives in Code
- `config/sim_params.yaml`:
  - `pass_through.base`
  - `pass_through.vacancy_target`
  - `pass_through.vacancy_slope`
  - `pass_through.elasticity_slope`
  - `pass_through.demand_elasticity`
- `scripts/simulate.py`: computes `φ_t` each year and applies it to the tax term.

## Notes
- This is still reduced-form but grounded in standard incidence intuition.
- The pass-through function is intentionally simple and transparent; you can swap it for a logistic if you want smoother bounds.

# Simple Statewide Simulator (Annual) - Model Spec

## Scope
- Geography: California statewide
- Time step: Annual
- Outcomes: Rent index (ZORI) and price index (ZHVI)
- Policy levers:
  - Incremental property tax rate on rental properties
- % increase in completions (upzoning proxy)

## Core State Variables
- P_t: Home price index (ZHVI, annualized)
- R_t: Rent index (ZORI, annualized)
- H_t: Housing stock (DOF E-5)
- C_t: Completions (HCD APR, statewide)
- M_t: Permits (HCD APR, statewide)
- Pop_t: Population (DOF E-5)
- Vac_t: Vacancy rate (ACS)
- RentShare_t: Renter share (ACS)

## Policy Inputs
- dTax_rent: Incremental effective property tax rate on rentals (e.g., +0.20%)
- completions_uplift_pct: % increase in completions (e.g., +10%)

## Derived Inputs
- C_t' = C_t * (1 + completions_uplift_pct)
- M_t' = M_t * (1 + upzone_pct)
- DeltaH_t = C_t' - Demolitions_t (if unknown, assume 0 or a fixed % of stock)

## Outcome Equations (simple reduced form)

### Rent change
- log(R_t / R_{t-1}) = a0 + a1 * log(H_t / H_{t-1}) + a2 * log(Pop_t / Pop_{t-1})
                         + a3 * dTax_rent + a4 * Vac_{t-1} + e_t

Interpretation:
- a1 < 0 (more housing supply lowers rent growth)
- a2 > 0 (more population raises rent growth)
- a3 >= 0 (tax increase on rentals passes through to rents)
- a4 < 0 (higher vacancy lowers rent growth)

### Price change
- log(P_t / P_{t-1}) = b0 + b1 * log(H_t / H_{t-1}) + b2 * log(Pop_t / Pop_{t-1})
                      + b3 * log(R_t / R_{t-1}) + u_t

Interpretation:
- b1 < 0 (more housing supply lowers price growth)
- b2 > 0 (more population raises price growth)
- b3 > 0 (rents feed into prices)

## Calibration (initial placeholders)
- Use simple regression over 2018+ once data assembled; if insufficient, set
  coefficients based on literature or conservative assumptions and allow user
  overrides.
- Suggested defaults (initial):
  - a1 = -0.5, a2 = 0.8, a3 = 0.5, a4 = -0.2
  - b1 = -0.3, b2 = 0.6, b3 = 0.4

## Outputs
- Annual series for P_t and R_t under baseline and policy scenarios
- Policy deltas: % change in P_t and R_t vs baseline

## Assumptions and Limitations
- Statewide aggregation masks regional heterogeneity
- Property tax pass-through is simplified and user-controlled
- Upzoning is proxied as a % increase in permits/completions

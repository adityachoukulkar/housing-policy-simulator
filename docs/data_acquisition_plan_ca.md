# California (Statewide) Free-Only Data Acquisition Plan

This plan uses Zillow (ZHVI/ZORI) as outcomes, HCD APR for permits/completions, DOF E-5 for stock/population, and ACS for vacancy/renter share. Data is annualized from monthly series where needed.

## 1) Zillow ZHVI (Prices)
- Source: Zillow Research Data
- File (example): `Zhvi_AllHomes_State.csv` or `Zhvi_SingleFamilyResidence_State.csv`
- Geography: CA state row
- Frequency: Monthly; annualize by averaging months in year
- Fields: `RegionName`, `YYYY-MM` columns
- Output: `data/raw/zillow/zhvi_state.csv`

## 2) Zillow ZORI (Rents)
- Source: Zillow Research Data
- File (example): `ZORI_AllHomes_State.csv` or `ZORI_SingleFamilyResidence_State.csv`
- Geography: CA state row
- Frequency: Monthly; annualize by averaging months in year
- Fields: `RegionName`, `YYYY-MM` columns
- Output: `data/raw/zillow/zori_state.csv`

## 3) HCD Annual Progress Report (APR)
- Source: HCD APR open data download
- Geography: Jurisdiction-level; aggregate to statewide
- Frequency: Annual (report year)
- Fields (minimum):
  - `report_year`
  - `units_permitted_total`
  - `units_completed_total`
  - Optional: unit type breakdowns if available
- Output: `data/raw/hcd_apr/apr_raw.csv`

## 4) CA Dept. of Finance E-5 Population & Housing Estimates
- Source: DOF E-5 tables
- Geography: Statewide
- Frequency: Annual
- Fields (minimum):
  - `year`
  - `population`
  - `housing_units`
- Output: `data/raw/dof_e5/e5_state.csv`

## 5) ACS (1-year) Statewide Tables
- Source: Census API
- Geography: Statewide
- Frequency: Annual
- Fields (minimum):
  - Vacancy rate (total / rental)
  - Renter share (% renter-occupied)
- Output: `data/raw/acs/acs_state.csv`

## 6) Optional cross-checks
- FHFA HPI statewide (quarterly): `data/raw/fhfa/hpi_state.csv`
- Census BPS statewide permits: `data/raw/bps/bps_state.csv`

## Annualization Rules
- Zillow monthly series -> annual average (mean of months in year)
- If a year is missing months: drop year or require >= 9 months (configurable)

## Target Unified Dataset
- File: `data/processed/ca_state_annual.csv`
- Columns (minimum):
  - `year`
  - `zhvi`
  - `zori`
  - `permits`
  - `completions`
  - `housing_units`
  - `population`
  - `vacancy_rate`
  - `renter_share`


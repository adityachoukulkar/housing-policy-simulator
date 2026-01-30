# California (Statewide) Free-Only Data Sources

This document lists the minimum free data needed for a simple statewide annual simulator.

## Outcomes

### Zillow ZHVI (home values)
- Level: Statewide (CA), monthly; can be annualized
- Use: Primary price index
- Access: CSV download from Zillow Research Data page
- Notes: Multiple series (all homes, SFR, condo/co-op); pick one and be consistent

### Zillow ZORI (rents)
- Level: Statewide (CA), monthly; can be annualized
- Use: Primary rent index
- Access: CSV download from Zillow Research Data page
- Notes: Multiple series (all homes, SFR, multifamily); pick one and be consistent

### FHFA House Price Index (optional cross-check)
- Level: Statewide (CA), quarterly
- Use: Secondary price series for validation
- Access: FHFA HPI download portal

### HUD Fair Market Rents (optional benchmark)
- Level: County/metro/ZIP (SAFMR), annual
- Use: Policy benchmark rather than market rent series
- Access: HUD USER data portal

## Supply

### HCD Annual Progress Report (APR)
- Level: Jurisdiction-level (cities/counties), annual
- Fields: Applications, entitlements, permits, completions by unit type
- Use: Primary permits/completions series; aggregate to statewide annual totals
- Access: HCD APR open data downloads
- Notes: Coverage improves over time; 2018+ recommended

### Census Building Permits Survey (BPS) (cross-check)
- Level: Statewide, annual
- Fields: Permits by structure type
- Use: Validate statewide permit trend
- Access: Census BPS annual files

## Stock and Demand Fundamentals

### CA Dept. of Finance E-5 Population & Housing Estimates
- Level: Statewide, annual
- Fields: Population, housing units
- Use: Baseline demand and stock
- Access: DOF E-5 tables

### American Community Survey (ACS)
- Level: Statewide, annual (1-year)
- Fields: Tenure, rent, vacancy, household formation, income, unit type
- Use: Renter share, vacancy rates, household growth proxies
- Access: Census API

## Property Tax Context

### CA Board of Equalization (BOE) Annual Report / News Releases
- Level: Statewide, annual
- Fields: Total assessed value, total property tax revenue
- Use: Calibrate baseline effective tax rate
- Access: BOE publications

## Known Free-Only Gaps
- No statewide parcel-level property tax roll or effective tax rates
- No statewide zoning capacity dataset suitable for parcel-accurate upzoning

## Data Coverage Start (recommended)
- 2018 onward (to align with HCD APR coverage)


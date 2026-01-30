# Scripts

## build_all.py
Runs the full pipeline: download -> extract DOF -> build dataset.

Usage:
```
python3 scripts/build_all.py
```

Notes:
- `build_all.py` runs `download_data.py --skip-acs` by default.

## download_data.py
Downloads raw data for the California statewide simulator.

Usage:
```
python3 scripts/download_data.py
```

Notes:
- Set `CENSUS_API_KEY` in your environment to increase ACS API limits.
- Use `--skip-acs` to skip ACS download if you don't have a key yet.
- If a file already exists, it is skipped unless you pass `--force`.

## extract_dof_state.py
Extracts statewide population and housing units from DOF E-5/E-8 Excel files.

Usage:
```
python3 scripts/extract_dof_state.py
```

## prepare_template_data.py
Creates empty template CSVs under `data/raw/*` with expected headers.

Usage:
```
python3 scripts/prepare_template_data.py
```

## build_dataset.py
Builds `data/processed/ca_state_annual.csv` from raw CSVs using
`config/data_build.yaml` mappings.

Usage:
```
python3 scripts/build_dataset.py
```

## simulate.py
Runs the statewide annual simulator over a grid of tax and upzoning percentages.

Usage:
```
python3 scripts/simulate.py
```

Configuration:
- `config/sim_params.yaml` controls coefficient defaults and the policy grid.
- `policy_grid.tax_delta` and `policy_grid.upzone_pct` accept either a list
  or `{min, max, step}` to generate a range.

## calibrate_coeffs.py
Calibrates coefficients via OLS on the processed dataset.

Usage:
```
python3 scripts/calibrate_coeffs.py
```

To write calibrated values to config:
```
python3 scripts/calibrate_coeffs.py --write
```

## plot_results.py
Creates Plotly HTML charts from `scenario_trajectories.csv`.

Usage:
```
python3 scripts/plot_results.py
```

Optional filters:
```
python3 scripts/plot_results.py --tax 0.002 --uplift 0.10
```

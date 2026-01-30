#!/usr/bin/env python3
"""Download raw datasets for the California statewide simulator.

Downloads:
- Zillow ZHVI (state)
- Zillow ZORI (state)
- HCD APR Table A2 (permits/completions)
- DOF E-5 and E-8 (Excel)
- ACS 1-year statewide (vacancy rate, renter share)
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


try:
    import yaml
except Exception as exc:  # pragma: no cover - environment dependent
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    raise


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MIN_DOWNLOAD_BYTES = 256


@dataclass
class Config:
    outputs: Dict[str, Path]
    urls: Dict[str, str]
    acs: Dict[str, Any]


def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    outputs = {k: Path(v) for k, v in raw["outputs"].items()}
    return Config(outputs=outputs, urls=raw["urls"], acs=raw["acs"])


def download_file(url: str, path: Path, force: bool) -> None:
    if path.exists() and not force:
        try:
            if path.stat().st_size < MIN_DOWNLOAD_BYTES:
                print(f"Existing file too small, re-downloading: {path}")
            else:
                print(f"Skip existing: {path}")
                return
        except OSError:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp, path.open("wb") as f:
        content = resp.read()
        f.write(content)
    if path.stat().st_size < MIN_DOWNLOAD_BYTES or _is_probably_html(content):
        raise ValueError(f"Download appears invalid (too small or HTML): {url}")
    print(f"Downloaded {url} -> {path}")


def fetch_acs(acs_cfg: Dict[str, Any], output_path: Path, force: bool) -> None:
    if output_path.exists() and not force:
        print(f"Skip existing: {output_path}")
        return

    start_year = int(acs_cfg["start_year"])
    end_year = int(acs_cfg["end_year"])
    state_fips = str(acs_cfg["state_fips"])
    api_key_env = acs_cfg.get("api_key_env", "CENSUS_API_KEY")
    dataset = acs_cfg.get("dataset", "acs1")
    fallback_dataset = acs_cfg.get("fallback_dataset", "acs5")

    api_key = None
    if api_key_env:
        api_key = __import__("os").environ.get(api_key_env)

    # ACS variables:
    # B25002_001E total housing units
    # B25002_003E vacant housing units
    # B25003_001E total occupied units
    # B25003_003E renter-occupied units
    vars_list = ["B25002_001E", "B25002_003E", "B25003_001E", "B25003_003E"]

    rows = []
    for year in range(start_year, end_year + 1):
        record = _fetch_acs_year(
            year,
            dataset,
            fallback_dataset,
            vars_list,
            state_fips,
            api_key,
        )
        if record is None:
            continue

        total_units = float(record["B25002_001E"])
        vacant_units = float(record["B25002_003E"])
        occupied_units = float(record["B25003_001E"])
        renter_units = float(record["B25003_003E"])

        vacancy_rate = vacant_units / total_units if total_units else 0.0
        renter_share = renter_units / occupied_units if occupied_units else 0.0

        rows.append(
            {
                "year": year,
                "vacancy_rate": vacancy_rate,
                "renter_share": renter_share,
            }
        )

    if not rows:
        raise ValueError("ACS download failed for all requested years.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "vacancy_rate", "renter_share"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {output_path}")


def _fetch_acs_year(
    year: int,
    dataset: str,
    fallback_dataset: str,
    vars_list: list[str],
    state_fips: str,
    api_key: str | None,
) -> Dict[str, str] | None:
    for ds in [dataset, fallback_dataset]:
        base = f"https://api.census.gov/data/{year}/acs/{ds}"
        params = {
            "get": ",".join(vars_list),
            "for": f"state:{state_fips}",
        }
        if api_key:
            params["key"] = api_key
        url = base + "?" + urlencode(params)

        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req) as resp:
            content = resp.read()
        if _is_probably_html(content):
            print(f"ACS {year} {ds}: non-JSON response; skipping")
            continue
        try:
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError:
            print(f"ACS {year} {ds}: JSON decode error; skipping")
            continue
        if isinstance(data, dict) and data.get("error"):
            print(f"ACS {year} {ds}: API error {data.get('error')}; skipping")
            continue
        if not isinstance(data, list) or len(data) < 2:
            print(f"ACS {year} {ds}: unexpected response; skipping")
            continue

        header = data[0]
        values = data[1]
        return dict(zip(header, values))
    return None


def _is_probably_html(content: bytes) -> bool:
    head = content[:200].lower()
    return b"<!doctype html" in head or b"<html" in head


def download_datastore_csv(resource_id: str, path: Path, force: bool) -> None:
    if path.exists() and not force:
        print(f"Skip existing: {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    base = "https://data.ca.gov/api/3/action/datastore_search"
    limit = 5000
    offset = 0
    fieldnames = None

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = None
        while True:
            params = {"resource_id": resource_id, "limit": limit, "offset": offset}
            url = base + "?" + urlencode(params)
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            result = data.get("result", {})
            records = result.get("records", [])
            if not records:
                break

            if fieldnames is None:
                fieldnames = [f["id"] for f in result.get("fields", []) if f["id"] != "_id"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

            for row in records:
                row.pop("_id", None)
                writer.writerow(row)

            offset += limit

    print(f"Downloaded data.ca.gov datastore -> {path}")


def main() -> int:
    force = "--force" in sys.argv
    skip_acs = "--skip-acs" in sys.argv
    cfg = load_config(Path("config/download_sources.yaml"))

    download_file(cfg.urls["zillow_zhvi"], cfg.outputs["zillow_zhvi"], force)
    download_file(cfg.urls["zillow_zori"], cfg.outputs["zillow_zori"], force)
    try:
        download_file(cfg.urls["hcd_apr_table_a2"], cfg.outputs["hcd_apr_table_a2"], force)
    except HTTPError as exc:
        if exc.code == 403:
            resource_id = cfg.urls["hcd_apr_resource_id"]
            download_datastore_csv(resource_id, cfg.outputs["hcd_apr_table_a2"], force)
        else:
            raise
    except ValueError:
        resource_id = cfg.urls["hcd_apr_resource_id"]
        download_datastore_csv(resource_id, cfg.outputs["hcd_apr_table_a2"], force)

    download_file(cfg.urls["dof_e5_xlsx"], cfg.outputs["dof_e5_xlsx"], force)
    download_file(cfg.urls["dof_e8_xlsx"], cfg.outputs["dof_e8_xlsx"], force)

    if skip_acs:
        print("Skipping ACS download (--skip-acs).")
    else:
        fetch_acs(cfg.acs, cfg.outputs["acs_state"], force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

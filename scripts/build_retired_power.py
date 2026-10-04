"""Build and validate the EIA-860M retired-power layer (STEP 2)."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.processing.retired_power import (
    RETIRED_COLUMNS,
    aggregate_retired_plants,
    match_retired_plants,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/eia/august_generator2026.xlsx"
BASE = ROOT / "data/processed/candidate_sites.parquet"
PLANTS = ROOT / "data/processed/retired_power_sites.parquet"
ENRICHED = ROOT / "data/processed/candidate_sites_power.parquet"
VALIDATION = ROOT / "outputs/validation"
SOURCE_URL = (
    "https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx"
)

if not RAW.is_file() or not BASE.is_file():
    raise SystemExit(
        "STEP 2 needs the downloaded EIA-860M workbook and STEP 1 candidate_sites.parquet"
    )

retired_headers = pd.read_excel(
    RAW, sheet_name="Retired", header=2, nrows=0
).columns.tolist()
print("EIA Retired source columns (df.columns.tolist()):")
print(retired_headers)
VALIDATION.mkdir(parents=True, exist_ok=True)
(VALIDATION / "eia_retired_source_columns.json").write_text(
    json.dumps(retired_headers, indent=2) + "\n", encoding="utf-8"
)

retired = pd.concat(
    [
        pd.read_excel(RAW, sheet_name=sheet, header=2, usecols=RETIRED_COLUMNS)
        for sheet in ("Retired", "Retired_PR")
    ],
    ignore_index=True,
)
operating = pd.concat(
    [
        pd.read_excel(RAW, sheet_name=sheet, header=2, usecols=["Plant ID"])
        for sheet in ("Operating", "Operating_PR")
    ],
    ignore_index=True,
)
plants = aggregate_retired_plants(retired, operating)
sites = pd.read_parquet(BASE)
enriched = match_retired_plants(sites, plants)
if len(enriched) != len(sites) or not enriched["site_id"].is_unique:
    raise ValueError("Accidental duplicate or missing site join")
matched = enriched.loc[enriched["former_power_plant"]]
if not matched["power_site_distance_km"].le(2).all():
    raise ValueError("A retired-power match exceeds 2 km")
if not plants["plant_id"].is_unique:
    raise ValueError("Duplicate aggregated plant IDs")
passing = enriched.loc[enriched["passes_initial_filter"]]
passing_matched = passing.loc[passing["former_power_plant"]]

stats = {
    "retired_generator_rows_with_plant_id": int(
        pd.to_numeric(retired["Plant ID"], errors="coerce").notna().sum()
    ),
    "retired_power_plants_loaded": len(plants),
    "fully_retired_plants_with_valid_coordinates": int(
        (plants["fully_retired"] & plants["has_valid_coordinates"]).sum()
    ),
    "all_epa_sites_matched": len(matched),
    "initial_filter_sites_matched": len(passing_matched),
    "initial_filter_match_percentage": round(
        len(passing_matched) / len(passing) * 100, 2
    ),
    "median_match_distance_km": round(
        float(passing_matched["power_site_distance_km"].median()), 4
    )
    if len(passing_matched)
    else None,
    "former_coal_candidate_sites": int(
        passing_matched["former_primary_fuel"].isin(["BIT", "SUB", "LIG", "WC"]).sum()
    ),
    "former_natural_gas_candidate_sites": int(
        passing_matched["former_primary_fuel"].eq("NG").sum()
    ),
    "site_id_duplicates": int(enriched["site_id"].duplicated().sum()),
}
sample_columns = [
    "site_id",
    "site_name",
    "matched_power_plant_name",
    "power_site_distance_km",
    "former_capacity_mw",
    "former_primary_fuel",
    "power_match_confidence",
]
sample = passing_matched.sample(n=min(10, len(passing_matched)), random_state=42)[
    sample_columns
]
sample_records = (
    sample.astype(object).where(pd.notna(sample), None).to_dict(orient="records")
)
print(f"Retired power plants loaded: {stats['retired_power_plants_loaded']:,}")
print(f"Candidate sites matched: {stats['initial_filter_sites_matched']:,}")
print(f"Match percentage: {stats['initial_filter_match_percentage']:.2f}%")
print(f"Median match distance: {stats['median_match_distance_km']} km")
print(f"Former coal sites: {stats['former_coal_candidate_sites']:,}")
print(f"Former gas sites (NG): {stats['former_natural_gas_candidate_sites']:,}")
print("Random matched sites (seed=42):")
print(sample.to_string(index=False))

plants.to_parquet(PLANTS, index=False)
enriched.to_parquet(ENRICHED, index=False)
with RAW.open("rb") as raw_file:
    digest = hashlib.file_digest(raw_file, "sha256").hexdigest()
summary = {
    "source_url": SOURCE_URL,
    "source_file": RAW.relative_to(ROOT).as_posix(),
    "source_sha256": digest,
    "source_version": "August 2026 EIA-860M, released September 24, 2026",
    "download_date": "2026-10-03",
    "source_sheets": ["Retired", "Retired_PR", "Operating", "Operating_PR"],
    "source_columns_file": "outputs/validation/eia_retired_source_columns.json",
    "used_retired_columns": RETIRED_COLUMNS,
    "match_radius_km": 2,
    "capacity_interpretation": "Sum of retired generator nameplate MW; historical infrastructure-scale proxy, not currently available grid capacity.",
    "former_power_plant_rule": "Retired generators present and no generator in EIA-860M Operating or Operating_PR for the same Plant ID.",
    "statistics": stats,
    "random_match_seed": 42,
    "random_matched_sample": sample_records,
}
(VALIDATION / "step2_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)
print(f"Wrote {PLANTS.relative_to(ROOT)}")
print(f"Wrote {ENRICHED.relative_to(ROOT)}")

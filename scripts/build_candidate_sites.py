"""Build STEP 1 EPA RE-Powering candidate sites and validation map.

Run from this feature directory:
    ../.venv/bin/python -m scripts.build_candidate_sites
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.processing.repowering import (
    COLUMN_MAPPING,
    build_candidate_map,
    standardize_sites,
    validate_sites,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/repowering/re-powering-screening-dataset-2022_Updated.xlsx"
PROCESSED = ROOT / "data/processed/candidate_sites.parquet"
VALIDATION = ROOT / "outputs/validation"
MAP = VALIDATION / "candidate_sites_map.html"
SHEET = "RE-Powering Sites"
SOURCE_URL = (
    "https://www.epa.gov/system/files/documents/2023-05/"
    "re-powering-screening-dataset-2022%20Updated.xlsx"
)

if not RAW.is_file():
    raise SystemExit(f"Missing official EPA source file: {RAW}")

headers = pd.read_excel(
    RAW, sheet_name=SHEET, nrows=0, engine="openpyxl"
).columns.tolist()
print("EPA source columns (df.columns.tolist()):")
print(headers)
VALIDATION.mkdir(parents=True, exist_ok=True)
(VALIDATION / "source_columns.json").write_text(
    json.dumps(headers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

source = pd.read_excel(
    RAW, sheet_name=SHEET, usecols=list(COLUMN_MAPPING), engine="openpyxl"
)
sites = standardize_sites(source)
validate_sites(sites)

valid_coordinates = sites["latitude"].between(-90, 90) & sites["longitude"].between(
    -180, 180
)
near_high_voltage_line = sites["distance_to_transmission"].le(3) & sites[
    "transmission_voltage"
].ge(115)
passing = sites.loc[sites["passes_initial_filter"]]
stats = {
    "total_epa_sites": len(sites),
    "sites_with_valid_coordinates": int(valid_coordinates.sum()),
    "sites_at_least_50_acres": int(sites["acreage"].ge(50).sum()),
    "sites_near_at_least_115kv_transmission": int(near_high_voltage_line.sum()),
    "sites_passing_all_filters": len(passing),
    "source_site_id_duplicates": int(sites["source_site_id"].duplicated().sum()),
    "site_id_duplicates": int(sites["site_id"].duplicated().sum()),
    "transmission_voltage_over_765kv": int(
        sites["transmission_voltage_review_required"].sum()
    ),
    "passing_sites_with_transmission_voltage_over_765kv": int(
        passing["transmission_voltage_review_required"].sum()
    ),
    "substation_voltage_over_765_reported_units": int(
        sites["substation_voltage_review_required"].sum()
    ),
}
sample_columns = [
    "site_id",
    "site_name",
    "state",
    "acreage",
    "transmission_voltage",
    "distance_to_transmission",
    "distance_to_substation",
]
sample = passing.sample(n=min(10, len(passing)), random_state=42)[sample_columns]
sample_records = (
    sample.astype(object).where(pd.notna(sample), None).to_dict(orient="records")
)

print(f"Total EPA sites: {stats['total_epa_sites']:,}")
print(f"Sites with valid coordinates: {stats['sites_with_valid_coordinates']:,}")
print(f"Sites >= 50 acres: {stats['sites_at_least_50_acres']:,}")
print(
    f"Sites near >=115kV transmission: {stats['sites_near_at_least_115kv_transmission']:,}"
)
print(f"Sites passing all filters: {stats['sites_passing_all_filters']:,}")
print(
    f"Transmission voltage >765 kV (review): {stats['transmission_voltage_over_765kv']:,}"
)
print(
    "Passing sites with transmission voltage >765 kV (review): "
    f"{stats['passing_sites_with_transmission_voltage_over_765kv']:,}"
)
print("Random 10 candidate sites (seed=42):")
print(sample.to_string(index=False))

PROCESSED.parent.mkdir(parents=True, exist_ok=True)
sites.to_parquet(PROCESSED, index=False)
build_candidate_map(sites, MAP)

with RAW.open("rb") as raw_file:
    digest = hashlib.file_digest(raw_file, "sha256").hexdigest()
summary = {
    "source_url": SOURCE_URL,
    "source_file": RAW.relative_to(ROOT).as_posix(),
    "source_sha256": digest,
    "source_sheet": SHEET,
    "source_version": "2022 (updated 2023), per workbook Attributes sheet",
    "download_date": "2026-10-03",
    "source_columns_file": "outputs/validation/source_columns.json",
    "map_basemap": {
        "service": "USGS The National Map USGSTopo",
        "url_template": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Map services and data available from U.S. Geological Survey, National Geospatial Program.",
    },
    "column_mapping": COLUMN_MAPPING,
    "filter": {
        "acreage_acres_min": 50,
        "transmission_distance_miles_max": 3,
        "transmission_voltage_kv_min": 115,
        "substation_distance_miles_max": 5,
    },
    "statistics": stats,
    "random_sample_seed": 42,
    "random_candidate_sample": sample_records,
}
(VALIDATION / "step1_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)
print(f"Wrote {PROCESSED.relative_to(ROOT)}")
print(f"Wrote {MAP.relative_to(ROOT)}")

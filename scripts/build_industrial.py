"""Build EPA FRS industrial layer and geodesic candidate-site proximity fields."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.processing.industrial import SECTOR_PREFIXES, read_industrial_facilities
from src.spatial.radius import radius_metrics

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/frs/national_single.zip"
FACILITY_OUTPUT = ROOT / "data/processed/industrial_facilities.parquet"
SITE_INPUT = ROOT / "data/processed/candidate_sites_inheritance.parquet"
SITE_OUTPUT = ROOT / "data/processed/candidate_sites_industrial.parquet"
VALIDATION = ROOT / "outputs/validation"


def main() -> None:
    facilities, columns, source_stats = read_industrial_facilities(RAW)
    FACILITY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    facilities.to_parquet(FACILITY_OUTPUT, index=False)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "frs_source_columns.json").write_text(
        json.dumps(columns, indent=2) + "\n", encoding="utf-8"
    )
    valid = facilities.loc[
        facilities["latitude"].between(-90, 90)
        & facilities["longitude"].between(-180, 180)
    ].reset_index(drop=True)
    sites = pd.read_parquet(SITE_INPUT)
    masks = {
        f"{sector}_sites": valid[f"is_{sector}"].to_numpy(dtype=bool)
        for sector in SECTOR_PREFIXES
    }
    metrics = radius_metrics(sites, valid, (1, 5, 10), masks)
    renames = {
        "count_1km": "industrial_sites_1km",
        "count_5km": "industrial_sites_5km",
        "count_10km": "industrial_sites_10km",
        "nearest_km": "nearest_industrial_sink_km",
        **{f"{sector}_sites_5km": f"{sector}_sites_5km" for sector in SECTOR_PREFIXES},
    }
    metrics = metrics.rename(columns=renames)
    nearest_pos = metrics.pop("nearest_target_pos").to_numpy(dtype=int)
    sites = pd.concat([sites.reset_index(drop=True), metrics.reset_index(drop=True)], axis=1)
    sites["nearest_industrial_sink_id"] = pd.Series(pd.NA, index=sites.index, dtype="string")
    sites["nearest_industrial_sink_name"] = pd.Series(pd.NA, index=sites.index, dtype="string")
    sites["nearest_industrial_sink_naics"] = pd.Series(pd.NA, index=sites.index, dtype="string")
    matched = nearest_pos >= 0
    picked = valid.iloc[nearest_pos[matched]]
    sites.loc[matched, "nearest_industrial_sink_id"] = picked["facility_id"].to_numpy()
    sites.loc[matched, "nearest_industrial_sink_name"] = picked["facility_name"].to_numpy()
    sites.loc[matched, "nearest_industrial_sink_naics"] = picked[
        "selected_naics_codes"
    ].to_numpy()
    if not (
        (sites["industrial_sites_1km"] <= sites["industrial_sites_5km"])
        & (sites["industrial_sites_5km"] <= sites["industrial_sites_10km"])
    ).all():
        raise ValueError("Industrial radius counts are not nested")
    if sites["nearest_industrial_sink_km"].lt(0).any():
        raise ValueError("Negative industrial distance")
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(SITE_OUTPUT, index=False)
    passing = sites.loc[sites["passes_initial_filter"]]
    sample = passing.sample(n=20, random_state=42)
    sample_columns = [
        "site_id", "site_name", "industrial_sites_5km",
        "nearest_industrial_sink_name", "nearest_industrial_sink_km",
        "nearest_industrial_sink_naics",
    ]
    sample[sample_columns].to_csv(VALIDATION / "step4_random20.csv", index=False)
    with RAW.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    summary = {
        "source_zip_sha256": digest,
        **source_stats,
        "sites_enriched": len(sites),
        "passing_sites": len(passing),
        "passing_with_5km_industry": int(passing["industrial_sites_5km"].gt(0).sum()),
        "nested_counts_valid": True,
        "nearest_distance_min_km": float(np.nanmin(sites["nearest_industrial_sink_km"])),
        "random20_site_ids": sample["site_id"].astype(int).tolist(),
    }
    (VALIDATION / "step4_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(sample[sample_columns].to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

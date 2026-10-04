"""Build the STEP 5 wastewater layer, spatial fields, and reuse proxy."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.processing.wastewater import read_wastewater_facilities
from src.processing.water_score import score_water_reuse
from src.spatial.radius import radius_metrics

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cwns/2022CWNS_NATIONAL_Sept2026.zip"
DICTIONARY = ROOT / "data/raw/cwns/CWNS-Database-Dictionary-January2025.xlsx"
WWTP_OUTPUT = ROOT / "data/processed/wastewater_facilities.parquet"
SITE_INPUT = ROOT / "data/processed/candidate_sites_industrial.parquet"
SITE_OUTPUT = ROOT / "data/processed/candidate_sites_water.parquet"
VALIDATION = ROOT / "outputs/validation"


def main() -> None:
    facilities, headers, source_stats = read_wastewater_facilities(RAW)
    WWTP_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    facilities.to_parquet(WWTP_OUTPUT, index=False)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    (VALIDATION / "cwns_source_columns.json").write_text(
        json.dumps(headers, indent=2) + "\n", encoding="utf-8"
    )
    point = facilities.loc[
        facilities["latitude"].between(-90, 90)
        & facilities["longitude"].between(-180, 180)
    ].reset_index(drop=True)
    sites = pd.read_parquet(SITE_INPUT)
    metrics = radius_metrics(
        sites, point, (5, 10),
        sum_values={"design_flow_mgd": point["design_flow_mgd"].to_numpy(dtype=float)},
    ).rename(
        columns={
            "count_5km": "wwtp_count_5km",
            "count_10km": "wwtp_count_10km",
            "nearest_km": "nearest_wwtp_km",
            "design_flow_mgd_sum_5km": "wastewater_flow_5km",
            "design_flow_mgd_sum_10km": "wastewater_flow_10km",
            "design_flow_mgd_known_count_5km": "wwtp_flow_known_count_5km",
            "design_flow_mgd_known_count_10km": "wwtp_flow_known_count_10km",
        }
    )
    nearest_pos = metrics.pop("nearest_target_pos").to_numpy(dtype=int)
    sites = pd.concat([sites.reset_index(drop=True), metrics.reset_index(drop=True)], axis=1)
    for radius in (5, 10):
        no_known_flow = (
            sites[f"wwtp_count_{radius}km"].gt(0)
            & sites[f"wwtp_flow_known_count_{radius}km"].eq(0)
        )
        sites.loc[no_known_flow, f"wastewater_flow_{radius}km"] = float("nan")
    for name in (
        "nearest_wwtp_id", "nearest_wwtp_name", "nearest_wwtp_treatment_level"
    ):
        sites[name] = pd.Series(pd.NA, index=sites.index, dtype="string")
    matched = nearest_pos >= 0
    picked = point.iloc[nearest_pos[matched]]
    sites.loc[matched, "nearest_wwtp_id"] = picked["facility_id"].to_numpy()
    sites.loc[matched, "nearest_wwtp_name"] = picked["facility_name"].to_numpy()
    sites.loc[matched, "nearest_wwtp_treatment_level"] = picked[
        "treatment_level"
    ].to_numpy()
    sites["nearest_wwtp_design_flow_mgd"] = float("nan")
    sites.loc[matched, "nearest_wwtp_design_flow_mgd"] = picked[
        "design_flow_mgd"
    ].to_numpy(dtype=float)
    sites = score_water_reuse(sites)
    if not (sites["wwtp_count_5km"] <= sites["wwtp_count_10km"]).all():
        raise ValueError("WWTP counts are not nested")
    if sites["nearest_wwtp_km"].lt(0).any():
        raise ValueError("Negative WWTP distance")
    if sites[["wastewater_flow_5km", "wastewater_flow_10km"]].lt(0).any().any():
        raise ValueError("Negative reported design flow")
    if not sites["water_reuse_component"].between(0, 100).all():
        raise ValueError("Water reuse component outside [0,100]")
    SITE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(SITE_OUTPUT, index=False)
    passing = sites.loc[sites["passes_initial_filter"]]
    sample = passing.sample(n=20, random_state=42)
    columns = [
        "site_id", "site_name", "nearest_wwtp_name", "nearest_wwtp_km",
        "wwtp_count_5km", "wwtp_count_10km", "wastewater_flow_5km",
        "wastewater_flow_10km", "nearest_wwtp_design_flow_mgd",
    ]
    sample[columns].to_csv(VALIDATION / "step5_random20.csv", index=False)
    top = (
        passing.sort_values(
            ["water_reuse_component", "wastewater_flow_10km", "nearest_wwtp_km"],
            ascending=[False, False, True],
        )
        .drop_duplicates(["site_name", "latitude", "longitude"])
        .head(20)
    )
    top[["water_reuse_component", *columns]].to_csv(
        VALIDATION / "step5_top20.csv", index=False
    )
    with RAW.open("rb") as source:
        zip_hash = hashlib.file_digest(source, "sha256").hexdigest()
    with DICTIONARY.open("rb") as source:
        dictionary_hash = hashlib.file_digest(source, "sha256").hexdigest()
    summary = {
        "source_zip_sha256": zip_hash,
        "data_dictionary_sha256": dictionary_hash,
        **source_stats,
        "sites_enriched": len(sites),
        "passing_sites": len(passing),
        "passing_with_wwtp_5km": int(passing["wwtp_count_5km"].gt(0).sum()),
        "passing_with_known_design_flow_10km": int(
            passing["wwtp_flow_known_count_10km"].gt(0).sum()
        ),
        "nested_counts_valid": True,
        "random20_site_ids": sample["site_id"].astype(int).tolist(),
        "top20_site_ids": top["site_id"].astype(int).tolist(),
    }
    (VALIDATION / "step5_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(sample[columns].to_string(index=False))
    print(top[["water_reuse_component", *columns]].to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

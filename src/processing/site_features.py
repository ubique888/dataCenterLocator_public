"""Publish a typed, one-row-per-screened-site feature contract."""

import numpy as np
import pandas as pd

RENAME = {
    "latitude": "lat",
    "longitude": "lon",
    "transmission_voltage": "transmission_kv",
    "distance_to_transmission": "transmission_distance",
    "distance_to_substation": "substation_distance",
    "distance_to_rail": "rail_distance",
    "distance_to_road": "road_distance",
}

REQUIRED_COLUMNS = [
    "site_id", "site_name", "lat", "lon", "state", "county", "acreage",
    "former_power_plant", "former_capacity_mw", "former_primary_fuel",
    "retirement_year", "transmission_kv", "transmission_distance",
    "substation_voltage", "substation_distance", "rail_distance",
    "road_distance", "industrial_sites_1km", "industrial_sites_5km",
    "industrial_sites_10km", "nearest_industrial_sink_km",
    "nearest_wwtp_km", "wwtp_count_5km", "wastewater_flow_5km",
    "inheritance_score", "symbiosis_score", "data_quality_score",
    "missing_fields_count", "power_match_confidence",
]

ALWAYS_EXPECTED = [
    "site_name", "lat", "lon", "state", "county", "acreage",
    "transmission_kv", "transmission_distance", "substation_voltage",
    "substation_distance", "rail_distance", "road_distance",
    "nearest_industrial_sink_km", "nearest_wwtp_km", "inheritance_score",
    "symbiosis_score",
]
FORMER_ONLY = ["former_capacity_mw", "former_primary_fuel", "retirement_year"]
CONFIDENCE_PENALTY = {
    "very_high": 0, "high": 3, "medium": 8, "low": 15, "unmatched": 0,
}


def build_site_features(source: pd.DataFrame) -> pd.DataFrame:
    """Select STEP 1 passing rows, rename the published contract, and score quality."""
    if "passes_initial_filter" not in source:
        raise ValueError("Missing passes_initial_filter")
    sites = source.loc[source["passes_initial_filter"].eq(True)].copy()
    sites = sites.rename(columns=RENAME).reset_index(drop=True)
    missing = set(REQUIRED_COLUMNS) - {"data_quality_score", "missing_fields_count"} - set(sites)
    if missing:
        raise ValueError(f"Missing final feature inputs: {sorted(missing)}")
    if sites["site_id"].isna().any() or sites["site_id"].duplicated().any():
        raise ValueError("Final site IDs must be present and unique")
    if not sites["lat"].between(-90, 90).all() or not sites["lon"].between(-180, 180).all():
        raise ValueError("Invalid site coordinates")

    masks: dict[str, pd.Series] = {
        name: sites[name].isna() for name in ALWAYS_EXPECTED
    }
    matched = sites["former_power_plant"].eq(True)
    for name in FORMER_ONLY:
        masks[name] = matched & sites[name].isna()
    masks["wastewater_flow_5km"] = (
        sites["wwtp_count_5km"].gt(0) & sites["wastewater_flow_5km"].isna()
    )
    sites["missing_fields_count"] = sum(mask.astype("int64") for mask in masks.values())
    sites["data_quality_missing_fields"] = [
        ", ".join(name for name, mask in masks.items() if bool(mask.iloc[i]))
        for i in range(len(sites))
    ]
    confidence_penalty = sites["power_match_confidence"].map(CONFIDENCE_PENALTY)
    if confidence_penalty.isna().any():
        raise ValueError("Unexpected power match confidence")
    voltage_penalty = (
        sites.get("transmission_voltage_review_required", False).astype(int) * 10
        + sites.get("substation_voltage_review_required", False).astype(int) * 5
    )
    sites["data_quality_score"] = np.maximum(
        0,
        100 - 10 * sites["missing_fields_count"] - confidence_penalty
        - voltage_penalty,
    ).astype(float)
    if not sites["data_quality_score"].between(0, 100).all():
        raise ValueError("Data quality score outside [0,100]")
    if "overall_score" in sites:
        raise ValueError("Do not publish an overall score")
    extra = [name for name in sites if name not in REQUIRED_COLUMNS]
    return sites[[*REQUIRED_COLUMNS, *extra]]

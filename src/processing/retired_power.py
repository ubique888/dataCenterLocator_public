"""Aggregate EIA retired generators and link verified former plants to EPA sites."""

import numpy as np
import pandas as pd

from src.spatial.nearby import nearest_within_km

RETIRED_COLUMNS = [
    "Plant ID",
    "Plant Name",
    "Generator ID",
    "Nameplate Capacity (MW)",
    "Energy Source Code",
    "Retirement Year",
    "Latitude",
    "Longitude",
]


def aggregate_retired_plants(
    retired: pd.DataFrame, operating: pd.DataFrame
) -> pd.DataFrame:
    """Sum retired nameplate capacity per plant and identify fully retired plants."""
    missing = set(RETIRED_COLUMNS) - set(retired.columns)
    if missing:
        raise ValueError(f"Missing EIA retired columns: {sorted(missing)}")
    if "Plant ID" not in operating:
        raise ValueError("Missing EIA operating Plant ID")
    rows = retired.loc[:, RETIRED_COLUMNS].copy()
    for column in (
        "Plant ID",
        "Nameplate Capacity (MW)",
        "Retirement Year",
        "Latitude",
        "Longitude",
    ):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    rows = rows.dropna(subset=["Plant ID"])
    rows["Plant ID"] = rows["Plant ID"].astype("int64")
    rows = rows.drop_duplicates(subset=["Plant ID", "Generator ID"])
    if rows.empty:
        raise ValueError("No retired generators with a valid Plant ID")

    grouped = rows.groupby("Plant ID", sort=True)
    plants = (
        grouped.agg(
            plant_name=("Plant Name", "first"),
            latitude=("Latitude", "first"),
            longitude=("Longitude", "first"),
            former_capacity_mw=(
                "Nameplate Capacity (MW)",
                lambda values: values.sum(min_count=1),
            ),
            latest_retirement_year=("Retirement Year", "max"),
            generator_count=("Generator ID", "nunique"),
        )
        .rename_axis("plant_id")
        .reset_index()
    )

    fuel_capacity = (
        rows.groupby(["Plant ID", "Energy Source Code"], dropna=False)[
            "Nameplate Capacity (MW)"
        ]
        .sum(min_count=1)
        .reset_index()
        .sort_values(
            ["Plant ID", "Nameplate Capacity (MW)", "Energy Source Code"],
            ascending=[True, False, True],
        )
        .drop_duplicates("Plant ID")
        .set_index("Plant ID")["Energy Source Code"]
    )
    plants["former_primary_fuel"] = plants["plant_id"].map(fuel_capacity)
    operating_ids = (
        pd.to_numeric(operating["Plant ID"], errors="coerce").dropna().astype("int64")
    )
    plants["fully_retired"] = ~plants["plant_id"].isin(operating_ids)
    plants["has_valid_coordinates"] = plants["latitude"].between(-90, 90) & plants[
        "longitude"
    ].between(-180, 180)
    plants["latest_retirement_year"] = plants["latest_retirement_year"].astype("Int64")
    return plants


def match_retired_plants(sites: pd.DataFrame, plants: pd.DataFrame) -> pd.DataFrame:
    """Attach the nearest fully retired EIA plant within 2 km without changing row count."""
    result = sites.reset_index(drop=True).copy()
    eligible = plants.loc[
        plants["fully_retired"]
        & plants["latitude"].between(-90, 90)
        & plants["longitude"].between(-180, 180)
    ].reset_index(drop=True)
    positions, distances = nearest_within_km(result, eligible, radius_km=2)
    matched = positions >= 0
    result["former_power_plant"] = matched
    result["matched_power_plant_id"] = pd.Series(
        pd.NA, index=result.index, dtype="Int64"
    )
    result["matched_power_plant_name"] = pd.Series(
        pd.NA, index=result.index, dtype="string"
    )
    result["former_capacity_mw"] = np.nan
    result["former_primary_fuel"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["retirement_year"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["power_site_distance_km"] = distances
    result["power_match_confidence"] = "unmatched"
    if matched.any():
        picked = eligible.iloc[positions[matched]]
        result.loc[matched, "matched_power_plant_id"] = picked["plant_id"].to_numpy()
        result.loc[matched, "matched_power_plant_name"] = picked[
            "plant_name"
        ].to_numpy()
        result.loc[matched, "former_capacity_mw"] = picked[
            "former_capacity_mw"
        ].to_numpy()
        result.loc[matched, "former_primary_fuel"] = picked[
            "former_primary_fuel"
        ].to_numpy()
        result.loc[matched, "retirement_year"] = picked[
            "latest_retirement_year"
        ].to_numpy()
        result.loc[matched, "power_match_confidence"] = np.select(
            [
                distances[matched] <= 0.25,
                distances[matched] <= 0.5,
                distances[matched] <= 1,
            ],
            ["very_high", "high", "medium"],
            default="low",
        )
    return result

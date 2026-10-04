"""Build supplemental power and internet-exchange connectivity metrics."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Geod

CONNECTIVITY_COLUMNS = [
    "site_id",
    "substation_distance_km",
    "peering_facility_id",
    "peering_facility_distance_km",
    "peering_facility_network_count",
    "connectivity_status",
    "peering_snapshot_id",
]
SITE_COLUMNS = {"site_id", "lat", "lon", "substation_distance"}
FACILITY_COLUMNS = {
    "facility_id", "latitude", "longitude", "network_count", "snapshot_id"
}
WGS84 = Geod(ellps="WGS84")
SITE_BLOCK_SIZE = 128
FACILITY_BLOCK_SIZE = 512


def _numeric_series(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").astype("float64")


def _valid_coordinates(
    frame: pd.DataFrame,
    latitude: str,
    longitude: str,
    *,
    reject_origin_placeholder: bool = False,
) -> np.ndarray:
    lat = _numeric_series(frame[latitude]).to_numpy()
    lon = _numeric_series(frame[longitude]).to_numpy()
    valid = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & (lat >= -90)
        & (lat <= 90)
        & (lon >= -180)
        & (lon <= 180)
    )
    if reject_origin_placeholder:
        valid &= ~((lat == 0) & (lon == 0))
    return valid


def _validate_ids(frame: pd.DataFrame, column: str, label: str) -> pd.Series:
    values = _numeric_series(frame[column])
    valid = np.isfinite(values.to_numpy()) & (values.to_numpy() > 0)
    valid &= values.to_numpy() == np.floor(values.to_numpy())
    if not bool(valid.all()):
        raise ValueError(f"{label} must contain non-null positive integer IDs")
    ids = values.astype("int64")
    if ids.duplicated().any():
        raise ValueError(f"{label} must be unique")
    return ids


def build_power_connectivity(
    sites: pd.DataFrame, facilities: pd.DataFrame, snapshot_id: str
) -> pd.DataFrame:
    """Return one supplemental metric row per input site, preserving its order.

    The PeeringDB distance is the exact WGS84 geodesic to the nearest eligible
    IXP-hosting facility in the supplied snapshot. No distance cutoff is used.
    Network count always comes from that same nearest facility, including when
    its count is missing.
    """
    missing_sites = SITE_COLUMNS - set(sites.columns)
    if missing_sites:
        raise ValueError(f"sites missing required columns: {sorted(missing_sites)}")
    missing_facilities = FACILITY_COLUMNS - set(facilities.columns)
    if missing_facilities:
        raise ValueError(
            f"facilities missing required columns: {sorted(missing_facilities)}"
        )
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise ValueError("snapshot_id must be a non-empty string")

    site_ids = _validate_ids(sites, "site_id", "site_id")
    if facilities.empty:
        facility_ids = pd.Series([], dtype="int64")
    else:
        facility_ids = _validate_ids(facilities, "facility_id", "facility_id")
        if facilities["snapshot_id"].isna().any() or not facilities[
            "snapshot_id"
        ].astype(str).eq(snapshot_id).all():
            raise ValueError("facility snapshot IDs must match the requested snapshot")
        if not _valid_coordinates(
            facilities,
            "latitude",
            "longitude",
            reject_origin_placeholder=True,
        ).all():
            raise ValueError("eligible facilities must have valid coordinates")

    site_lat = _numeric_series(sites["lat"]).to_numpy()
    site_lon = _numeric_series(sites["lon"]).to_numpy()
    valid_site = _valid_coordinates(sites, "lat", "lon")
    miles = _numeric_series(sites["substation_distance"])
    mile_values = miles.to_numpy()
    valid_miles = np.isfinite(mile_values) & (mile_values >= 0)
    substation_km = (miles * 1.609344).where(valid_miles).to_numpy()

    row_count = len(sites)
    nearest_id = np.full(row_count, -1, dtype=np.int64)
    nearest_km = np.full(row_count, np.nan, dtype=np.float64)
    network_counts = pd.array([pd.NA] * row_count, dtype="Int64")

    if not facilities.empty:
        ordered = facilities.assign(_facility_id=facility_ids).sort_values(
            "_facility_id", kind="stable"
        )
        facility_id_values = ordered["_facility_id"].to_numpy(dtype=np.int64)
        facility_lat = _numeric_series(ordered["latitude"]).to_numpy()
        facility_lon = _numeric_series(ordered["longitude"]).to_numpy()
        counts = pd.to_numeric(ordered["network_count"], errors="coerce").astype(
            "Int64"
        )

        valid_rows = np.flatnonzero(valid_site)
        for site_start in range(0, len(valid_rows), SITE_BLOCK_SIZE):
            row_indexes = valid_rows[site_start : site_start + SITE_BLOCK_SIZE]
            block_lat = site_lat[row_indexes]
            block_lon = site_lon[row_indexes]
            best_distance = np.full(len(row_indexes), np.inf, dtype=np.float64)
            best_id = np.full(len(row_indexes), -1, dtype=np.int64)
            for facility_start in range(
                0, len(facility_id_values), FACILITY_BLOCK_SIZE
            ):
                stop = min(
                    facility_start + FACILITY_BLOCK_SIZE, len(facility_id_values)
                )
                lon1 = np.repeat(block_lon, stop - facility_start)
                lat1 = np.repeat(block_lat, stop - facility_start)
                lon2 = np.tile(facility_lon[facility_start:stop], len(row_indexes))
                lat2 = np.tile(facility_lat[facility_start:stop], len(row_indexes))
                _, _, metres = WGS84.inv(lon1, lat1, lon2, lat2)
                distances = metres.reshape(len(row_indexes), stop - facility_start)
                local_indexes = np.argmin(distances, axis=1)
                local_distance = distances[
                    np.arange(len(row_indexes)), local_indexes
                ]
                local_ids = facility_id_values[
                    facility_start + local_indexes
                ]
                # Strict comparison keeps the earlier (lower-ID) facility on ties.
                better = local_distance < best_distance
                best_distance[better] = local_distance[better]
                best_id[better] = local_ids[better]

            nearest_id[row_indexes] = best_id
            nearest_km[row_indexes] = best_distance / 1000.0
            selected = pd.Series(best_id).map(
                pd.Series(counts.array, index=facility_id_values)
            )
            network_counts[row_indexes] = pd.array(selected, dtype="Int64")

    status = np.full(row_count, "matched", dtype=object)
    status[~valid_site] = "invalid_site_coordinates"
    if facilities.empty:
        status[valid_site] = "no_eligible_facilities"

    output = pd.DataFrame(
        {
            "site_id": site_ids.to_numpy(dtype=np.int64),
            "substation_distance_km": substation_km,
            "peering_facility_id": pd.array(
                [value if value >= 0 else pd.NA for value in nearest_id], dtype="Int64"
            ),
            "peering_facility_distance_km": nearest_km,
            "peering_facility_network_count": network_counts,
            "connectivity_status": status,
            "peering_snapshot_id": snapshot_id,
        },
        columns=CONNECTIVITY_COLUMNS,
    )
    return output


def connectivity_summary(
    metrics: pd.DataFrame, facilities: pd.DataFrame, snapshot_id: str
) -> dict[str, Any]:
    """Create the auditable build summary persisted next to generated data."""
    statuses = Counter(metrics["connectivity_status"].astype(str))
    distances = metrics["peering_facility_distance_km"].dropna()
    substation_distances = metrics["substation_distance_km"].dropna()
    nearest_ids = metrics["peering_facility_id"].dropna().astype("int64")
    facility_ids = set(facilities["facility_id"].astype("int64"))
    linked_ids = set(nearest_ids)
    relation_ok = all(int(value) in facility_ids for value in nearest_ids)
    return {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "site_rows": int(len(metrics)),
        "eligible_facility_rows": int(len(facilities)),
        "status_counts": dict(sorted(statuses.items())),
        "missing_substation_distance_count": int(
            metrics["substation_distance_km"].isna().sum()
        ),
        "missing_nearest_facility_count": int(
            metrics["peering_facility_id"].isna().sum()
        ),
        "missing_nearest_facility_network_count": int(
            metrics["peering_facility_network_count"].isna().sum()
        ),
        "nearest_facility_relation_count": int(len(nearest_ids)),
        "unique_nearest_facility_count": int(len(linked_ids)),
        "nearest_facility_relations_valid": bool(relation_ok),
        "nearest_facility_distance_km_quantiles": {
            str(q): (float(distances.quantile(q)) if len(distances) else None)
            for q in (0.0, 0.25, 0.5, 0.75, 1.0)
        },
        "substation_distance_km_quantiles": {
            str(q): (
                float(substation_distances.quantile(q))
                if len(substation_distances)
                else None
            )
            for q in (0.0, 0.25, 0.5, 0.75, 1.0)
        },
    }

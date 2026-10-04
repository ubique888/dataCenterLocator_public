"""Geodesic proximity helpers for national point datasets."""

import numpy as np
import pandas as pd
from pyproj import Geod
from shapely import STRtree, box, points

GEOD = Geod(ellps="WGS84")


def nearest_within_km(
    sites: pd.DataFrame, targets: pd.DataFrame, radius_km: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return target positions and WGS84 distances; unmatched positions are -1/NaN."""
    if radius_km <= 0:
        raise ValueError("radius_km must be positive")
    nearest = np.full(len(sites), -1, dtype=np.int64)
    distance_km = np.full(len(sites), np.nan, dtype=float)
    if sites.empty or targets.empty:
        return nearest, distance_km

    site_lat = pd.to_numeric(sites["latitude"], errors="coerce").to_numpy(dtype=float)
    site_lon = pd.to_numeric(sites["longitude"], errors="coerce").to_numpy(dtype=float)
    target_lat = pd.to_numeric(targets["latitude"], errors="coerce").to_numpy(
        dtype=float
    )
    target_lon = pd.to_numeric(targets["longitude"], errors="coerce").to_numpy(
        dtype=float
    )
    valid_sites = np.flatnonzero(
        np.isfinite(site_lat) & np.isfinite(site_lon) & (np.abs(site_lat) <= 90)
    )
    valid_targets = np.flatnonzero(
        np.isfinite(target_lat) & np.isfinite(target_lon) & (np.abs(target_lat) <= 90)
    )
    if not len(valid_sites) or not len(valid_targets):
        return nearest, distance_km

    # Add only antimeridian-adjacent target copies so a US island site can
    # match across +/-180 degrees without tripling the national target index.
    indexed_lon = target_lon[valid_targets]
    indexed_lat = target_lat[valid_targets]
    indexed_target = valid_targets.copy()
    edge = np.abs(indexed_lon) > 170
    if edge.any():
        indexed_lon = np.concatenate(
            [indexed_lon, indexed_lon[edge] + 360, indexed_lon[edge] - 360]
        )
        indexed_lat = np.concatenate(
            [indexed_lat, indexed_lat[edge], indexed_lat[edge]]
        )
        indexed_target = np.concatenate(
            [indexed_target, indexed_target[edge], indexed_target[edge]]
        )

    tree = STRtree(points(indexed_lon, indexed_lat))
    lat_margin = radius_km / 110.0
    lon_margin = radius_km / (
        110.0 * np.maximum(np.cos(np.deg2rad(site_lat[valid_sites])), 0.01)
    )
    envelopes = box(
        site_lon[valid_sites] - lon_margin,
        site_lat[valid_sites] - lat_margin,
        site_lon[valid_sites] + lon_margin,
        site_lat[valid_sites] + lat_margin,
    )
    query_site, query_target = tree.query(envelopes)
    if not len(query_site):
        return nearest, distance_km
    source_pos = valid_sites[query_site]
    target_pos = indexed_target[query_target]
    _, _, distance_m = GEOD.inv(
        site_lon[source_pos],
        site_lat[source_pos],
        target_lon[target_pos],
        target_lat[target_pos],
    )
    keep = distance_m <= radius_km * 1000
    source_pos = source_pos[keep]
    target_pos = target_pos[keep]
    distance_m = distance_m[keep]
    if not len(source_pos):
        return nearest, distance_km
    order = np.lexsort((target_pos, distance_m, source_pos))
    source_pos = source_pos[order]
    target_pos = target_pos[order]
    distance_m = distance_m[order]
    first = np.r_[True, source_pos[1:] != source_pos[:-1]]
    nearest[source_pos[first]] = target_pos[first]
    distance_km[source_pos[first]] = distance_m[first] / 1000
    return nearest, distance_km

"""Coordinate-backed, exact geodesic 5 km neighborhood bundle for the explorer."""

import numpy as np
import pandas as pd
from shapely import STRtree, box, points

from src.spatial.nearby import GEOD

RADIUS_KM = 5.0


def _sector(row: object) -> str:
    labels = [
        label for field, label in [
            ("is_food", "Food"), ("is_beverage", "Beverage"),
            ("is_paper", "Paper"), ("is_chemical", "Chemical"),
            ("is_metal", "Primary metal"),
        ] if getattr(row, field)
    ]
    return ", ".join(labels) or "Selected manufacturing"


def _pairs(sites: pd.DataFrame, facilities: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    site_lat = sites["lat"].to_numpy(dtype=float)
    site_lon = sites["lon"].to_numpy(dtype=float)
    target_lat = facilities["latitude"].to_numpy(dtype=float, na_value=np.nan)
    target_lon = facilities["longitude"].to_numpy(dtype=float, na_value=np.nan)
    valid = np.flatnonzero(
        np.isfinite(target_lat) & np.isfinite(target_lon)
        & (np.abs(target_lat) <= 90) & (np.abs(target_lon) <= 180)
    )
    if not len(valid):
        return np.array([], dtype=int), np.array([], dtype=int), np.array([], dtype=float)
    indexed_lon = target_lon[valid]
    indexed_lat = target_lat[valid]
    indexed_pos = valid.copy()
    edge = np.abs(indexed_lon) >= 170
    if edge.any():
        indexed_lon = np.concatenate([indexed_lon, indexed_lon[edge] + 360, indexed_lon[edge] - 360])
        indexed_lat = np.concatenate([indexed_lat, indexed_lat[edge], indexed_lat[edge]])
        indexed_pos = np.concatenate([indexed_pos, indexed_pos[edge], indexed_pos[edge]])
    tree = STRtree(points(indexed_lon, indexed_lat))
    result_site, result_target, result_km = [], [], []
    for start in range(0, len(sites), 1000):
        stop = min(start + 1000, len(sites))
        lat = site_lat[start:stop]
        lon = site_lon[start:stop]
        lat_width = RADIUS_KM / 100.0
        lon_width = RADIUS_KM / (100.0 * np.maximum(np.cos(np.deg2rad(lat)), 0.01))
        src, idx = tree.query(box(lon-lon_width, lat-lat_width, lon+lon_width, lat+lat_width))
        if not len(src):
            continue
        site_pos = src + start
        target_pos = indexed_pos[idx]
        unique = np.unique(np.column_stack([site_pos, target_pos]), axis=0)
        site_pos, target_pos = unique[:, 0], unique[:, 1]
        _, _, meters = GEOD.inv(
            site_lon[site_pos], site_lat[site_pos], target_lon[target_pos], target_lat[target_pos]
        )
        inside = meters <= RADIUS_KM * 1000
        result_site.extend(site_pos[inside])
        result_target.extend(target_pos[inside])
        result_km.extend(meters[inside] / 1000)
    return np.asarray(result_site), np.asarray(result_target), np.asarray(result_km)


def local_ecosystems(
    sites: pd.DataFrame, industry: pd.DataFrame, wastewater: pd.DataFrame
) -> dict[str, dict[str, list[dict]]]:
    """Return real facility points and distances, keyed by published site ID."""
    output: dict[str, dict[str, list[dict]]] = {}
    for frame, key in [(industry, "i"), (wastewater, "w")]:
        site_pos, target_pos, distances = _pairs(sites, frame)
        for source, target, km in zip(site_pos, target_pos, distances, strict=True):
            row = frame.iloc[target]
            site_id = str(int(sites.iloc[source]["site_id"]))
            record = {
                "id": str(row.facility_id),
                "name": str(row.facility_name) if pd.notna(row.facility_name) else "Unnamed facility",
                "lat": round(float(row.latitude), 6),
                "lon": round(float(row.longitude), 6),
                "km": round(float(km), 3),
                "type": _sector(row) if key == "i" else "Wastewater treatment plant",
                "naics": str(row.selected_naics_codes) if key == "i" and pd.notna(row.selected_naics_codes) else None,
            }
            output.setdefault(site_id, {"i": [], "w": []})[key].append(record)
    return output

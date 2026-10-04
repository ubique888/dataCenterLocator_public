"""Exact WGS84 point distances and nested radius counts at national scale."""

import numpy as np
import pandas as pd
from shapely import STRtree, box, points

from src.spatial.nearby import GEOD


def _envelopes(lon: np.ndarray, lat: np.ndarray, km: np.ndarray):
    # 100 km per latitude degree and the cosine-adjusted longitude width are
    # conservative supersets for WGS84 distances at these spatial scales.
    lat_width = km / 100.0
    lon_width = km / (100.0 * np.maximum(np.cos(np.deg2rad(lat)), 0.01))
    return box(lon - lon_width, lat - lat_width, lon + lon_width, lat + lat_width)


def radius_metrics(
    sites: pd.DataFrame,
    targets: pd.DataFrame,
    radii_km: tuple[float, ...],
    categories: dict[str, np.ndarray] | None = None,
    sum_values: dict[str, np.ndarray] | None = None,
    chunk_size: int = 5000,
) -> pd.DataFrame:
    """Count targets within each geodesic radius and find exact nearest target.

    `categories` are masks aligned to targets; category counts use the largest
    requested radius that is at most 5 km.
    """
    if not radii_km or sorted(radii_km) != list(radii_km) or min(radii_km) <= 0:
        raise ValueError("radii_km must be positive and ascending")
    categories = {name: np.asarray(mask, dtype=bool) for name, mask in (categories or {}).items()}
    if any(len(mask) != len(targets) for mask in categories.values()):
        raise ValueError("Category masks must align with targets")
    sum_values = {
        name: np.asarray(values, dtype=float)
        for name, values in (sum_values or {}).items()
    }
    if any(len(values) != len(targets) for values in sum_values.values()):
        raise ValueError("Sum values must align with targets")
    n = len(sites)
    result = pd.DataFrame(index=sites.index)
    for radius in radii_km:
        result[f"count_{radius:g}km"] = np.zeros(n, dtype=np.int64)
    category_radius = max((r for r in radii_km if r <= 5), default=radii_km[0])
    for name in categories:
        result[f"{name}_{category_radius:g}km"] = np.zeros(n, dtype=np.int64)
    for name in sum_values:
        for radius in radii_km:
            result[f"{name}_sum_{radius:g}km"] = np.zeros(n, dtype=float)
            result[f"{name}_known_count_{radius:g}km"] = np.zeros(n, dtype=np.int64)
    nearest = np.full(n, -1, dtype=np.int64)
    nearest_km = np.full(n, np.nan)
    if n == 0 or targets.empty:
        result["nearest_target_pos"] = nearest
        result["nearest_km"] = nearest_km
        return result

    site_lat = sites["latitude"].to_numpy(dtype=float)
    site_lon = sites["longitude"].to_numpy(dtype=float)
    target_lat = targets["latitude"].to_numpy(dtype=float)
    target_lon = targets["longitude"].to_numpy(dtype=float)
    valid_target = np.flatnonzero(
        np.isfinite(target_lat) & np.isfinite(target_lon)
        & (np.abs(target_lat) <= 90) & (np.abs(target_lon) <= 180)
    )
    if not len(valid_target):
        result["nearest_target_pos"] = nearest
        result["nearest_km"] = nearest_km
        return result
    indexed_lon = target_lon[valid_target]
    indexed_lat = target_lat[valid_target]
    indexed_target = valid_target.copy()
    edge = np.abs(indexed_lon) >= 170
    if edge.any():
        indexed_lon = np.concatenate(
            [indexed_lon, indexed_lon[edge] + 360, indexed_lon[edge] - 360]
        )
        indexed_lat = np.concatenate([indexed_lat, indexed_lat[edge], indexed_lat[edge]])
        indexed_target = np.concatenate(
            [indexed_target, indexed_target[edge], indexed_target[edge]]
        )
    tree = STRtree(points(indexed_lon, indexed_lat))
    for start in range(0, n, chunk_size):
        stop = min(start + chunk_size, n)
        valid = np.flatnonzero(
            np.isfinite(site_lat[start:stop])
            & np.isfinite(site_lon[start:stop])
            & (np.abs(site_lat[start:stop]) <= 90)
            & (np.abs(site_lon[start:stop]) <= 180)
        ) + start
        if not len(valid):
            continue
        # A planar nearest point gives a geodesic upper bound. Querying every
        # point in that bound then yields the true WGS84 nearest neighbor.
        query_idx, planar_idx = tree.query_nearest(
            points(site_lon[valid], site_lat[valid]), all_matches=False
        )
        anchor_target = indexed_target[planar_idx]
        _, _, anchor_m = GEOD.inv(
            site_lon[valid[query_idx]], site_lat[valid[query_idx]],
            target_lon[anchor_target], target_lat[anchor_target],
        )
        upper_km = np.empty(len(valid), dtype=float)
        upper_km[query_idx] = anchor_m / 1000 + 0.001
        nearest_src, nearest_idx = tree.query(
            _envelopes(site_lon[valid], site_lat[valid], upper_km)
        )
        src = valid[nearest_src]
        target = indexed_target[nearest_idx]
        _, _, distance_m = GEOD.inv(
            site_lon[src], site_lat[src], target_lon[target], target_lat[target]
        )
        order = np.lexsort((target, distance_m, src))
        ordered_src, ordered_target = src[order], target[order]
        ordered_m = distance_m[order]
        first = np.r_[True, ordered_src[1:] != ordered_src[:-1]]
        nearest[ordered_src[first]] = ordered_target[first]
        nearest_km[ordered_src[first]] = ordered_m[first] / 1000

        pair_site, pair_index = tree.query(
            _envelopes(
                site_lon[valid], site_lat[valid],
                np.full(len(valid), radii_km[-1]),
            )
        )
        if not len(pair_site):
            continue
        pair_src = valid[pair_site]
        pair_target = indexed_target[pair_index]
        _, _, pair_m = GEOD.inv(
            site_lon[pair_src], site_lat[pair_src],
            target_lon[pair_target], target_lat[pair_target],
        )
        pair_km = pair_m / 1000
        for radius in radii_km:
            counts = np.bincount(
                pair_src[pair_km <= radius] - start, minlength=stop - start
            )
            result.iloc[start:stop, result.columns.get_loc(f"count_{radius:g}km")] = counts
        for name, mask in categories.items():
            selected = (pair_km <= category_radius) & mask[pair_target]
            counts = np.bincount(
                pair_src[selected] - start, minlength=stop - start
            )
            result.iloc[
                start:stop, result.columns.get_loc(f"{name}_{category_radius:g}km")
            ] = counts
        for name, values in sum_values.items():
            known = np.isfinite(values[pair_target])
            for radius in radii_km:
                selected = known & (pair_km <= radius)
                known_count = np.bincount(
                    pair_src[selected] - start, minlength=stop - start
                )
                value_sum = np.bincount(
                    pair_src[selected] - start,
                    weights=values[pair_target[selected]],
                    minlength=stop - start,
                )
                result.iloc[
                    start:stop,
                    result.columns.get_loc(f"{name}_known_count_{radius:g}km"),
                ] = known_count
                result.iloc[
                    start:stop, result.columns.get_loc(f"{name}_sum_{radius:g}km")
                ] = value_sum
    result["nearest_target_pos"] = nearest
    result["nearest_km"] = nearest_km
    return result

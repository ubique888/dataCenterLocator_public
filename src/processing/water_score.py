"""Capped wastewater proximity and design-flow screening utility."""

import numpy as np
import pandas as pd


def score_water_reuse(sites: pd.DataFrame) -> pd.DataFrame:
    required = {
        "nearest_wwtp_km", "wwtp_count_10km", "wastewater_flow_10km",
        "wwtp_flow_known_count_10km",
    }
    missing = required - set(sites)
    if missing:
        raise ValueError(f"Missing water reuse inputs: {sorted(missing)}")
    result = sites.copy()
    distance = result["nearest_wwtp_km"].to_numpy(dtype=float)
    proximity = np.interp(
        distance, [0, 0.5, 2, 5, 10], [100, 100, 90, 60, 0]
    )
    proximity[~np.isfinite(distance)] = 0
    design_flow = result["wastewater_flow_10km"].fillna(0).to_numpy(dtype=float)
    flow_utility = np.interp(design_flow, [0, 1, 10, 100], [0, 15, 55, 100])
    result["water_reuse_component"] = 0.6 * proximity + 0.4 * flow_utility
    result["water_flow_missing_reason"] = pd.Series(pd.NA, index=result.index, dtype="string")
    unknown = result["wwtp_count_10km"].gt(0) & result[
        "wwtp_flow_known_count_10km"
    ].eq(0)
    result.loc[unknown, "water_flow_missing_reason"] = (
        "Nearby WWTP exists but CWNS current design flow is unreported"
    )
    return result

"""Keep industrial and water symbiosis separate from infrastructure inheritance."""

import numpy as np
import pandas as pd


def _piecewise(values: pd.Series, x: list[float], y: list[float]) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    scores = np.interp(numeric.to_numpy(dtype=float), x, y)
    scores[numeric.isna().to_numpy()] = np.nan
    return pd.Series(scores, index=values.index)


def score_symbiosis(sites: pd.DataFrame) -> pd.DataFrame:
    required = {
        "industrial_sites_5km", "nearest_industrial_sink_km",
        "nearest_wwtp_km", "wastewater_flow_10km", "water_reuse_component",
    }
    missing = required - set(sites)
    if missing:
        raise ValueError(f"Missing symbiosis inputs: {sorted(missing)}")
    result = sites.copy()
    result["industrial_component"] = _piecewise(
        result["industrial_sites_5km"],
        [0, 1, 5, 20, 50, 100], [0, 20, 45, 70, 90, 100],
    )
    result["heat_sink_proximity_component"] = _piecewise(
        result["nearest_industrial_sink_km"],
        [0, 0.5, 1, 2, 5, 10], [100, 100, 90, 75, 45, 0],
    )
    result["wastewater_proximity_component"] = _piecewise(
        result["nearest_wwtp_km"],
        [0, 0.5, 2, 5, 10], [100, 100, 90, 60, 0],
    )
    result["wastewater_availability_component"] = _piecewise(
        result["wastewater_flow_10km"].fillna(0),
        [0, 1, 10, 100], [0, 15, 55, 100],
    )
    if not np.allclose(
        result["water_reuse_component"],
        0.6 * result["wastewater_proximity_component"]
        + 0.4 * result["wastewater_availability_component"],
        atol=1e-9, equal_nan=True,
    ):
        raise ValueError("STEP 5 water score does not match saved components")
    result["symbiosis_score"] = (
        0.25 * result["industrial_component"]
        + 0.25 * result["heat_sink_proximity_component"]
        + 0.50 * result["water_reuse_component"]
    )
    return result

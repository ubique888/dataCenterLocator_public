import pandas as pd

from src.processing.water_score import score_water_reuse
from src.spatial.radius import radius_metrics


def test_flow_sums_and_known_counts_use_reported_values_only() -> None:
    sites = pd.DataFrame({"latitude": [0.0], "longitude": [0.0]})
    plants = pd.DataFrame(
        {"latitude": [0.0, 0.0], "longitude": [0.01, 0.02]}
    )
    metrics = radius_metrics(
        sites, plants, (5, 10), sum_values={"flow": [2.5, float("nan")]}
    )
    assert metrics.loc[0, "count_5km"] == 2
    assert metrics.loc[0, "flow_known_count_5km"] == 1
    assert metrics.loc[0, "flow_sum_5km"] == 2.5


def test_water_score_is_bounded_and_unknown_flow_explained() -> None:
    sites = pd.DataFrame(
        {
            "nearest_wwtp_km": [1.0, 20.0],
            "wwtp_count_10km": [1, 0],
            "wastewater_flow_10km": [float("nan"), 0.0],
            "wwtp_flow_known_count_10km": [0, 0],
        }
    )
    scored = score_water_reuse(sites)
    assert scored["water_reuse_component"].between(0, 100).all()
    assert scored.loc[0, "water_reuse_component"] > 0
    assert pd.notna(scored.loc[0, "water_flow_missing_reason"])
    assert scored.loc[1, "water_reuse_component"] == 0

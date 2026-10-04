import pandas as pd

from src.processing.industrial import selected_codes
from src.spatial.radius import radius_metrics


def test_naics_filter_is_prefix_not_substring() -> None:
    assert selected_codes("213112, 311712, 325199, 999999") == [
        "311712", "325199"
    ]
    assert selected_codes(pd.NA) == []


def test_nested_geodesic_counts_and_dateline_nearest() -> None:
    sites = pd.DataFrame({"latitude": [0.0, 0.0], "longitude": [0.0, 179.99]})
    targets = pd.DataFrame(
        {"latitude": [0.0, 0.0, 0.0], "longitude": [0.005, 0.05, -179.99]}
    )
    metrics = radius_metrics(
        sites, targets, (1, 5, 10), {"food_sites": [True, False, True]}
    )
    assert metrics.loc[0, ["count_1km", "count_5km", "count_10km"]].tolist() == [
        1, 1, 2
    ]
    assert metrics.loc[0, "food_sites_5km"] == 1
    assert metrics.loc[1, "nearest_target_pos"] == 2
    assert 2 < metrics.loc[1, "nearest_km"] < 3

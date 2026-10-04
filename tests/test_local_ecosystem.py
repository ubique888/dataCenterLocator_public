import pandas as pd

from src.processing.local_ecosystem import local_ecosystems
from src.spatial.nearby import GEOD


def test_only_coordinate_backed_facilities_within_5km() -> None:
    sites = pd.DataFrame({"site_id": [7], "lat": [40.0], "lon": [-75.0]})
    _, near_lat, _ = GEOD.fwd(-75.0, 40.0, 0, 4999)
    _, far_lat, _ = GEOD.fwd(-75.0, 40.0, 0, 5001)
    industry = pd.DataFrame({
        "facility_id": ["a", "b", "c"], "facility_name": ["Near", "Far", "No point"],
        "latitude": [near_lat, far_lat, None], "longitude": [-75.0, -75.0, None],
        "selected_naics_codes": ["311111", "325111", "322111"],
        "is_food": [True, False, False], "is_beverage": [False] * 3,
        "is_paper": [False, False, True], "is_chemical": [False, True, False],
        "is_metal": [False] * 3,
    })
    wastewater = pd.DataFrame({
        "facility_id": ["w"], "facility_name": ["Plant"],
        "latitude": [40.0], "longitude": [-75.0],
    })
    result = local_ecosystems(sites, industry, wastewater)["7"]
    assert [item["id"] for item in result["i"]] == ["a"]
    assert result["i"][0]["type"] == "Food"
    assert abs(result["i"][0]["km"] - 4.999) < 0.001
    assert result["w"][0]["km"] == 0

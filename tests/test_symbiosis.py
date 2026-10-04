import pandas as pd

from src.processing.symbiosis import score_symbiosis


def test_symbiosis_excludes_inheritance_inputs() -> None:
    sites = pd.DataFrame(
        {
            "industrial_sites_5km": [20, 20],
            "nearest_industrial_sink_km": [1.0, 1.0],
            "nearest_wwtp_km": [2.0, 2.0],
            "wastewater_flow_10km": [10.0, 10.0],
            "water_reuse_component": [76.0, 76.0],
            "transmission_voltage": [115, 500],
            "acreage": [50, 1000],
        }
    )
    # Water component: 0.6*90 + 0.4*55 = 76.
    scored = score_symbiosis(sites)
    assert scored.loc[0, "symbiosis_score"] == scored.loc[1, "symbiosis_score"]
    assert scored["symbiosis_score"].between(0, 100).all()
    assert scored.loc[0, "wastewater_proximity_component"] == 90
    assert scored.loc[0, "wastewater_availability_component"] == 55

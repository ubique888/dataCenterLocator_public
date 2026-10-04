import pandas as pd

from src.processing.site_features import build_site_features


def test_final_mapping_and_conditional_missingness() -> None:
    source = pd.DataFrame(
        {
            "site_id": [1, 2], "site_name": ["Former station", None],
            "latitude": [40.0, 41.0], "longitude": [-75.0, -76.0],
            "state": ["PA", "PA"], "county": ["X", "Y"],
            "acreage": [100.0, 60.0],
            "former_power_plant": [True, False],
            "former_capacity_mw": [250.0, float("nan")],
            "former_primary_fuel": ["NG", pd.NA],
            "retirement_year": [2020, pd.NA],
            "transmission_voltage": [230.0, 115.0],
            "distance_to_transmission": [0.4, 2.0],
            "substation_voltage": [138.0, float("nan")],
            "distance_to_substation": [0.7, 3.0],
            "distance_to_rail": [1.0, 5.0],
            "distance_to_road": [0.2, 1.0],
            "industrial_sites_1km": [2, 0],
            "industrial_sites_5km": [8, 0],
            "industrial_sites_10km": [20, 1],
            "nearest_industrial_sink_km": [0.2, 11.0],
            "nearest_wwtp_km": [1.0, 15.0],
            "wwtp_count_5km": [1, 0],
            "wastewater_flow_5km": [float("nan"), 0.0],
            "inheritance_score": [80.0, 30.0],
            "symbiosis_score": [75.0, 10.0],
            "power_match_confidence": ["high", "unmatched"],
            "transmission_voltage_review_required": [False, False],
            "substation_voltage_review_required": [False, False],
            "passes_initial_filter": [True, True],
        }
    )
    result = build_site_features(source)
    assert len(result) == 2
    assert result.loc[0, "transmission_kv"] == 230
    assert result.loc[0, "lat"] == 40
    assert result.loc[0, "missing_fields_count"] == 1
    assert result.loc[1, "missing_fields_count"] == 2
    assert result.loc[0, "data_quality_score"] > result.loc[1, "data_quality_score"]
    assert "overall_score" not in result


def test_unmatched_power_fields_do_not_count_as_missing() -> None:
    source = pd.DataFrame(
        {
            "site_id": [1], "site_name": ["Site"],
            "latitude": [40.0], "longitude": [-75.0],
            "state": ["PA"], "county": ["X"], "acreage": [50.0],
            "former_power_plant": [False], "former_capacity_mw": [float("nan")],
            "former_primary_fuel": [pd.NA], "retirement_year": [pd.NA],
            "transmission_voltage": [115.0], "distance_to_transmission": [3.0],
            "substation_voltage": [138.0], "distance_to_substation": [5.0],
            "distance_to_rail": [1.0], "distance_to_road": [1.0],
            "industrial_sites_1km": [0], "industrial_sites_5km": [0],
            "industrial_sites_10km": [0], "nearest_industrial_sink_km": [20.0],
            "nearest_wwtp_km": [20.0], "wwtp_count_5km": [0],
            "wastewater_flow_5km": [0.0], "inheritance_score": [20.0],
            "symbiosis_score": [10.0], "power_match_confidence": ["unmatched"],
            "transmission_voltage_review_required": [False],
            "substation_voltage_review_required": [False],
            "passes_initial_filter": [True],
        }
    )
    result = build_site_features(source)
    assert result.loc[0, "missing_fields_count"] == 0
    assert result.loc[0, "data_quality_score"] == 100

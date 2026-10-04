import pandas as pd

from src.processing.inheritance import score_inheritance


def example_site() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "acreage": [250.0],
            "former_capacity_mw": [500.0],
            "former_power_plant": [True],
            "site_name": ["Duane Arnold Energy Center"],
            "matched_power_plant_name": ["Duane Arnold Energy Center"],
            "power_site_distance_km": [0.1],
            "power_match_confidence": ["very_high"],
            "transmission_voltage": [345.0],
            "distance_to_transmission": [0.25],
            "substation_voltage": [138.0],
            "distance_to_substation": [0.25],
            "distance_to_road": [0.5],
            "distance_to_rail": [1.0],
            "passes_initial_filter": [True],
        }
    )


def test_scores_are_bounded_and_keep_components() -> None:
    scored = score_inheritance(example_site())
    components = [
        "power_legacy_component", "transmission_component",
        "substation_component", "land_component", "transport_component",
        "inheritance_score",
    ]
    assert ((scored[components] >= 0) & (scored[components] <= 100)).all().all()
    assert scored.loc[0, "power_legacy_component"] == 85
    assert pd.isna(scored.loc[0, "score_missing_reason"])


def test_unmatched_power_is_zero_and_missing_input_has_reason() -> None:
    sites = example_site()
    sites.loc[0, "former_power_plant"] = False
    sites.loc[0, "former_capacity_mw"] = float("nan")
    sites.loc[0, "power_match_confidence"] = "unmatched"
    assert score_inheritance(sites).loc[0, "power_legacy_component"] == 0
    sites.loc[0, "distance_to_road"] = float("nan")
    scored = score_inheritance(sites)
    assert pd.isna(scored.loc[0, "inheritance_score"])
    assert "distance_to_road" in scored.loc[0, "score_missing_reason"]


def test_unrelated_nearby_plant_gets_no_legacy_credit() -> None:
    sites = example_site()
    sites.loc[0, "site_name"] = "Coastal Oil Pump Pad"
    sites.loc[0, "matched_power_plant_name"] = "New Boston Generating Station"
    sites.loc[0, "power_site_distance_km"] = 0.8
    scored = score_inheritance(sites)
    assert scored.loc[0, "power_identity_evidence"] == "proximity_only"
    assert scored.loc[0, "power_legacy_component"] == 0


def test_shared_place_name_does_not_prove_power_site_identity() -> None:
    sites = example_site()
    sites.loc[0, "site_name"] = "Shell Oil Deer Park Refinery"
    sites.loc[0, "matched_power_plant_name"] = "Deer Park Plant"
    scored = score_inheritance(sites)
    assert scored.loc[0, "power_identity_evidence"] == "proximity_only"
    assert scored.loc[0, "power_legacy_component"] == 0

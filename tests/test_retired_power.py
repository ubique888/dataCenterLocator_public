import pandas as pd

from src.processing.retired_power import aggregate_retired_plants, match_retired_plants
from src.spatial.nearby import nearest_within_km


def test_aggregate_retired_plants_keeps_history_and_identifies_fully_retired() -> None:
    retired = pd.DataFrame(
        {
            "Plant ID": [10, 10, 20],
            "Plant Name": ["Old A", "Old A", "Old B"],
            "Generator ID": ["A", "B", "C"],
            "Nameplate Capacity (MW)": [100.0, 50.0, 80.0],
            "Energy Source Code": ["NG", "BIT", "BIT"],
            "Retirement Year": [2015, 2020, 2018],
            "Latitude": [40.0, 40.0, 41.0],
            "Longitude": [-100.0, -100.0, -101.0],
        }
    )
    operating = pd.DataFrame({"Plant ID": [10]})

    plants = aggregate_retired_plants(retired, operating)

    assert len(plants) == 2
    a = plants.set_index("plant_id").loc[10]
    assert a["former_capacity_mw"] == 150
    assert a["latest_retirement_year"] == 2020
    assert a["former_primary_fuel"] == "NG"
    assert a["generator_count"] == 2
    assert not a["fully_retired"]
    assert plants.set_index("plant_id").loc[20, "fully_retired"]


def test_nearest_within_km_uses_geodesic_distance_and_radius() -> None:
    sites = pd.DataFrame({"latitude": [0.0, 0.0, 0.0], "longitude": [0.0, 0.013, 0.03]})
    targets = pd.DataFrame({"latitude": [0.0], "longitude": [0.0]})

    indices, distances = nearest_within_km(sites, targets, radius_km=2)

    assert indices.tolist() == [0, 0, -1]
    assert distances[0] == 0
    assert 1 < distances[1] < 2
    assert pd.isna(distances[2])


def test_match_retired_plants_keeps_candidate_rows_and_nearest_confidence() -> None:
    sites = pd.DataFrame(
        {"site_id": [1, 2, 3], "latitude": [0.0] * 3, "longitude": [0.001, 0.013, 0.03]}
    )
    plants = pd.DataFrame(
        {
            "plant_id": [10, 20],
            "plant_name": ["Former", "Still operating"],
            "latitude": [0.0, 0.0],
            "longitude": [0.0, 0.03],
            "former_capacity_mw": [100.0, 200.0],
            "former_primary_fuel": ["BIT", "NG"],
            "latest_retirement_year": [2020, 2022],
            "fully_retired": [True, False],
        }
    )

    result = match_retired_plants(sites, plants)

    assert result.site_id.tolist() == [1, 2, 3]
    assert result.former_power_plant.tolist() == [True, True, False]
    assert result.power_match_confidence.tolist() == ["very_high", "low", "unmatched"]
    assert result.loc[0, "matched_power_plant_id"] == 10
    assert result.loc[0, "matched_power_plant_name"] == "Former"
    assert pd.isna(result.loc[2, "former_capacity_mw"])
    assert result.loc[result.former_power_plant, "power_site_distance_km"].le(2).all()


def test_missing_retired_capacity_stays_missing() -> None:
    retired = pd.DataFrame(
        {
            "Plant ID": [30],
            "Plant Name": ["Unknown capacity"],
            "Generator ID": ["A"],
            "Nameplate Capacity (MW)": [None],
            "Energy Source Code": ["NG"],
            "Retirement Year": [2020],
            "Latitude": [40.0],
            "Longitude": [-100.0],
        }
    )

    plants = aggregate_retired_plants(retired, pd.DataFrame({"Plant ID": []}))

    assert pd.isna(plants.loc[0, "former_capacity_mw"])

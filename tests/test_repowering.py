from pathlib import Path

import pandas as pd
import pytest

from src.processing.repowering import (
    COLUMN_MAPPING,
    build_candidate_map,
    standardize_sites,
    validate_sites,
)


def source_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Cross-Reference Number": [101, 102, 103],
            "Site ID": ["same", "same", "other"],
            "Site Name": ["First", "Second", "Third"],
            "Latitude": [39.0, 40.0, 41.0],
            "Longitude": [-100.0, -101.0, -102.0],
            "Acreage (Acres)": [50.0, 49.9, None],
            "Distance to Nearest Transmission Line (miles)": [3.0, 1.0, 1.0],
            "Nearest Transmission Line kV (kilovolts)": [115.0, 230.0, 230.0],
            "Nearest Transmission Line Status": ["IN SERVICE", "INACTIVE", None],
            "Distance to Nearest Substation (miles)": [5.0, 1.0, 1.0],
            "Nearest Substation Voltage (Volts)": [115.0, 138.0, None],
            "Distance to Nearest Road (miles)": [0.2, 0.3, None],
            "Distance to Nearest Rail (miles)": [1.2, 1.3, None],
            "Program": ["BROWNFIELDS", "BROWNFIELDS", "AML"],
            "Known Landfill": ["Y", None, None],
            "Known Abandoned Mine Land": [None, None, "Y"],
            "State": ["KS", "MO", "IA"],
            "County": ["A", "B", "C"],
        }
    )


def test_standardization_preserves_all_rows_and_applies_inclusive_filter() -> None:
    sites = standardize_sites(source_rows())

    assert COLUMN_MAPPING["Cross-Reference Number"] == "site_id"
    assert sites["site_id"].tolist() == [101, 102, 103]
    assert sites["source_site_id"].tolist() == ["same", "same", "other"]
    assert sites["passes_initial_filter"].tolist() == [True, False, False]
    assert sites["site_type"].tolist() == [
        "known_landfill",
        None,
        "known_abandoned_mine_land",
    ]
    assert sites.loc[0, "transmission_voltage"] == 115
    assert sites.loc[0, "transmission_status"] == "IN SERVICE"
    assert sites.loc[0, "distance_to_substation"] == 5


def test_validation_accepts_duplicate_source_ids_but_rejects_duplicate_reference_ids() -> (
    None
):
    sites = standardize_sites(source_rows())
    validate_sites(sites)

    sites.loc[1, "site_id"] = sites.loc[0, "site_id"]
    with pytest.raises(ValueError, match="site_id"):
        validate_sites(sites)


def test_mixed_numeric_and_text_source_ids_round_trip_to_parquet(
    tmp_path: Path,
) -> None:
    source = source_rows()
    source["Site ID"] = source["Site ID"].astype(object)
    source.loc[1, "Site ID"] = 238836
    sites = standardize_sites(source)
    output = tmp_path / "sites.parquet"

    sites.to_parquet(output, index=False)

    reloaded = pd.read_parquet(output)
    assert reloaded["source_site_id"].tolist() == ["same", "238836", "other"]


@pytest.mark.parametrize(
    ("column", "bad_value"),
    [("latitude", 91), ("longitude", -181), ("acreage", -1)],
)
def test_validation_rejects_invalid_physical_values(
    column: str, bad_value: float
) -> None:
    sites = standardize_sites(source_rows())
    sites.loc[0, column] = bad_value
    with pytest.raises(ValueError, match=column):
        validate_sites(sites)


def test_map_contains_every_passing_site_with_required_popup_fields(
    tmp_path: Path,
) -> None:
    sites = standardize_sites(source_rows())
    output = tmp_path / "map.html"

    build_candidate_map(sites, output)

    html = output.read_text(encoding="utf-8")
    assert (
        "basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}"
        in html
    )
    assert "USGS The National Map" in html
    assert "tile.openstreetmap.org" not in html
    assert '"site_name": "First"' in html
    assert '"site_name": "Second"' not in html
    assert '"acreage": 50.0' in html
    assert '"transmission_voltage": 115.0' in html
    assert '"distance_to_transmission": 3.0' in html
    assert '"distance_to_substation": 5.0' in html

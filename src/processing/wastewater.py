"""Select existing 2022 CWNS publicly owned treatment works and attributes."""

import zipfile
from pathlib import Path

import pandas as pd

TABLES = [
    "FACILITIES", "FACILITIES_CONFIRMED", "FACILITY_TYPES",
    "PHYSICAL_LOCATION", "FLOW", "EFFLUENT",
    "POPULATION_WASTEWATER", "POPULATION_WASTEWATER_CONFIRMED",
]


def _read(archive: zipfile.ZipFile, table: str) -> pd.DataFrame:
    name = next(name for name in archive.namelist() if name.endswith(f"/{table}.csv"))
    with archive.open(name) as source:
        return pd.read_csv(source, dtype="string")


def read_wastewater_facilities(path: Path) -> tuple[pd.DataFrame, dict, dict]:
    """Keep existing treatment plants; do not mistake proposed new plants for supply."""
    with zipfile.ZipFile(path) as archive:
        tables = {name: _read(archive, name) for name in TABLES}
    headers = {name: table.columns.tolist() for name, table in tables.items()}
    facility_types = tables["FACILITY_TYPES"]
    current_ids = set(
        facility_types.loc[
            facility_types["FACILITY_TYPE"].eq("Treatment Plant")
            & facility_types["CHANGE_TYPE"].ne("New"),
            "CWNS_ID",
        ]
    )
    submitted = tables["FACILITIES"].loc[
        tables["FACILITIES"]["CWNS_ID"].isin(current_ids),
        ["CWNS_ID", "FACILITY_ID", "FACILITY_NAME"],
    ].copy()
    submitted["record_status"] = "submitted"
    confirmed_pop = tables["POPULATION_WASTEWATER_CONFIRMED"]
    confirmed = tables["FACILITIES_CONFIRMED"].loc[
        tables["FACILITIES_CONFIRMED"]["CWNS_ID"].isin(confirmed_pop["CWNS_ID"]),
        ["CWNS_ID", "FACILITY_ID", "FACILITY_NAME"],
    ].copy()
    confirmed["record_status"] = "confirmed_only"
    facilities = pd.concat([submitted, confirmed], ignore_index=True)
    if facilities["CWNS_ID"].duplicated().any():
        raise ValueError("CWNS treatment plant IDs must be unique")

    submitted_location = tables["PHYSICAL_LOCATION"].loc[
        :, ["CWNS_ID", "LOCATION_TYPE", "LATITUDE", "LONGITUDE", "DATUM"]
    ]
    confirmed_location = confirmed_pop.loc[
        :, ["CWNS_ID", "LOCATION_TYPE", "LATITUDE", "LONGITUDE", "DATUM"]
    ]
    location = pd.concat([submitted_location, confirmed_location], ignore_index=True)
    location = location.drop_duplicates("CWNS_ID")
    facilities = facilities.merge(location, on="CWNS_ID", how="left", validate="one_to_one")

    flow = tables["FLOW"].loc[
        tables["FLOW"]["FLOW_TYPE"].eq("Total Flow"),
        ["CWNS_ID", "CURRENT_DESIGN_FLOW"],
    ].drop_duplicates("CWNS_ID")
    facilities = facilities.merge(flow, on="CWNS_ID", how="left", validate="one_to_one")
    effluent = tables["EFFLUENT"].loc[
        :, ["CWNS_ID", "CURRENT_EFFLUENT_TREATMENT_LEVEL"]
    ].drop_duplicates("CWNS_ID")
    facilities = facilities.merge(effluent, on="CWNS_ID", how="left", validate="one_to_one")
    population = pd.concat(
        [
            tables["POPULATION_WASTEWATER"].loc[
                :, ["CWNS_ID", "TOTAL_RES_POPULATION_2022"]
            ],
            confirmed_pop.loc[:, ["CWNS_ID", "TOTAL_RES_POPULATION_2022"]],
        ],
        ignore_index=True,
    ).drop_duplicates("CWNS_ID")
    facilities = facilities.merge(
        population, on="CWNS_ID", how="left", validate="one_to_one"
    )
    confirmed_treatment = confirmed_pop.set_index("CWNS_ID")[
        "CURRENT_EFFLUENT_TREATMENT_LEVEL"
    ]
    missing_treatment = facilities["CURRENT_EFFLUENT_TREATMENT_LEVEL"].isna()
    facilities.loc[missing_treatment, "CURRENT_EFFLUENT_TREATMENT_LEVEL"] = (
        facilities.loc[missing_treatment, "CWNS_ID"].map(confirmed_treatment)
    )
    facilities = facilities.rename(
        columns={
            "CWNS_ID": "facility_id", "FACILITY_ID": "source_facility_id",
            "FACILITY_NAME": "facility_name", "LOCATION_TYPE": "location_type",
            "LATITUDE": "latitude", "LONGITUDE": "longitude", "DATUM": "datum",
            "CURRENT_DESIGN_FLOW": "design_flow_mgd",
            "CURRENT_EFFLUENT_TREATMENT_LEVEL": "treatment_level",
            "TOTAL_RES_POPULATION_2022": "population_served",
        }
    )
    for column in ("latitude", "longitude", "design_flow_mgd", "population_served"):
        facilities[column] = pd.to_numeric(facilities[column], errors="coerce")
    # City/county reference positions are not plant coordinates.
    facilities.loc[facilities["location_type"].ne("Point"), ["latitude", "longitude"]] = pd.NA
    valid = (facilities["latitude"].between(-90, 90) & facilities[
        "longitude"
    ].between(-180, 180)).fillna(False)
    facilities.loc[~valid, ["latitude", "longitude"]] = pd.NA
    if facilities["design_flow_mgd"].lt(0).any():
        raise ValueError("Negative CWNS design flow")
    if facilities["population_served"].lt(0).any():
        raise ValueError("Negative CWNS population")
    stats = {
        "submitted_existing_treatment_plants": len(submitted),
        "confirmed_only_treatment_plants": len(confirmed),
        "total_treatment_plants": len(facilities),
        "valid_point_coordinates": int(valid.sum()),
        "missing_or_approximate_coordinates": int((~valid).sum()),
        "reported_current_design_flow": int(facilities["design_flow_mgd"].notna().sum()),
        "reported_treatment_level": int(facilities["treatment_level"].notna().sum()),
        "reported_population_served": int(facilities["population_served"].notna().sum()),
    }
    return facilities, headers, stats

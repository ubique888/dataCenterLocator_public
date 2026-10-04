"""Transparent, capped infrastructure utility scores for EPA candidate sites."""

import re

import numpy as np
import pandas as pd

GENERIC_NAME_WORDS = {
    "a", "and", "at", "co", "company", "corp", "corporation", "electric",
    "energy", "facility", "generating", "generation", "inc", "llc", "lp",
    "of", "plant", "power", "station", "the", "utility", "utilities",
    "unit", "former", "site", "no", "number", "new", "south", "north",
    "east", "west", "center", "centre", "river", "bay", "beach", "point",
    "landfill",
}
POWER_SITE_WORDS = {
    "power", "generating", "generation", "nuclear", "electric", "utility",
    "utilities", "edison", "energy",
}


def _name_words(name: object) -> set[str]:
    if pd.isna(name):
        return set()
    return set(re.findall(r"[a-z]{3,}", str(name).lower()))


def _identity_evidence(row: pd.Series) -> str:
    if not row["former_power_plant"]:
        return "unmatched"
    site_words = _name_words(row["site_name"])
    plant_words = _name_words(row["matched_power_plant_name"])
    shared = (site_words & plant_words) - GENERIC_NAME_WORDS
    # Place names alone (e.g. Deer Park, Baton Rouge) are not site identity.
    if site_words == plant_words and len(site_words) >= 2:
        return "name_corrob"
    if site_words & POWER_SITE_WORDS and (
        len(shared) >= 2
        or bool(shared) and row["power_site_distance_km"] <= 0.5
    ):
        return "name_corrob"
    if site_words & POWER_SITE_WORDS and row["power_site_distance_km"] <= 0.25:
        return "power_site_very_close"
    return "proximity_only"


def _utility(values: pd.Series, anchors: list[tuple[float, float]]) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    result = np.interp(
        numeric.to_numpy(dtype=float),
        [point[0] for point in anchors],
        [point[1] for point in anchors],
    )
    result[numeric.isna().to_numpy()] = np.nan
    return pd.Series(result, index=values.index)


def score_inheritance(sites: pd.DataFrame) -> pd.DataFrame:
    """Score each site; missing inputs remain null with an explicit reason."""
    required = {
        "acreage", "former_capacity_mw", "former_power_plant",
        "power_match_confidence", "transmission_voltage",
        "distance_to_transmission", "distance_to_substation",
        "distance_to_road", "distance_to_rail", "passes_initial_filter",
        "site_name", "matched_power_plant_name", "power_site_distance_km",
    }
    missing = required - set(sites)
    if missing:
        raise ValueError(f"Missing inheritance inputs: {sorted(missing)}")
    result = sites.copy()
    capacity = _utility(
        result["former_capacity_mw"],
        [(0, 0), (25, 25), (100, 50), (500, 85), (1000, 100)],
    )
    confidence = result["power_match_confidence"].map(
        {"very_high": 1.0, "high": 0.85, "medium": 0.65, "low": 0.30}
    )
    result["power_identity_evidence"] = result.apply(_identity_evidence, axis=1)
    identity_factor = result["power_identity_evidence"].map(
        {"name_corrob": 1.0, "power_site_very_close": 0.7,
         "proximity_only": 0.0, "unmatched": 0.0}
    )
    result["power_legacy_component"] = capacity * confidence * identity_factor
    result.loc[result["former_power_plant"].eq(False), "power_legacy_component"] = 0.0

    voltage = _utility(
        result["transmission_voltage"],
        [(0, 0), (115, 30), (138, 45), (230, 70), (345, 90), (500, 100)],
    )
    line_distance = _utility(
        result["distance_to_transmission"],
        [(0, 100), (0.5, 100), (1, 90), (2, 70), (3, 40), (5, 0)],
    )
    result["transmission_component"] = 0.65 * voltage + 0.35 * line_distance
    result["substation_component"] = _utility(
        result["distance_to_substation"],
        [(0, 100), (0.25, 100), (0.5, 90), (1, 75), (2, 55), (5, 0)],
    )
    result["land_component"] = _utility(
        result["acreage"],
        [(0, 0), (50, 20), (100, 40), (250, 70), (500, 90), (1000, 100)],
    )
    road = _utility(
        result["distance_to_road"],
        [(0, 100), (0.5, 100), (1, 85), (2, 60), (5, 20), (10, 0)],
    )
    rail = _utility(
        result["distance_to_rail"],
        [(0, 100), (1, 100), (3, 75), (5, 50), (10, 0)],
    )
    result["transport_component"] = 0.6 * road + 0.4 * rail
    components = [
        "power_legacy_component", "transmission_component",
        "substation_component", "land_component", "transport_component",
    ]
    weights = np.array([0.30, 0.25, 0.20, 0.15, 0.10])
    # A strong grid/land location without corroborated former power infrastructure
    # remains visible, but cannot dominate this inheritance-focused ranking.
    result["inheritance_score"] = (
        result[components].dot(weights) * (0.7 + 0.3 * identity_factor)
    )
    result.loc[result[components].isna().any(axis=1), "inheritance_score"] = np.nan

    missing_inputs = {
        "power_legacy_component": "former_capacity_mw or power_match_confidence",
        "transmission_component": "transmission_voltage or distance_to_transmission",
        "substation_component": "distance_to_substation",
        "land_component": "acreage",
        "transport_component": "distance_to_road or distance_to_rail",
    }
    reasons = [
        "; ".join(
            missing_inputs[column]
            for column in components
            if pd.isna(row[column])
        )
        for _, row in result[components].iterrows()
    ]
    result["score_missing_reason"] = pd.Series(reasons, index=result.index).replace("", pd.NA)
    return result

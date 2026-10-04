"""Export the screened site table into a standalone map-first HTML page."""

import json
import re
from pathlib import Path

import pandas as pd

ASSETS = Path(__file__).resolve().parent


def _number(value: object) -> float | None:
    return float(value) if pd.notna(value) else None


def site_records(sites: pd.DataFrame) -> list[dict]:
    required = {
        "site_id", "site_name", "state", "county", "lat", "lon",
        "acreage", "former_power_plant", "transmission_kv",
        "transmission_distance", "substation_distance",
        "inheritance_score", "symbiosis_score", "data_quality_score",
    }
    missing = required - set(sites)
    if missing:
        raise ValueError(f"Missing frontend fields: {sorted(missing)}")
    if sites["site_id"].duplicated().any():
        raise ValueError("Frontend site IDs must be unique")
    detail_fields = {
        "former_capacity_mw": "formerMw", "matched_power_plant_name": "powerName",
        "former_primary_fuel": "powerFuel", "retirement_year": "retirementYear",
        "power_match_confidence": "powerConfidence", "power_identity_evidence": "powerEvidence",
        "power_site_distance_km": "powerDistanceKm", "substation_voltage": "subVoltageRaw",
        "rail_distance": "railMi", "road_distance": "roadMi",
        "industrial_sites_5km": "industrial5", "food_sites_5km": "food5",
        "beverage_sites_5km": "beverage5", "paper_sites_5km": "paper5",
        "chemical_sites_5km": "chemical5", "metal_sites_5km": "metal5",
        "nearest_industrial_sink_name": "sinkName", "nearest_industrial_sink_naics": "sinkNaics",
        "nearest_industrial_sink_km": "sinkKm", "wwtp_count_5km": "wwtp5",
        "nearest_wwtp_name": "wwtpName", "nearest_wwtp_km": "wwtpKm",
        "nearest_wwtp_design_flow_mgd": "wwtpDesignFlow", "wastewater_flow_5km": "waterFlow5",
        "wwtp_flow_known_count_5km": "wwtpKnownFlow5",
        "power_legacy_component": "powerComponent", "transmission_component": "transComponent",
        "substation_component": "subComponent", "land_component": "landComponent",
        "transport_component": "transportComponent", "industrial_component": "industrialComponent",
        "heat_sink_proximity_component": "heatComponent", "water_reuse_component": "waterComponent",
        "data_quality_missing_fields": "qualityMissing", "missing_fields_count": "missingCount",
    }
    missing_details = set(detail_fields) - set(sites)
    if missing_details:
        raise ValueError(f"Missing detail fields: {sorted(missing_details)}")
    records = [
        {
            "id": int(row.site_id),
            "name": str(row.site_name) if pd.notna(row.site_name) else "Unnamed site",
            "state": str(row.state) if pd.notna(row.state) else "",
            "county": str(row.county) if pd.notna(row.county) else "",
            "lat": float(row.lat),
            "lon": float(row.lon),
            "acreage": _number(row.acreage),
            "former": bool(row.former_power_plant) and row.power_identity_evidence in {"name_corrob", "power_site_very_close"},
            "nearbyPowerRecord": bool(row.former_power_plant),
            "transKv": _number(row.transmission_kv),
            "transMi": _number(row.transmission_distance),
            "subMi": _number(row.substation_distance),
            "inheritance": _number(row.inheritance_score),
            "symbiosis": _number(row.symbiosis_score),
            "quality": _number(row.data_quality_score),
            **{target: (_number(getattr(row, source)) if pd.api.types.is_numeric_dtype(sites[source])
                        else (str(getattr(row, source)) if pd.notna(getattr(row, source)) else None))
               for source, target in detail_fields.items()},
        }
        for row in sites.itertuples(index=False)
    ]
    return records


def build_site_explorer(
    sites: pd.DataFrame,
    output: Path,
    ecosystem: dict | None = None,
    connectivity: dict | None = None,
) -> None:
    records = site_records(sites)
    payload = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    payload = payload.replace("<", "\\u003c").replace("&", "\\u0026")
    ecosystem_payload = json.dumps(
        ecosystem or {}, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    ecosystem_payload = ecosystem_payload.replace("<", "\\u003c").replace("&", "\\u0026")
    connectivity_payload = json.dumps(
        connectivity, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    connectivity_payload = connectivity_payload.replace("<", "\\u003c").replace(
        "&", "\\u0026"
    )
    template = (ASSETS / "site_explorer_template.html").read_text(encoding="utf-8")
    styles = (ASSETS / "site_explorer.css").read_text(encoding="utf-8")
    connectivity_script = (ASSETS / "power_connectivity.js").read_text(encoding="utf-8")
    script = (ASSETS / "site_explorer.js").read_text(encoding="utf-8")
    replacements = {
        "__STYLES__": styles,
        "__SITE_DATA__": payload,
        "__ECOSYSTEM_DATA__": ecosystem_payload,
        "__CONNECTIVITY_DATA__": connectivity_payload,
        "__CONNECTIVITY_HIDDEN__": "" if connectivity is not None else "hidden",
        "__POWER_CONNECTIVITY_SCRIPT__": connectivity_script,
        "__SCRIPT__": script,
    }
    token_pattern = re.compile("|".join(re.escape(token) for token in replacements))
    page = token_pattern.sub(lambda match: replacements[match.group(0)], template)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")

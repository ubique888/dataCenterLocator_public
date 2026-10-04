"""Transform the EPA RE-Powering screening spreadsheet into a site base layer."""

import json
from pathlib import Path

import pandas as pd

# These names come from the "RE-Powering Sites" worksheet in the downloaded file.
COLUMN_MAPPING = {
    "Cross-Reference Number": "site_id",
    "Site ID": "source_site_id",
    "Site Name": "site_name",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Acreage (Acres)": "acreage",
    "Distance to Nearest Transmission Line (miles)": "distance_to_transmission",
    "Nearest Transmission Line kV (kilovolts)": "transmission_voltage",
    "Nearest Transmission Line Status": "transmission_status",
    "Distance to Nearest Substation (miles)": "distance_to_substation",
    "Nearest Substation Voltage (Volts)": "substation_voltage",
    "Distance to Nearest Road (miles)": "distance_to_road",
    "Distance to Nearest Rail (miles)": "distance_to_rail",
    "Program": "source_program",
    "Known Landfill": "source_known_landfill",
    "Known Abandoned Mine Land": "source_known_abandoned_mine_land",
    "State": "state",
    "County": "county",
}

NUMERIC_COLUMNS = (
    "latitude",
    "longitude",
    "acreage",
    "distance_to_transmission",
    "transmission_voltage",
    "distance_to_substation",
    "substation_voltage",
    "distance_to_road",
    "distance_to_rail",
)


def standardize_sites(source: pd.DataFrame) -> pd.DataFrame:
    """Map observed source columns and retain every EPA row with a filter flag."""
    missing = set(COLUMN_MAPPING) - set(source.columns)
    if missing:
        raise ValueError(f"Missing EPA source columns: {sorted(missing)}")

    sites = source.loc[:, list(COLUMN_MAPPING)].rename(columns=COLUMN_MAPPING).copy()
    # EPA mixes numeric and text Site ID cells; identifiers are text, not measures.
    sites["source_site_id"] = sites["source_site_id"].astype("string")
    for column in NUMERIC_COLUMNS:
        sites[column] = pd.to_numeric(sites[column], errors="coerce")

    landfill = sites["source_known_landfill"].eq("Y")
    mine = sites["source_known_abandoned_mine_land"].eq("Y")
    sites["site_type"] = pd.Series(
        [
            "known_landfill_and_abandoned_mine_land"
            if is_landfill and is_mine
            else "known_landfill"
            if is_landfill
            else "known_abandoned_mine_land"
            if is_mine
            else None
            for is_landfill, is_mine in zip(landfill, mine, strict=True)
        ],
        index=sites.index,
        dtype=object,
    )
    sites["passes_initial_filter"] = (
        sites["acreage"].ge(50)
        & sites["distance_to_transmission"].le(3)
        & sites["transmission_voltage"].ge(115)
        & sites["distance_to_substation"].le(5)
    )
    # Keep EPA's reported voltage; flag unusually high values for review.
    sites["transmission_voltage_review_required"] = sites["transmission_voltage"].gt(
        765
    )
    sites["substation_voltage_review_required"] = sites["substation_voltage"].gt(765)
    return sites


def validate_sites(sites: pd.DataFrame) -> None:
    """Fail on broken identifiers or impossible coordinates and physical values."""
    if sites["site_id"].isna().any() or sites["site_id"].duplicated().any():
        raise ValueError("site_id must be present and unique")
    for column, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180)):
        if sites[column].isna().any() or not sites[column].between(lower, upper).all():
            raise ValueError(f"{column} must be present and in [{lower}, {upper}]")
    for column in (
        "acreage",
        "distance_to_transmission",
        "transmission_voltage",
        "distance_to_substation",
        "substation_voltage",
        "distance_to_road",
        "distance_to_rail",
    ):
        if sites[column].lt(0).any():
            raise ValueError(f"{column} cannot be negative")
    if not sites["passes_initial_filter"].isin([True, False]).all():
        raise ValueError("passes_initial_filter must be boolean")


def build_candidate_map(sites: pd.DataFrame, output: Path) -> None:
    """Write a Leaflet map with one clickable canvas point per passing site."""
    passing = sites.loc[sites["passes_initial_filter"]]
    records = [
        {
            "site_id": int(row.site_id),
            "site_name": row.site_name
            if pd.notna(row.site_name)
            else "Name unavailable",
            "latitude": float(row.latitude),
            "longitude": float(row.longitude),
            "acreage": float(row.acreage),
            "transmission_voltage": float(row.transmission_voltage),
            "distance_to_transmission": float(row.distance_to_transmission),
            "distance_to_substation": float(row.distance_to_substation),
        }
        for row in passing.itertuples(index=False)
    ]
    data = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c")
    template = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EPA RE-Powering Candidate Sites</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body,#map{height:100%;margin:0}body{font:14px system-ui,sans-serif}
#summary{position:absolute;z-index:1000;top:12px;left:52px;background:#fff;padding:10px 14px;
border-radius:5px;box-shadow:0 1px 8px #0003;max-width:320px}
#summary strong{display:block;font-size:16px;margin-bottom:3px}.leaflet-popup-content{line-height:1.6}
</style></head><body><div id="map" role="application" aria-label="Map of EPA RE-Powering candidate sites"></div>
<div id="summary"><strong>EPA RE-Powering candidate sites</strong><span id="count"></span><br>
Click a point for acreage and infrastructure distances. Source: EPA screening dataset, 2022 (updated 2023).</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const sites = __DATA__;
const map = L.map('map', {preferCanvas: true}).setView([39, -98], 4);
L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}', {
  maxZoom: 20,
  attribution: 'Map services and data available from <a href="https://www.usgs.gov/">' +
    'U.S. Geological Survey, National Geospatial Program</a> (USGS The National Map)'
}).addTo(map);
const canvas = L.canvas({padding: 0.5});
const escapeHtml = value => String(value).replace(/[&<>"']/g, char =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
for (const site of sites) {
  const popup = `<strong>${escapeHtml(site.site_name)}</strong><br>` +
    `Acreage: ${site.acreage.toLocaleString()} acres<br>` +
    `Transmission: ${site.transmission_voltage} kV, ${site.distance_to_transmission.toFixed(2)} mi<br>` +
    `Substation distance: ${site.distance_to_substation.toFixed(2)} mi`;
  L.circleMarker([site.latitude, site.longitude], {
    renderer: canvas, radius: 3.5, color: '#155e75', fillColor: '#0891b2',
    fillOpacity: 0.6, weight: 0.7
  }).bindPopup(popup).addTo(map);
}
document.getElementById('count').textContent = sites.length.toLocaleString() + ' sites pass the initial filter.';
</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace("__DATA__", data), encoding="utf-8")

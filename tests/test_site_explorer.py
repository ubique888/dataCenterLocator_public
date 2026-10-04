import json
import re
import subprocess
from pathlib import Path

import pandas as pd

from src.visualization.site_explorer import build_site_explorer, site_records


def sample_sites() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "site_id": [1, 2], "site_name": ["Plant <one>", None],
            "state": ["NY", "CA"], "county": ["A", "B"],
            "lat": [40.0, 35.0], "lon": [-73.0, -120.0],
            "acreage": [200.0, 50.0], "former_power_plant": [True, True],
            "transmission_kv": [345.0, 115.0],
            "transmission_distance": [0.4, 3.0],
            "substation_distance": [0.5, 5.0],
            "inheritance_score": [80.0, 30.0],
            "symbiosis_score": [90.0, 25.0],
            "data_quality_score": [95.0, 90.0],
        }
    )
    numeric_detail = [
        "former_capacity_mw", "retirement_year", "power_site_distance_km",
        "substation_voltage", "rail_distance", "road_distance", "industrial_sites_5km",
        "food_sites_5km", "beverage_sites_5km", "paper_sites_5km", "chemical_sites_5km",
        "metal_sites_5km", "nearest_industrial_sink_km", "wwtp_count_5km",
        "nearest_wwtp_km", "nearest_wwtp_design_flow_mgd", "wastewater_flow_5km",
        "wwtp_flow_known_count_5km", "power_legacy_component", "transmission_component",
        "substation_component", "land_component", "transport_component",
        "industrial_component", "heat_sink_proximity_component", "water_reuse_component",
        "missing_fields_count",
    ]
    text_detail = [
        "matched_power_plant_name", "former_primary_fuel", "power_match_confidence",
        "power_identity_evidence", "nearest_industrial_sink_name",
        "nearest_industrial_sink_naics", "nearest_wwtp_name", "data_quality_missing_fields",
    ]
    for name in numeric_detail:
        frame[name] = pd.Series([None, None], dtype="Float64")
    for name in text_detail:
        frame[name] = pd.Series([None, None], dtype="string")
    frame["industrial_sites_5km"] = [8, 0]
    frame["wwtp_count_5km"] = [1, 0]
    frame["former_capacity_mw"] = [820, 1.1]
    frame["power_legacy_component"] = [85, 0]
    frame["power_identity_evidence"] = ["name_corrob", "proximity_only"]
    frame["wastewater_flow_5km"] = [None, 0]
    return frame


def test_records_have_one_site_per_row_and_safe_html(tmp_path: Path) -> None:
    records = site_records(sample_sites())
    assert len(records) == 2
    assert records[0]["id"] == 1
    assert records[0]["former"] is True
    assert records[1]["former"] is False
    assert records[1]["nearbyPowerRecord"] is True
    output = tmp_path / "explorer.html"
    build_site_explorer(sample_sites(), output)
    html = output.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" not in html
    assert "basemap.nationalmap.gov" in html
    assert "\\u003cone>" in html
    match = re.search(r'<script type="application/json" id="site-data">(.*?)</script>', html, re.DOTALL)
    assert match is not None
    assert len(json.loads(match.group(1))) == 2
    assert 'id="inheritance-reason"' in html
    assert 'id="symbiosis-reason"' in html


def test_template_tokens_in_source_text_do_not_replace_template_scripts(tmp_path: Path) -> None:
    sites = sample_sites()
    sites.loc[0, "site_name"] = "__SCRIPT__"
    output = tmp_path / "token-collision.html"

    build_site_explorer(
        sites,
        output,
        ecosystem={"label": "__POWER_CONNECTIVITY_SCRIPT__"},
        connectivity={"meta": {}, "sites": {}, "facilities": {}},
    )

    html = output.read_text(encoding="utf-8")
    match = re.search(
        r'<script type="application/json" id="site-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    records = json.loads(match.group(1))
    assert records[0]["name"] == "__SCRIPT__"

    ecosystem_match = re.search(
        r'<script type="application/json" id="ecosystem-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert ecosystem_match is not None
    assert json.loads(ecosystem_match.group(1)) == {
        "label": "__POWER_CONNECTIVITY_SCRIPT__"
    }


def test_all_seven_filter_boundaries() -> None:
    script = Path(__file__).resolve().parents[1] / "src/visualization/site_explorer.js"
    js = f"""
const {{sitePassesFilters}}=require({json.dumps(str(script))});
const site={{former:true,acreage:50,transKv:115,transMi:3,subMi:5,inheritance:60,symbiosis:75}};
const f={{formerOnly:true,minAcreage:50,minTransKv:115,maxTransMi:3,maxSubMi:5,minInheritance:60,minSymbiosis:75}};
if(!sitePassesFilters(site,f)) process.exit(1);
for(const [key,value] of Object.entries({{former:false,acreage:49,transKv:114,transMi:3.1,subMi:5.1,inheritance:59,symbiosis:74}})){{
  if(sitePassesFilters({{...site,[key]:value}},f)) process.exit(2);
}}
"""
    subprocess.run(["node", "-e", js], check=True)

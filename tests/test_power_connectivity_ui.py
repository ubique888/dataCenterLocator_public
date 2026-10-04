import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/visualization/power_connectivity.js"


def run_node(source):
    subprocess.run(["node", "-e", source], check=True, cwd=ROOT)


def test_connectivity_filters_include_boundaries_zero_and_unknown_when_unbounded():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const boundary={{subKm:0,peerKm:5,peerNetworks:0}};
if(!pc.passesFilters(boundary,{{maxSubKm:0,maxPeerKm:5,minPeerNetworks:0}})) process.exit(1);
if(!pc.passesFilters({{subKm:null,peerKm:null,peerNetworks:null}},{{maxSubKm:null,maxPeerKm:null,minPeerNetworks:null}})) process.exit(2);
if(pc.passesFilters({{subKm:null,peerKm:1,peerNetworks:1}},{{maxSubKm:0,maxPeerKm:null,minPeerNetworks:null}})) process.exit(3);
if(pc.passesFilters({{subKm:1,peerKm:1,peerNetworks:9}},{{maxSubKm:null,maxPeerKm:null,minPeerNetworks:10}})) process.exit(4);
"""
    )


def test_fixed_color_bins_cover_distances_counts_and_missing_values():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const colors=[0,0.5,0.50001,2,2.0001,5,10,25,50,50.01].map(peerKm=>pc.colorForMetric({{peerKm}},'peerKm'));
if(colors[0]!==colors[1] || colors[1]===colors[2] || colors[8]===colors[9]) process.exit(1);
if(pc.colorForMetric({{peerKm:null}},'peerKm')!=='#8a9698') process.exit(2);
const networkColors=[0,1,9,10,49,50,99,100,249,250].map(peerNetworks=>pc.colorForMetric({{peerNetworks}},'peerNetworks'));
if(networkColors[0]===networkColors[1] || networkColors[1]!==networkColors[2] || networkColors[8]===networkColors[9]) process.exit(3);
"""
    )


def test_bubble_radius_helper_has_null_zero_and_cap_behavior():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
if(pc.bubbleRadius(null,100)!==4) process.exit(1);
if(pc.bubbleRadius(0,100)!==4) process.exit(2);
if(pc.bubbleRadius(100,100)!==12) process.exit(3);
if(pc.bubbleRadius(1000,100)!==12) process.exit(4);
"""
    )


def test_threshold_parser_rejects_negative_nonfinite_and_fractional_network_counts():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
if(pc.parseThreshold('',false).value!==null) process.exit(1);
if(!pc.parseThreshold('0',true).valid) process.exit(2);
if(pc.parseThreshold('1.5',true).valid) process.exit(3);
if(pc.parseThreshold('-1',false).valid) process.exit(4);
if(pc.parseThreshold('Infinity',false).valid) process.exit(5);
"""
    )


def test_antimeridian_link_splits_into_short_segments():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const parts=pc.splitAtAntimeridian({{lat:10,lon:179.9}},{{lat:12,lon:-179.9}});
if(parts.length!==2) process.exit(1);
if(parts[0][1][1]!==180 || parts[1][0][1]!==-180) process.exit(2);
if(Math.abs(parts[0][0][1]-parts[0][1][1])>1) process.exit(3);
"""
    )


def test_comparison_domains_are_fixed_from_full_payload_and_log_positions_keep_zero():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const payload={{sites:{{
  '1':{{subKm:0,peerKm:0,peerNetworks:0}},
  '2':{{subKm:2,peerKm:10,peerNetworks:null}},
  '3':{{subKm:200,peerKm:100,peerNetworks:1000}},
  '4':{{subKm:null,peerKm:5,peerNetworks:null}}
}}}};
const domains=pc.comparisonDomains(payload);
if(domains.xMax!==200 || domains.yMax!==100 || domains.networkCap!==950) process.exit(1);
const origin=pc.comparisonPosition(payload.sites['1'],domains);
if(origin.x!==0 || origin.y!==1) process.exit(2);
if(pc.comparisonPosition(payload.sites['4'],domains)!==null) process.exit(3);
const empty=pc.comparisonDomains({{sites:{{'1':{{subKm:0,peerKm:0,peerNetworks:0}}}}}});
if(empty.xMax!==1 || empty.yMax!==1 || empty.networkCap!==1) process.exit(4);
"""
    )


def test_table_sort_keeps_unknown_last_and_breaks_ties_by_site_id():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const payload={{sites:{{
  '9':{{peerKm:5,subKm:1,peerNetworks:0}},
  '2':{{peerKm:5,subKm:1,peerNetworks:null}},
  '7':{{peerKm:null,subKm:2,peerNetworks:4}},
  '3':{{peerKm:1,subKm:null,peerNetworks:9}}
}}}};
const asc=pc.sortVisibleIds(['9','7','2','3'],payload,'peerKm','asc');
const desc=pc.sortVisibleIds(['9','7','2','3'],payload,'peerKm','desc');
if(asc.join(',')!=='3,2,9,7') process.exit(1);
if(desc.join(',')!=='2,9,3,7') process.exit(2);
"""
    )


def test_network_marker_style_separates_unknown_zero_and_selected_points():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const unknown=pc.networkMarkerStyle(null,false);
const zero=pc.networkMarkerStyle(0,false);
const selected=pc.networkMarkerStyle(2,true);
if(unknown.hollow!==true || zero.hollow!==false || zero.radius!==4) process.exit(1);
if(selected.stroke!=='#be6b32' || selected.hollow) process.exit(2);
"""
    )


def test_selection_bridge_refreshes_shared_renderers_without_leaflet():
    bridge = ROOT / "src/visualization/site_explorer.js"
    source = bridge.read_text(encoding="utf-8")
    assert source.count("if (mode === 'connectivity') drawConnectivityMap();") == 2
    assert "mode === 'connectivity' && typeof L !== 'undefined'" not in source


def test_overlapping_plot_points_choose_nearest_then_lower_site_id():
    run_node(
        f"""
const pc=require({json.dumps(str(MODULE))});
const points=[{{id:'9',x:20,y:20,radius:5}},{{id:'2',x:20,y:20,radius:5}},{{id:'1',x:24,y:20,radius:5}}];
if(pc.nearestHit(points,20,20).id!=='2') process.exit(1);
if(pc.nearestHit(points,24,20).id!=='1') process.exit(2);
if(pc.nearestHit(points,100,100)!==null) process.exit(3);
"""
    )


def test_preview_contains_connectivity_controls_map_and_shared_detail_hooks():
    from src.visualization.site_explorer import build_site_explorer
    from test_site_explorer import sample_sites

    payload = {
        "schema_version": 1,
        "meta": {
            "snapshot_id": "20261003T233324Z",
            "retrieved_at": "2026-10-03T23:33:25.668704Z",
            "epa_source_version": "EPA RE-Powering America’s Land Initiative, 2022 release updated 2023",
        },
        "sites": {"1": {"subKm": 2, "peerKm": 3, "peerId": 10, "peerNetworks": 4, "status": "matched"}},
        "facilities": {"10": {"id": 10, "name": "Example", "lat": 38, "lon": -77, "networks": 4}},
    }
    output = ROOT / "outputs/validation/ui-contract-preview.html"
    build_site_explorer(sample_sites(), output, connectivity=payload)
    html = output.read_text(encoding="utf-8")

    for element_id in (
        "connectivity-workspace",
        "connectivity-map",
        "max-substation-km",
        "max-peering-km",
        "min-peering-networks",
        "show-matched-facilities",
        "connectivity-detail",
        "detail-substation-km",
        "detail-peering-km",
        "detail-peering-networks",
        "facility-link",
        "connectivity-compare-canvas",
        "connectivity-table-body",
        "connectivity-pagination",
    ):
        assert f'id="{element_id}"' in html
    assert "connectivity-source-note" in html
    assert 'id="epa-source-version"' in html
    assert 'id="peering-retrieved-at"' in html
    assert "connectivity.meta.epa_source_version" in html
    assert "connectivity.meta.retrieved_at" in html
    output.unlink()

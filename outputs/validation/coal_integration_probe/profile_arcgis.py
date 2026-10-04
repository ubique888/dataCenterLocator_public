"""Profile sampled GeoMine fields and complete PA/WV/VA eAMLIS key index."""
import json
import re
from pathlib import Path

import pandas as pd
from pyproj import Geod
from shapely.geometry import shape

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def read(name):
    return json.loads((OUT/(name+".json")).read_text())

def attrs(name):
    return pd.DataFrame([f["attributes"] for f in read(name)["features"]])

mapping = pd.concat([attrs(f"eamlis_mapping_page_{i}") for i in range(0,8937,2000)],ignore_index=True)
if len(mapping) != read("eamlis_mapping_coalstate_count")["count"] or not mapping.OBJECTID.is_unique:
    raise ValueError("Incomplete or duplicate eAMLIS pages")
if not mapping.AMLIS_KEY.is_unique:
    raise ValueError("eAMLIS mapping is not one row per key")
sites = pd.read_parquet(ROOT / "data/processed/site_features.parquet")
coal = sites.loc[sites.source_program.str.contains("COAL MINE",case=False,na=False)].copy()

def key(value):
    match = re.fullmatch(r"(PA|WV)\s*(\d{1,6})",str(value).strip().upper())
    return match[1]+match[2].zfill(6) if match else None

coal["probe_amlis_key"] = coal.source_site_id.map(key)
links = coal.merge(mapping,left_on="probe_amlis_key",right_on="AMLIS_KEY",how="left",validate="many_to_one")
matched=links.AMLIS_KEY.notna()
coordinate_ok=links.LATITUDE.between(17,72)&links.LONGITUDE.between(-180,-60)
links["probe_distance_km"] = float("nan")
_,_,distance=Geod(ellps="WGS84").inv(links.loc[matched,"lon"].to_numpy(),links.loc[matched,"lat"].to_numpy(),links.loc[matched,"LONGITUDE"].to_numpy(),links.loc[matched,"LATITUDE"].to_numpy())
links.loc[matched,"probe_distance_km"]=distance/1000
links["probe_coordinate_usable"] = matched & coordinate_ok
links["probe_name_agrees"] = [
    pd.notna(b) and re.sub(r"[^a-z0-9]","",str(a).lower()) == re.sub(r"[^a-z0-9]","",str(b).lower())
    for a,b in links[["site_name","PA_NAME"]].itertuples(index=False,name=None)
]
links[["site_id","site_name","state","source_site_id","probe_amlis_key","AMLIS_KEY","PA_NAME","MINE_TYPE","probe_distance_km","probe_coordinate_usable","probe_name_agrees"]].to_csv(OUT/"eamlis_key_link_diagnostic.csv",index=False)

stats=attrs("geomine_source_stats")
problems=attrs("eamlis_linked_problems_sample")
geometries=read("geomine_boundary_geometry")["features"]
postmeta=read("geomine_postuse_meta")
summary={
    "eamlis_mapping_rows_in_three_states":len(mapping),
    "eamlis_unique_mapping_keys":int(mapping.AMLIS_KEY.nunique()),
    "candidate_coal_program_rows":len(coal),
    "candidate_normalizable_keys":int(coal.probe_amlis_key.notna().sum()),
    "candidate_key_matches":int(matched.sum()),
    "candidate_distinct_matched_keys":int(links.loc[matched,"AMLIS_KEY"].nunique()),
    "candidate_matches_invalid_coordinates":int((matched & ~coordinate_ok).sum()),
    "candidate_matches_name_agrees":int(links.probe_name_agrees.sum()),
    "candidate_matches_valid_coordinates_over_1km":int((matched & coordinate_ok & links.probe_distance_km.gt(1)).sum()),
    "matches_by_state":{str(s):{"candidate_rows":len(g),"key_matches":int(g.AMLIS_KEY.notna().sum()),"within_100m":int(g.probe_distance_km.le(.1).sum()),"within_1km":int(g.probe_distance_km.le(1).sum()),"over_1km":int(g.probe_distance_km.gt(1).sum())} for s,g in links.groupby("state")},
    "match_distances_km_quantiles":{str(k):float(v) for k,v in links.probe_distance_km.quantile([0,.5,.9,.95,1]).items()},
    "usable_coordinate_match_distances_km_quantiles":{str(k):float(v) for k,v in links.loc[coordinate_ok,"probe_distance_km"].quantile([0,.5,.9,.95,1]).items()},
    "mapping_mine_type_codes":{str(k):int(v) for k,v in mapping.MINE_TYPE.value_counts(dropna=False).items()},
    "geomine_boundary_features":int(stats.record_count.sum()),
    "geomine_boundary_msha_nonnull":int(stats.msha_nonnull.sum()),
    "geomine_boundary_pa_wv_va_msha_nonnull":stats.loc[stats.contact.isin([20,2,1]),["contact","record_count","msha_nonnull"]].to_dict("records"),
    "geomine_geojson_sample":{"features":len(geometries),"bytes":(OUT/'geomine_boundary_geometry.json').stat().st_size,"geometry_types":[f['geometry']['type'] for f in geometries],"valid_geometries":[shape(f['geometry']).is_valid for f in geometries],"bounds":[shape(f['geometry']).bounds for f in geometries]},
    "postmining_fields":[f["name"] for f in postmeta["fields"]],
    "postmining_domains":{f["name"]:f["domain"] for f in postmeta["fields"] if f.get("domain") and f["name"]!="contact"},
    "problem_rows_per_sample_key":{str(k):int(v) for k,v in problems.AMLIS_KEY.value_counts().items()},
    "problem_statuses_per_sample_key":{str(k):sorted(g.STATUS0.unique().tolist()) for k,g in problems.groupby("AMLIS_KEY")},
}
(OUT/"arcgis_profile.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))

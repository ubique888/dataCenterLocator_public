"""Audit MSHA completeness and candidate linkage; no production data mutations."""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.spatial.nearby import nearest_within_km
from src.processing.site_features import RENAME, build_site_features
from src.visualization.site_explorer import site_records

with zipfile.ZipFile(OUT / "Mines.zip") as archive:
    raw = archive.read("Mines.txt")
mines = pd.read_csv(io.StringIO(raw.decode("latin-1")), sep="|", dtype="string")
coal = mines.loc[mines.COAL_METAL_IND.eq("C")].copy().reset_index(drop=True)
coal["latitude"] = pd.to_numeric(coal.LATITUDE, errors="coerce")
coal["longitude"] = pd.to_numeric(coal.LONGITUDE, errors="coerce")
valid = coal.latitude.between(-90,90) & coal.longitude.between(-180,180) & coal.latitude.ne(0) & coal.longitude.ne(0)
us_plausible = valid & coal.latitude.between(17,72) & coal.longitude.between(-180,-60)
geo = coal.loc[us_plausible].reset_index(drop=True)
sites = pd.read_parquet(ROOT / "data/processed/site_features.parquet")
aml = sites.source_known_abandoned_mine_land.eq("Y")
explicit = sites.source_program.str.contains("COAL MINE",case=False,na=False)

def counts(series):
    return {str(k):int(v) for k,v in series.value_counts(dropna=False).items()}

summary = {
    "msha_rows":len(mines), "msha_unique_ids":int(mines.MINE_ID.nunique()),
    "coal_rows":len(coal), "coal_status":counts(coal.CURRENT_MINE_STATUS),
    "coal_types":counts(coal.CURRENT_MINE_TYPE), "coal_states":counts(coal.STATE),
    "coal_valid_nonzero_coordinates":int(valid.sum()),
    "coal_us_plausible_coordinates":int(us_plausible.sum()),
    "coal_missing_coordinate_rows":int((coal.latitude.isna() | coal.longitude.isna()).sum()),
    "coal_zero_coordinate_rows":int((coal.latitude.eq(0) | coal.longitude.eq(0)).sum()),
    "coal_coordinate_coverage_by_status":{
        str(k):{"rows":len(g),"usable_coordinates":int(us_plausible.loc[g.index].sum())}
        for k,g in coal.groupby("CURRENT_MINE_STATUS")
    },
    "current_sites":len(sites), "current_aml_rows":int(aml.sum()),
    "current_explicit_coal_program_rows":int(explicit.sum()),
    "current_aml_programs":counts(sites.loc[aml,"source_program"]),
    "current_exact_source_id_equal_msha":int(sites.source_site_id.astype("string").isin(coal.MINE_ID).sum()),
    "current_aml_exact_source_id_equal_msha":int(sites.loc[aml,"source_site_id"].astype("string").isin(coal.MINE_ID).sum()),
    "proximity_is_identity":False,
}
positions, distances = nearest_within_km(sites.rename(columns={"lat":"latitude","lon":"longitude"}),geo,5)
summary["proximity_counts"]={
    label:{str(r):int((mask & (positions>=0) & (distances<=r)).sum()) for r in [0.1,0.5,1,2,5]}
    for label,mask in [("all",np.ones(len(sites),dtype=bool)),("aml",aml.to_numpy()),("explicit_coal_program",explicit.to_numpy())]
}
matched = positions>=0
links = sites.loc[matched,["site_id","site_name","source_site_id","source_program","state","lat","lon"]].copy().reset_index(drop=True)
chosen = geo.iloc[positions[matched]].reset_index(drop=True)
for column in ["MINE_ID","CURRENT_MINE_NAME","CURRENT_MINE_STATUS","CURRENT_MINE_TYPE","STATE","LATITUDE","LONGITUDE"]:
    links["nearby_msha_"+column.lower()] = chosen[column]
links["distance_km"] = distances[matched]
links["relationship"] = "proximity_only_not_verified_identity"
links.to_csv(OUT/"msha_proximity_diagnostic.csv",index=False)

# Exercise the existing feature publisher in memory using actual new proximity evidence.
# Keep canonical EPA IDs and scores; this is not a production enrichment run.
probe = sites.rename(columns={v:k for k,v in RENAME.items()}).copy()
probe["coal_probe_nearest_msha_id"] = pd.Series(pd.NA,index=probe.index,dtype="string")
probe.loc[matched,"coal_probe_nearest_msha_id"] = chosen.MINE_ID.to_numpy()
probe["coal_probe_distance_km"] = distances
rebuilt = build_site_features(probe)
score_columns=["inheritance_score","symbiosis_score","data_quality_score"]
summary["feature_contract_dry_run"]={
    "rows":len(rebuilt),"unique_site_ids":bool(rebuilt.site_id.is_unique),
    "ids_preserved":bool(rebuilt.site_id.equals(sites.site_id)),
    "extra_fields_preserved":all(k in rebuilt for k in ["coal_probe_nearest_msha_id","coal_probe_distance_km"]),
    "scores_unchanged":bool(rebuilt[score_columns].equals(sites[score_columns])),
    "production_written":False,
}
export_records=site_records(rebuilt)
summary["existing_frontend_export_dry_run"]={
    "records":len(export_records),
    "new_mine_fields_exported":any("coal_probe" in key for record in export_records for key in record),
    "interpretation":"Explicit exporter mapping must be extended to display new fields.",
}
(OUT/"msha_profile.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))

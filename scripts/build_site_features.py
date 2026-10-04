"""Generate STEP 7 final feature table and diagnostics."""

import json
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

from src.processing.site_features import REQUIRED_COLUMNS, build_site_features

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/candidate_sites_symbiosis.parquet"
OUTPUT = ROOT / "data/processed/site_features.parquet"
VALIDATION = ROOT / "outputs/validation"
TOP_COLUMNS = [
    "site_id", "site_name", "state", "inheritance_score", "symbiosis_score",
    "data_quality_score", "power_identity_evidence", "former_capacity_mw",
    "transmission_kv", "transmission_distance", "industrial_sites_5km",
    "nearest_industrial_sink_km", "nearest_wwtp_km", "wastewater_flow_5km",
]


def main() -> None:
    upstream = pd.read_parquet(INPUT)
    sites = build_site_features(upstream)
    if len(sites) != int(upstream["passes_initial_filter"].sum()):
        raise ValueError("Filtered candidate count changed")
    if not set(REQUIRED_COLUMNS).issubset(sites.columns):
        raise ValueError("Final table lacks required fields")
    for score in ("inheritance_score", "symbiosis_score", "data_quality_score"):
        if not sites[score].between(0, 100).all():
            raise ValueError(f"Invalid {score} range")
    for column in (
        "acreage", "former_capacity_mw", "transmission_kv",
        "transmission_distance", "substation_distance", "rail_distance",
        "road_distance", "industrial_sites_1km", "industrial_sites_5km",
        "industrial_sites_10km", "nearest_industrial_sink_km",
        "nearest_wwtp_km", "wwtp_count_5km", "wastewater_flow_5km",
    ):
        if sites[column].lt(0).any():
            raise ValueError(f"Negative {column}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(OUTPUT, index=False)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    missingness = pd.DataFrame(
        {
            "column": sites.columns,
            "missing_count": sites.isna().sum().to_numpy(dtype=int),
        }
    )
    missingness["missing_fraction"] = missingness["missing_count"] / len(sites)
    missingness.to_csv(VALIDATION / "step7_missingness.csv", index=False)
    top_inheritance = sites.sort_values(
        ["inheritance_score", "symbiosis_score"], ascending=False
    ).head(20)
    top_symbiosis = sites.sort_values(
        ["symbiosis_score", "inheritance_score"], ascending=False
    ).head(20)
    q_inheritance = float(sites["inheritance_score"].quantile(0.75))
    q_symbiosis = float(sites["symbiosis_score"].quantile(0.75))
    dual_pool = sites.loc[
        sites["inheritance_score"].ge(q_inheritance)
        & sites["symbiosis_score"].ge(q_symbiosis)
    ]
    top_dual = dual_pool.sort_values(
        ["inheritance_score", "symbiosis_score"], ascending=False
    ).head(20)
    for name, table in (
        ("step7_top20_inheritance.csv", top_inheritance),
        ("step7_top20_symbiosis.csv", top_symbiosis),
        ("step7_top20_dual.csv", top_dual),
    ):
        table[TOP_COLUMNS].to_csv(VALIDATION / name, index=False)
    numeric_ranges = {
        name: {"min": float(sites[name].min()), "max": float(sites[name].max())}
        for name in sites
        if is_numeric_dtype(sites[name]) and sites[name].notna().any()
    }
    summary = {
        "upstream_rows": len(upstream),
        "candidate_rows": len(sites),
        "column_count": len(sites.columns),
        "duplicate_site_ids": int(sites["site_id"].duplicated().sum()),
        "data_quality_score_range": numeric_ranges["data_quality_score"],
        "missing_fields_count_range": numeric_ranges["missing_fields_count"],
        "numeric_ranges": numeric_ranges,
        "dual_pool_definition": "At or above each passing-site score's 75th percentile; ranked by inheritance, then symbiosis; no overall score",
        "dual_pool_count": len(dual_pool),
        "dual_pool_thresholds": {
            "inheritance": q_inheritance, "symbiosis": q_symbiosis,
        },
        "top20_site_ids": {
            "inheritance": top_inheritance["site_id"].astype(int).tolist(),
            "symbiosis": top_symbiosis["site_id"].astype(int).tolist(),
            "dual": top_dual["site_id"].astype(int).tolist(),
        },
    }
    (VALIDATION / "step7_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "numeric_ranges"}, indent=2))


if __name__ == "__main__":
    main()

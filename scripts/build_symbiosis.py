"""Build STEP 6 symbiosis axis, quadrant list, and standalone scatter HTML."""

import json
from pathlib import Path

import pandas as pd

from src.processing.symbiosis import score_symbiosis
from src.visualization.scatter import build_scatter

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/candidate_sites_water.parquet"
OUTPUT = ROOT / "data/processed/candidate_sites_symbiosis.parquet"
VALIDATION = ROOT / "outputs/validation"
COMPONENTS = [
    "industrial_component", "heat_sink_proximity_component",
    "wastewater_proximity_component", "wastewater_availability_component",
    "water_reuse_component", "symbiosis_score",
]
HIGH_INHERITANCE = 60.0
HIGH_SYMBIOSIS = 75.0


def main() -> None:
    sites = score_symbiosis(pd.read_parquet(INPUT))
    for column in COMPONENTS:
        if not sites[column].dropna().between(0, 100).all():
            raise ValueError(f"{column} outside [0,100]")
    if sites[COMPONENTS].isna().any().any():
        raise ValueError("Symbiosis components must be complete for every site")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(OUTPUT, index=False)
    passing = sites.loc[sites["passes_initial_filter"]].copy()
    inheritance_threshold = HIGH_INHERITANCE
    symbiosis_threshold = HIGH_SYMBIOSIS
    upper_right = passing.loc[
        passing["inheritance_score"].ge(inheritance_threshold)
        & passing["symbiosis_score"].ge(symbiosis_threshold)
    ].sort_values(["inheritance_score", "symbiosis_score"], ascending=False)
    columns = [
        "site_id", "site_name", "state", "inheritance_score",
        "symbiosis_score", "power_identity_evidence", "industrial_sites_5km",
        "nearest_industrial_sink_km", "wwtp_count_5km", "nearest_wwtp_km",
        "wastewater_flow_10km", *COMPONENTS[:-1],
    ]
    VALIDATION.mkdir(parents=True, exist_ok=True)
    upper_right[columns].to_csv(VALIDATION / "step6_upper_right.csv", index=False)
    build_scatter(
        passing, VALIDATION / "inheritance_vs_symbiosis.html",
        inheritance_threshold, symbiosis_threshold,
    )
    summary = {
        "sites_enriched": len(sites),
        "passing_sites_plotted": len(passing),
        "high_inheritance_threshold": inheritance_threshold,
        "high_symbiosis_threshold": symbiosis_threshold,
        "upper_right_count": len(upper_right),
        "symbiosis_score_range": {
            "min": float(passing["symbiosis_score"].min()),
            "max": float(passing["symbiosis_score"].max()),
        },
        "upper_right_top20_site_ids": upper_right.head(20)["site_id"].astype(int).tolist(),
        "overall_score_created": False,
    }
    (VALIDATION / "step6_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(upper_right[columns[:11]].head(20).to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

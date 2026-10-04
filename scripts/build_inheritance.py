"""Generate STEP 3 components, ranked table, and validation summary."""

import json
from pathlib import Path

import pandas as pd

from src.processing.inheritance import score_inheritance

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/processed/candidate_sites_power.parquet"
OUTPUT = ROOT / "data/processed/candidate_sites_inheritance.parquet"
VALIDATION = ROOT / "outputs/validation"
COMPONENTS = [
    "power_legacy_component", "transmission_component", "substation_component",
    "land_component", "transport_component", "inheritance_score",
]


def main() -> None:
    sites = score_inheritance(pd.read_parquet(INPUT))
    passing = sites.loc[sites["passes_initial_filter"]]
    if passing[COMPONENTS].isna().any().any():
        raise ValueError("Passing candidate has unexplained missing inheritance score")
    for column in COMPONENTS:
        if not sites[column].dropna().between(0, 100).all():
            raise ValueError(f"{column} outside [0, 100]")
    if sites["inheritance_score"].isna().ne(sites["score_missing_reason"].notna()).any():
        raise ValueError("Missing-score reason is inconsistent")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(OUTPUT, index=False)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    top = (
        passing.sort_values("inheritance_score", ascending=False)
        .drop_duplicates(["site_name", "latitude", "longitude"])
        .head(20)
    )
    columns = [
        "site_id", "site_name", "state", "inheritance_score",
        "former_capacity_mw", "matched_power_plant_name",
        "power_site_distance_km", "power_match_confidence", "power_identity_evidence",
        "transmission_voltage",
        "distance_to_transmission", "distance_to_substation", "acreage",
        *COMPONENTS[:-1],
    ]
    top[columns].to_csv(VALIDATION / "step3_top20.csv", index=False)
    summary = {
        "all_sites": len(sites),
        "passing_sites": len(passing),
        "passing_scores_missing": int(passing["inheritance_score"].isna().sum()),
        "score_missing_count": int(sites["inheritance_score"].isna().sum()),
        "component_ranges": {
            column: {"min": float(sites[column].min()), "max": float(sites[column].max())}
            for column in COMPONENTS
        },
        "top20_site_ids": top["site_id"].astype(int).tolist(),
        "top20_with_power_identity_evidence": int(
            top["power_identity_evidence"].isin(
                ["name_corrob", "power_site_very_close"]
            ).sum()
        ),
        "top20_without_power_identity_evidence": top.loc[
            ~top["power_identity_evidence"].isin(
                ["name_corrob", "power_site_very_close"]
            ), "site_id"
        ].astype(int).tolist(),
    }
    (VALIDATION / "step3_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(top[columns[:10]].to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

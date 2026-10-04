"""Build the standalone STEP 8 site map."""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.processing.local_ecosystem import local_ecosystems
from src.visualization.power_connectivity import connectivity_payload
from src.visualization.site_explorer import build_site_explorer

DEFAULT_OUTPUT = ROOT / "outputs/infrastructure_inheritance_symbiosis.html"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectivity-features", type=Path)
    parser.add_argument("--peering-facilities", type=Path)
    parser.add_argument("--peering-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    provided = [
        args.connectivity_features is not None,
        args.peering_facilities is not None,
        args.peering_manifest is not None,
    ]
    if any(provided) and not all(provided):
        parser.error(
            "--connectivity-features, --peering-facilities, and "
            "--peering-manifest must be provided together"
        )
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    sites = pd.read_parquet(ROOT / "data/processed/site_features.parquet")
    industry = pd.read_parquet(ROOT / "data/processed/industrial_facilities.parquet")
    wastewater = pd.read_parquet(ROOT / "data/processed/wastewater_facilities.parquet")
    ecosystem = local_ecosystems(sites, industry, wastewater)
    industrial_mismatches = []
    wastewater_mismatches = []
    for row in sites.itertuples(index=False):
        nearby = ecosystem.get(str(int(row.site_id)), {"i": [], "w": []})
        if len(nearby["i"]) != row.industrial_sites_5km:
            industrial_mismatches.append(int(row.site_id))
        if len(nearby["w"]) != row.wwtp_count_5km:
            wastewater_mismatches.append(int(row.site_id))
    if industrial_mismatches or wastewater_mismatches:
        raise ValueError(
            f"Local match counts differ: industry {industrial_mismatches[:10]}, "
            f"wastewater {wastewater_mismatches[:10]}"
        )
    summary = {
        "candidate_sites": len(sites),
        "sites_with_local_facilities": len(ecosystem),
        "industrial_matches_within_5km": sum(len(v["i"]) for v in ecosystem.values()),
        "wastewater_matches_within_5km": sum(len(v["w"]) for v in ecosystem.values()),
        "industrial_count_mismatches": industrial_mismatches,
        "wastewater_count_mismatches": wastewater_mismatches,
        "distance_method": "WGS84 pyproj.Geod.inv, <= 5 km",
        "coordinate_policy": "FRS/CWNS source points are embedded; HIFLD/FRA source geometry is queried live; EPA nearest-asset distances remain text-only",
    }
    (ROOT / "outputs/validation/step10_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    connectivity = None
    if args.connectivity_features is not None:
        connectivity_metrics = pd.read_parquet(args.connectivity_features)
        facilities = pd.read_parquet(args.peering_facilities)
        manifest = json.loads(args.peering_manifest.read_text(encoding="utf-8"))
        connectivity = connectivity_payload(sites, connectivity_metrics, facilities, manifest)
    build_site_explorer(sites, args.output, ecosystem, connectivity)
    print(f"Wrote {len(sites):,} sites and {sum(len(v['i'])+len(v['w']) for v in ecosystem.values()):,} facility matches to {args.output}")


if __name__ == "__main__":
    main()

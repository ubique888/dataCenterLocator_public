"""Create a reproducible metric coverage summary and review Markdown report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_power_connectivity import (
    DEFAULT_SITES,
    load_ready_snapshot,
)
from src.processing.power_connectivity import CONNECTIVITY_COLUMNS

DEFAULT_METRICS = ROOT / "data/processed/site_connectivity_features.parquet"
DEFAULT_SUMMARY = ROOT / "outputs/validation/power_connectivity_summary.json"
DEFAULT_REVIEW = ROOT / "outputs/validation/power_connectivity_review.md"
RANDOM_SEED = 20261003
METRIC_DEFINITIONS = {
    "substation_distance_km": {
        "label": "Nearest substation distance",
        "unit": "km",
        "direction": "smaller is geographically closer",
        "definition": "Existing EPA nearest-substation distance in miles × 1.609344.",
    },
    "peering_facility_distance_km": {
        "label": "Nearest listed IXP facility distance",
        "unit": "km",
        "direction": "smaller is geographically closer",
        "definition": "WGS84 ellipsoidal geodesic to the nearest eligible US PeeringDB facility hosting an IXP.",
    },
    "peering_facility_network_count": {
        "label": "Networks at that nearest facility",
        "unit": "registered networks",
        "direction": "larger is more networks listed in PeeringDB",
        "definition": "PeeringDB net_count from the same facility selected for the nearest-facility distance.",
    },
}


def _validated_ids(frame: pd.DataFrame, column: str, label: str) -> list[int]:
    if column not in frame:
        raise ValueError(f"{label} missing {column}")
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        raise ValueError(f"{label} IDs must be non-null")
    raw = values.to_numpy(dtype="float64")
    if not np.isfinite(raw).all() or not (raw > 0).all() or not (raw == np.floor(raw)).all():
        raise ValueError(f"{label} IDs must be positive integers")
    ids = values.astype("int64").tolist()
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} IDs must be unique")
    return ids


def _json_number(value: Any, *, integer: bool = False) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("metric values must be numeric or null") from error
    if not np.isfinite(number) or number < 0:
        raise ValueError("metric values must be finite and nonnegative")
    if integer:
        if not number.is_integer():
            raise ValueError("network count values must be integers")
        return int(number)
    return number


def _page_facts(manifest: dict[str, Any]) -> tuple[list[dict], str]:
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("manifest must contain a complete page traversal")
    page_facts = []
    hasher = hashlib.sha256()
    total = 0
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError(f"manifest page {index} must be an object")
        file = page.get("file")
        digest = page.get("sha256")
        count = page.get("count")
        if not isinstance(file, str) or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"manifest page {index} is missing a valid file/hash")
        try:
            int(digest, 16)
        except ValueError as error:
            raise ValueError(f"manifest page {index} hash is not hexadecimal") from error
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"manifest page {index} count must be a nonnegative integer")
        if page.get("http_status") not in (None, 200):
            raise ValueError(f"manifest page {index} is not HTTP 200")
        total += count
        hasher.update(f"{file}\n{digest}\n".encode("utf-8"))
        page_facts.append(
            {
                "file": file,
                "sha256": digest,
                "count": count,
                "http_status": page.get("http_status"),
                "started_at": page.get("started_at"),
                "ended_at": page.get("ended_at"),
                "parameters": page.get("parameters"),
            }
        )
    if total != manifest.get("raw_row_count"):
        raise ValueError("manifest raw row count does not match page counts")
    if pages[-1].get("count") != 0:
        raise ValueError("manifest is missing its terminal successful empty page")
    return page_facts, hasher.hexdigest()


def _example(site_id: int, metric: Any, facility_id: Any, value: Any) -> dict[str, Any]:
    if value is not None and pd.notna(value):
        value = int(value) if metric == "peering_facility_network_count" else float(value)
    return {
        "site_id": int(site_id),
        "facility_id": int(facility_id) if pd.notna(facility_id) else None,
        "value": value,
    }


def build_connectivity_report(
    sites: pd.DataFrame,
    metrics: pd.DataFrame,
    facilities: pd.DataFrame,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Return coverage metrics and their human-readable, source-traceable report."""
    if manifest.get("schema_version") != 1 or manifest.get("status") != "ready":
        raise ValueError("report requires a ready schema-v1 PeeringDB manifest")
    snapshot_id = manifest.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("manifest snapshot ID is missing")
    if metrics.columns.tolist() != CONNECTIVITY_COLUMNS:
        raise ValueError("connectivity metric table has an unexpected schema")
    site_ids = _validated_ids(sites, "site_id", "site")
    metric_ids = _validated_ids(metrics, "site_id", "connectivity metric")
    facility_ids = _validated_ids(facilities, "facility_id", "facility")
    if set(site_ids) != set(metric_ids) or len(site_ids) != len(metric_ids):
        raise ValueError("site ID sets must match exactly between base and metric tables")
    if metrics["peering_snapshot_id"].isna().any() or not metrics[
        "peering_snapshot_id"
    ].astype(str).eq(snapshot_id).all():
        raise ValueError("metric snapshot does not match PeeringDB manifest")
    if facilities["snapshot_id"].isna().any() or not facilities[
        "snapshot_id"
    ].astype(str).eq(snapshot_id).all():
        raise ValueError("facility dimension snapshot does not match manifest")

    metrics_by_site = metrics.assign(_site_id=pd.to_numeric(metrics["site_id"]).astype("int64")).set_index("_site_id")
    facilities_by_id = facilities.assign(
        _facility_id=pd.to_numeric(facilities["facility_id"]).astype("int64")
    ).set_index("_facility_id")
    referenced: list[int] = []
    for row in metrics.itertuples(index=False):
        facility_id = row.peering_facility_id
        count = _json_number(row.peering_facility_network_count, integer=True)
        if pd.notna(facility_id):
            facility_id = int(facility_id)
            if facility_id not in facilities_by_id.index:
                raise ValueError(f"unknown facility ID {facility_id}")
            referenced.append(facility_id)
            dimension_count = _json_number(
                facilities_by_id.loc[facility_id, "network_count"], integer=True
            )
            if count != dimension_count:
                raise ValueError("network count differs from referenced facility")
        elif count is not None:
            raise ValueError("network count is present without a nearest facility")
    if len(referenced) != len(metrics["peering_facility_id"].dropna()):
        raise ValueError("nearest-facility relation count changed")

    normalization = manifest.get("normalization")
    if not isinstance(normalization, dict):
        raise ValueError("manifest normalization summary is missing")
    if normalization.get("snapshot_id") != snapshot_id:
        raise ValueError("manifest normalization snapshot does not match")
    if normalization.get("raw_count") != manifest.get("raw_row_count"):
        raise ValueError("manifest normalization raw count does not match pages")
    if normalization.get("eligible_count") != len(facilities):
        raise ValueError("manifest eligible facility count does not match table")
    if normalization.get("network_count_missing") != int(facilities["network_count"].isna().sum()):
        raise ValueError("manifest missing network-count coverage does not match table")
    pages, snapshot_hash = _page_facts(manifest)

    metric_report: dict[str, Any] = {}
    for column, definition in METRIC_DEFINITIONS.items():
        if column not in metrics:
            raise ValueError(f"connectivity table missing metric {column}")
        integer = column == "peering_facility_network_count"
        values = [
            _json_number(value, integer=integer) for value in metrics[column].tolist()
        ]
        enriched = metrics[["site_id", "peering_facility_id"]].copy()
        enriched["value"] = pd.Series(values, dtype="object")
        known = enriched.loc[enriched["value"].notna()]
        unknown = enriched.loc[enriched["value"].isna()].sort_values("site_id")
        zeros = int(sum(value == 0 for value in values if value is not None))
        ascending = known.sort_values(["value", "site_id"], ascending=[True, True], kind="stable")
        descending = known.sort_values(["value", "site_id"], ascending=[False, True], kind="stable")
        metric_report[column] = {
            **definition,
            "row_count": int(len(metrics)),
            "known_count": int(len(known)),
            "unknown_count": int(len(unknown)),
            "zero_count": zeros,
            "minimum": (
                int(known["value"].min()) if integer and len(known)
                else float(known["value"].min()) if len(known) else None
            ),
            "maximum": (
                int(known["value"].max()) if integer and len(known)
                else float(known["value"].max()) if len(known) else None
            ),
            "median": float(known["value"].median()) if len(known) else None,
            "minimum_examples": [
                _example(row.site_id, column, row.peering_facility_id, row.value)
                for row in ascending.head(5).itertuples(index=False)
            ],
            "maximum_examples": [
                _example(row.site_id, column, row.peering_facility_id, row.value)
                for row in descending.head(5).itertuples(index=False)
            ],
            "unknown_examples": [
                _example(row.site_id, column, row.peering_facility_id, None)
                for row in unknown.head(5).itertuples(index=False)
            ],
        }

    sample_ids = np.random.default_rng(RANDOM_SEED).choice(
        np.asarray(site_ids, dtype=np.int64), size=min(5, len(site_ids)), replace=False
    ) if site_ids else []
    sample_rows = []
    for site_id in sample_ids:
        metric = metrics_by_site.loc[int(site_id)]
        sample_rows.append(
            {
                "site_id": int(site_id),
                "facility_id": (
                    int(metric["peering_facility_id"])
                    if pd.notna(metric["peering_facility_id"])
                    else None
                ),
                "substation_distance_km": _json_number(metric["substation_distance_km"]),
                "peering_facility_distance_km": _json_number(
                    metric["peering_facility_distance_km"]
                ),
                "peering_facility_network_count": _json_number(
                    metric["peering_facility_network_count"], integer=True
                ),
            }
        )

    statuses = Counter(metrics["connectivity_status"].astype(str))
    candidate_linkage = {
        "site_rows": int(len(sites)),
        "metric_rows": int(len(metrics)),
        "site_ids_match_exactly": True,
        "status_counts": dict(sorted(statuses.items())),
        "nearest_facility_relations": int(len(referenced)),
        "unique_nearest_facility_count": int(len(set(referenced))),
        "all_references_valid": True,
        "network_count_matches_referenced_facility": True,
    }
    summary = {
        "schema_version": 1,
        "candidate_scope": "Existing EPA screened candidates · ≥50-acre source cohort",
        "epa_source_version": "EPA RE-Powering America’s Land Initiative, 2022 release updated 2023",
        "peeringdb": {
            "snapshot_id": snapshot_id,
            "status": manifest["status"],
            "started_at": manifest.get("started_at"),
            "completed_at": manifest.get("completed_at"),
            "retrieved_at": manifest.get("retrieved_at"),
            "raw_row_count": int(manifest["raw_row_count"]),
            "eligible_facility_count": int(normalization["eligible_count"]),
            "rejected_record_count": int(normalization["rejected_count"]),
            "rejected_by_reason": dict(sorted(normalization.get("rejected_by_reason", {}).items())),
            "network_count_missing_facilities": int(normalization["network_count_missing"]),
            "page_count": int(len(pages)),
            "pages": pages,
            "snapshot_sha256": snapshot_hash,
            "hash_method": "SHA-256 over each manifest-ordered page file path, newline, page SHA-256, newline.",
        },
        "candidate_linkage": candidate_linkage,
        "metrics": metric_report,
        "fixed_random_sample": {
            "seed": RANDOM_SEED,
            "selection": "numpy default_rng(seed).choice without replacement; emitted in draw order",
            "rows": sample_rows,
        },
        "limitations": [
            "The 8,479 rows are the existing EPA screened cohort; they are not a national inventory of small urban or industrial parcels.",
            "PeeringDB facilities are US records with at least one listed IXP; this is not a complete fiber, carrier PoP, or data-center inventory.",
            "Geographic proximity does not establish available power, interconnection capacity, network latency, bandwidth, route diversity, or service rights.",
            "No combined score or 100 MW feasibility certification is derived from these three indicators.",
        ],
    }
    markdown = render_connectivity_review(summary)
    return summary, markdown


def _format_value(value: Any, unit: str) -> str:
    if value is None:
        return "Unknown"
    if unit == "registered networks":
        return f"{int(value):,}"
    return f"{float(value):,.4f} {unit}"


def render_connectivity_review(summary: dict[str, Any]) -> str:
    source = summary["peeringdb"]
    lines = [
        "# Power & connectivity coverage review",
        "",
        f"- Candidate cohort: {summary['candidate_scope']}",
        f"- EPA source: {summary['epa_source_version']}",
        f"- PeeringDB snapshot: `{source['snapshot_id']}` ({source['status']})",
        f"- Retrieval window: {source['started_at']} to {source['completed_at']}",
        f"- Snapshot SHA-256: `{source['snapshot_sha256']}`",
        "",
        "## PeeringDB coverage",
        "",
        "| Item | Count / value |",
        "|---|---:|",
        f"| US source facility rows | {source['raw_row_count']:,} |",
        f"| Eligible IXP-hosting facilities | {source['eligible_facility_count']:,} |",
        f"| Rejected source rows | {source['rejected_record_count']:,} |",
        f"| Eligible facilities with unknown network count | {source['network_count_missing_facilities']:,} |",
        f"| Snapshot pages, including terminal empty page | {source['page_count']:,} |",
        "",
        "Rejected rows by reason:",
        "",
    ]
    if source["rejected_by_reason"]:
        lines.extend(f"- `{reason}`: {count:,}" for reason, count in source["rejected_by_reason"].items())
    else:
        lines.append("- None")
    lines.extend([
        "",
        "Page file hashes are listed in `power_connectivity_summary.json`; the combined hash covers the ordered file paths and hashes. The API traversal is not a transactional snapshot, so the retrieval interval is part of the source record.",
        "",
        "## Candidate linkage",
        "",
        f"- Base sites and metric rows: {summary['candidate_linkage']['site_rows']:,} / {summary['candidate_linkage']['metric_rows']:,}; exact ID match: {summary['candidate_linkage']['site_ids_match_exactly']}.",
        f"- Connectivity states: `{json.dumps(summary['candidate_linkage']['status_counts'], ensure_ascii=False)}`.",
        f"- Nearest-facility relations: {summary['candidate_linkage']['nearest_facility_relations']:,} across {summary['candidate_linkage']['unique_nearest_facility_count']:,} unique facilities; relation and same-facility network-count checks passed.",
        "",
        "## Metric coverage and extremes",
        "",
        "| Metric | Unit | Known | Unknown | Zero | Minimum | Maximum |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for column, metric in summary["metrics"].items():
        lines.append(
            f"| {metric['label']} | {metric['unit']} | {metric['known_count']:,} | {metric['unknown_count']:,} | {metric['zero_count']:,} | {_format_value(metric['minimum'], metric['unit'])} | {_format_value(metric['maximum'], metric['unit'])} |"
        )
    lines.extend([
        "",
        "The registered network count describes PeeringDB directory entries at the selected facility; it does not indicate bandwidth, traffic capacity, latency, or a service commitment.",
    ])
    for column, metric in summary["metrics"].items():
        lines.extend(["", f"### {metric['label']}", "", f"{metric['definition']} Direction: {metric['direction']}.", ""])
        lines.append("Five smallest known values:")
        lines.extend(
            f"- site `{row['site_id']}`, facility `{row['facility_id']}`, value `{_format_value(row['value'], metric['unit'])}`"
            for row in metric["minimum_examples"]
        )
        lines.append("Five largest known values:")
        lines.extend(
            f"- site `{row['site_id']}`, facility `{row['facility_id']}`, value `{_format_value(row['value'], metric['unit'])}`"
            for row in metric["maximum_examples"]
        )
        lines.append("Unknown-value examples:")
        if metric["unknown_examples"]:
            lines.extend(
                f"- site `{row['site_id']}`, facility `{row['facility_id']}`, value `Unknown`"
                for row in metric["unknown_examples"]
            )
        else:
            lines.append("- No unknown values in this build.")
    lines.extend(["", "## Fixed random sample", "", f"Seed: `{summary['fixed_random_sample']['seed']}`. Values are raw Parquet values; the sample selection method is recorded in the JSON.", "", "| site_id | facility_id | Substation km | Nearest facility km | Networks at same facility |", "|---:|---:|---:|---:|---:|"])
    for row in summary["fixed_random_sample"]["rows"]:
        lines.append(
            f"| {row['site_id']} | {row['facility_id'] if row['facility_id'] is not None else 'Unknown'} | {_format_value(row['substation_distance_km'], 'km')} | {_format_value(row['peering_facility_distance_km'], 'km')} | {_format_value(row['peering_facility_network_count'], 'registered networks')} |"
        )
    lines.extend(["", "## Scope limits", ""])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_files(snapshot_dir: Path, metrics_path: Path = DEFAULT_METRICS) -> tuple[Path, Path]:
    manifest, facilities = load_ready_snapshot(snapshot_dir)
    sites = pd.read_parquet(DEFAULT_SITES)
    metrics = pd.read_parquet(metrics_path)
    summary, markdown = build_connectivity_report(sites, metrics, facilities, manifest)
    _atomic_write(DEFAULT_SUMMARY, json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    _atomic_write(DEFAULT_REVIEW, markdown)
    return DEFAULT_SUMMARY, DEFAULT_REVIEW


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    args = parser.parse_args()
    summary_path, review_path = build_files(args.snapshot, args.metrics)
    print(json.dumps({"summary": str(summary_path), "review": str(review_path)}, indent=2))


if __name__ == "__main__":
    main()

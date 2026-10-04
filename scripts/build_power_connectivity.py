"""Build local power/connectivity tables from a ready PeeringDB snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.processing.peeringdb import FACILITY_COLUMNS, normalize_peering_facilities
from src.processing.power_connectivity import (
    CONNECTIVITY_COLUMNS,
    build_power_connectivity,
    connectivity_summary,
)

DEFAULT_SITES = ROOT / "data/processed/site_features.parquet"
DEFAULT_FACILITIES = ROOT / "data/processed/peering_facilities.parquet"
DEFAULT_METRICS = ROOT / "data/processed/site_connectivity_features.parquet"
DEFAULT_SUMMARY = ROOT / "outputs/validation/power_connectivity_summary.json"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read valid JSON from {path}") from error


def load_ready_snapshot(snapshot_dir: Path) -> tuple[dict, pd.DataFrame]:
    """Verify a complete snapshot and its normalized table before using it."""
    snapshot_dir = snapshot_dir.resolve()
    manifest_path = snapshot_dir / "manifest.json"
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("snapshot manifest must be a JSON object")
    snapshot_id = manifest.get("snapshot_id")
    if manifest.get("schema_version") != 1 or manifest.get("status") != "ready":
        raise ValueError("snapshot manifest must be schema v1 and ready")
    if not isinstance(snapshot_id, str) or snapshot_dir.name != snapshot_id:
        raise ValueError("snapshot manifest ID must match its directory")
    retrieved_at = manifest.get("retrieved_at")
    if not isinstance(retrieved_at, str) or not retrieved_at:
        raise ValueError("snapshot manifest is missing retrieved_at")

    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("ready snapshot must list its complete page traversal")
    raw_records: list[dict] = []
    expected_skip = 0
    saw_empty = False
    for index, entry in enumerate(pages):
        if not isinstance(entry, dict):
            raise ValueError(f"snapshot page {index} entry must be an object")
        if entry.get("http_status") != 200:
            raise ValueError(f"snapshot page {index} is not HTTP 200")
        parameters = entry.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError(f"snapshot page {index} is missing request parameters")
        try:
            limit = int(parameters["limit"])
            skip = int(parameters["skip"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"snapshot page {index} has invalid pagination") from error
        if limit < 1 or skip != expected_skip:
            raise ValueError(f"snapshot page {index} has a pagination gap")

        relative_file = entry.get("file")
        if not isinstance(relative_file, str):
            raise ValueError(f"snapshot page {index} has no file path")
        page_path = (snapshot_dir / relative_file).resolve()
        if not page_path.is_relative_to(snapshot_dir) or not page_path.is_file():
            raise ValueError(f"snapshot page {index} file is missing or escapes snapshot")
        body = page_path.read_bytes()
        expected_digest = entry.get("sha256")
        if not isinstance(expected_digest, str) or hashlib.sha256(body).hexdigest() != expected_digest:
            raise ValueError(f"snapshot page {index} SHA-256 mismatch")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"snapshot page {index} is not valid JSON") from error
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"snapshot page {index} data must be an array of objects")
        if len(rows) != entry.get("count"):
            raise ValueError(f"snapshot page {index} count does not match its data")
        if saw_empty:
            raise ValueError("snapshot contains pages after its terminal empty page")
        if rows:
            if len(rows) > limit:
                raise ValueError(f"snapshot page {index} exceeds its requested limit")
            expected_skip += len(rows)
            raw_records.extend(rows)
        else:
            if index != len(pages) - 1:
                raise ValueError("snapshot terminal empty page must be last")
            saw_empty = True
    if not saw_empty:
        raise ValueError("snapshot traversal is incomplete: terminal empty page is absent")
    if len(raw_records) != manifest.get("raw_row_count"):
        raise ValueError("snapshot raw row count does not match its manifest")

    expected_facilities, _, summary = normalize_peering_facilities(
        raw_records, snapshot_id, retrieved_at
    )
    normalized_path = snapshot_dir / "facilities.parquet"
    try:
        facilities = pd.read_parquet(normalized_path)
    except (OSError, ValueError, ImportError) as error:
        raise ValueError(f"cannot read normalized facilities table: {normalized_path}") from error
    if list(facilities.columns) != FACILITY_COLUMNS:
        raise ValueError("normalized facilities table has an unexpected schema")
    if facilities["snapshot_id"].isna().any() or not facilities[
        "snapshot_id"
    ].astype(str).eq(snapshot_id).all():
        raise ValueError("normalized facility rows do not match manifest snapshot ID")
    if not expected_facilities.empty:
        actual_sorted = facilities.sort_values("facility_id").reset_index(drop=True)
        expected_sorted = expected_facilities.sort_values("facility_id").reset_index(drop=True)
        try:
            pd.testing.assert_frame_equal(
                actual_sorted,
                expected_sorted,
                check_dtype=False,
                check_exact=True,
                check_like=False,
            )
        except AssertionError as error:
            raise ValueError("normalized facilities differ from raw snapshot pages") from error
    elif not facilities.empty:
        raise ValueError("normalized facilities differ from empty raw snapshot pages")
    if manifest.get("normalization") != summary:
        raise ValueError("snapshot normalization summary does not match raw pages")
    return manifest, facilities


def _write_parquet_temp(frame: pd.DataFrame, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp.parquet", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        frame.to_parquet(temporary, index=False)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def build_outputs(
    snapshot_dir: Path,
    *,
    sites_path: Path = DEFAULT_SITES,
    facilities_output: Path = DEFAULT_FACILITIES,
    metrics_output: Path = DEFAULT_METRICS,
    summary_output: Path = DEFAULT_SUMMARY,
) -> dict:
    """Build and publish both Parquet outputs and a compact validation summary."""
    manifest, facilities = load_ready_snapshot(snapshot_dir)
    snapshot_id = manifest["snapshot_id"]
    sites = pd.read_parquet(sites_path)
    needed = {"site_id", "lat", "lon", "substation_distance"}
    missing = needed - set(sites.columns)
    if missing:
        raise ValueError(f"site features missing required columns: {sorted(missing)}")
    if sites["site_id"].isna().any() or sites["site_id"].duplicated().any():
        raise ValueError("site_id must be non-null and unique")
    metrics = build_power_connectivity(sites, facilities, snapshot_id)
    if metrics.columns.tolist() != CONNECTIVITY_COLUMNS:
        raise ValueError("connectivity features have an unexpected schema")
    if len(metrics) != len(sites) or not metrics["site_id"].equals(
        sites["site_id"].reset_index(drop=True)
    ):
        raise ValueError("connectivity rows do not preserve the site input relation")
    if not metrics["peering_snapshot_id"].eq(snapshot_id).all():
        raise ValueError("connectivity rows contain mixed snapshots")
    if not connectivity_summary(metrics, facilities, snapshot_id)[
        "nearest_facility_relations_valid"
    ]:
        raise ValueError("connectivity rows reference an unknown facility")
    summary = connectivity_summary(metrics, facilities, snapshot_id)

    staged: list[tuple[Path, Path]] = []
    try:
        staged_facilities = _write_parquet_temp(facilities, facilities_output)
        staged.append((staged_facilities, facilities_output))
        staged_metrics = _write_parquet_temp(metrics, metrics_output)
        staged.append((staged_metrics, metrics_output))
        # Re-read staged files and validate before publishing either final path.
        checked_facilities = pd.read_parquet(staged_facilities)
        checked_metrics = pd.read_parquet(staged_metrics)
        if len(checked_facilities) != len(facilities) or len(checked_metrics) != len(sites):
            raise ValueError("staged Parquet row counts do not match the inputs")
        if checked_metrics["site_id"].tolist() != sites["site_id"].tolist():
            raise ValueError("staged connectivity table changed site order")
        for temporary, output in staged:
            os.replace(temporary, output)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_temp = summary_output.with_name(f".{summary_output.name}.tmp")
    summary_temp.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(summary_temp, summary_output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot", type=Path, required=True,
        help="path to a completed local PeeringDB snapshot directory",
    )
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES)
    parser.add_argument("--facilities-output", type=Path, default=DEFAULT_FACILITIES)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    result = build_outputs(
        args.snapshot,
        sites_path=args.sites,
        facilities_output=args.facilities_output,
        metrics_output=args.metrics_output,
        summary_output=args.summary_output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

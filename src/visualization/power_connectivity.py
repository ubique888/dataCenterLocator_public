"""Validate and serialize the supplemental power/connectivity page data."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _ids(frame: pd.DataFrame, column: str, label: str) -> list[int]:
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any():
        raise ValueError(f"{label} must be non-null")
    numbers = values.to_numpy(dtype="float64")
    if not (numbers > 0).all() or not (numbers == numbers.astype("int64")).all():
        raise ValueError(f"{label} must contain positive integer IDs")
    result = values.astype("int64").tolist()
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must be unique")
    return result


def _nullable_number(value: Any, label: str, *, nonnegative: bool = True) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be a finite number or null") from error
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ValueError(f"{label} must be a finite nonnegative number or null")
    return number


def _nullable_integer(value: Any, label: str) -> int | None:
    number = _nullable_number(value, label)
    if number is None:
        return None
    if not number.is_integer():
        raise ValueError(f"{label} must be a nonnegative integer or null")
    return int(number)


def _nullable_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text if text else None


def connectivity_payload(
    sites: pd.DataFrame,
    metrics: pd.DataFrame,
    facilities: pd.DataFrame,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Build a schema-v1 JSON-safe payload, rejecting stale or dangling joins."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("PeeringDB manifest must be schema v1")
    snapshot_id = manifest.get("snapshot_id")
    retrieved_at = manifest.get("retrieved_at")
    if manifest.get("status") != "ready" or not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("PeeringDB manifest must identify a ready snapshot")
    if not isinstance(retrieved_at, str) or not retrieved_at:
        raise ValueError("PeeringDB manifest must include retrieved_at")

    required_sites = {"site_id"}
    required_metrics = {
        "site_id", "substation_distance_km", "peering_facility_id",
        "peering_facility_distance_km", "peering_facility_network_count",
        "connectivity_status", "peering_snapshot_id",
    }
    required_facilities = {
        "facility_id", "name", "city", "state", "latitude", "longitude",
        "network_count", "source_updated_at", "snapshot_id",
    }
    for label, frame, required in (
        ("sites", sites, required_sites),
        ("metrics", metrics, required_metrics),
        ("facilities", facilities, required_facilities),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} missing required columns: {sorted(missing)}")

    site_ids = _ids(sites, "site_id", "site_id")
    metric_ids = _ids(metrics, "site_id", "metrics site_id")
    if set(site_ids) != set(metric_ids) or len(site_ids) != len(metric_ids):
        raise ValueError("site ID sets must match exactly between sites and metrics")
    facility_ids = _ids(facilities, "facility_id", "facility_id")
    metrics_by_id = metrics.assign(
        _site_id=pd.to_numeric(metrics["site_id"]).astype("int64")
    ).set_index("_site_id", drop=False)
    facilities_by_id = facilities.assign(
        _facility_id=pd.to_numeric(facilities["facility_id"]).astype("int64")
    ).set_index("_facility_id", drop=False)

    if metrics["peering_snapshot_id"].isna().any() or not metrics[
        "peering_snapshot_id"
    ].astype(str).eq(snapshot_id).all():
        raise ValueError("connectivity metrics snapshot does not match manifest")
    if not facilities.empty and (
        facilities["snapshot_id"].isna().any()
        or not facilities["snapshot_id"].astype(str).eq(snapshot_id).all()
    ):
        raise ValueError("facility dimension snapshot does not match manifest")

    status_values = {"matched", "invalid_site_coordinates", "no_eligible_facilities"}
    site_payload: dict[str, dict[str, Any]] = {}
    referenced_ids: set[int] = set()
    for site_id in site_ids:
        metric = metrics_by_id.loc[site_id]
        if isinstance(metric, pd.DataFrame):
            raise ValueError("metrics site_id must be unique")
        status = _nullable_text(metric["connectivity_status"])
        if status not in status_values:
            raise ValueError(f"unknown connectivity status for site {site_id}")
        raw_facility_id = metric["peering_facility_id"]
        facility_id = _nullable_integer(raw_facility_id, "peering_facility_id")
        peer_km = _nullable_number(
            metric["peering_facility_distance_km"], "peering_facility_distance_km"
        )
        peer_networks = _nullable_integer(
            metric["peering_facility_network_count"],
            "peering_facility_network_count",
        )
        if status == "matched":
            if facility_id is None or peer_km is None:
                raise ValueError("matched connectivity rows require a facility ID and distance")
        elif facility_id is not None or peer_km is not None:
            raise ValueError("unmatched connectivity rows cannot reference a facility")
        if facility_id is not None:
            if facility_id not in facilities_by_id.index:
                raise ValueError(f"unknown facility ID {facility_id} in connectivity metrics")
            referenced_ids.add(facility_id)
            dimension_networks = _nullable_integer(
                facilities_by_id.loc[facility_id, "network_count"],
                "facility network_count",
            )
            if peer_networks != dimension_networks:
                raise ValueError("network count in metrics does not match facility dimension")
        elif peer_networks is not None:
            raise ValueError("network count requires a selected facility")

        site_payload[str(site_id)] = {
            "subKm": _nullable_number(
                metric["substation_distance_km"], "substation_distance_km"
            ),
            "peerKm": peer_km,
            "peerId": facility_id,
            "peerNetworks": peer_networks,
            "status": status,
        }

    facility_payload: dict[str, dict[str, Any]] = {}
    for facility_id in sorted(referenced_ids):
        row = facilities_by_id.loc[facility_id]
        latitude = _nullable_number(row["latitude"], "facility latitude", nonnegative=False)
        longitude = _nullable_number(row["longitude"], "facility longitude", nonnegative=False)
        if latitude is None or longitude is None or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"facility {facility_id} has invalid coordinates")
        if latitude == 0 and longitude == 0:
            raise ValueError(f"facility {facility_id} has placeholder coordinates")
        facility_payload[str(facility_id)] = {
            "id": facility_id,
            "name": _nullable_text(row["name"]),
            "city": _nullable_text(row["city"]),
            "state": _nullable_text(row["state"]),
            "lat": latitude,
            "lon": longitude,
            "networks": _nullable_integer(row["network_count"], "facility network_count"),
            "sourceUpdatedAt": _nullable_text(row["source_updated_at"]),
            "url": f"https://www.peeringdb.com/fac/{facility_id}",
        }

    return {
        "schema_version": 1,
        "meta": {
            "snapshot_id": snapshot_id,
            "retrieved_at": retrieved_at,
            "epa_source_version": "EPA RE-Powering America’s Land Initiative, 2022 release updated 2023",
            "candidate_scope": "Existing EPA screened candidates · ≥50-acre source cohort",
            "facility_scope": "US PeeringDB facilities hosting at least one IXP",
        },
        "sites": site_payload,
        "facilities": facility_payload,
    }

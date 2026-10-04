"""Normalize public PeeringDB facility snapshots for screening."""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

import pandas as pd

FACILITY_COLUMNS = [
    "facility_id",
    "name",
    "country",
    "state",
    "city",
    "latitude",
    "longitude",
    "ix_count",
    "network_count",
    "source_updated_at",
    "retrieved_at",
    "snapshot_id",
]

REQUIRED_ELIGIBILITY_FIELDS = frozenset(
    {
        "id", "country", "latitude", "longitude", "status", "ix_count",
    }
)


def _nonnegative_integer(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return None
    return int(number)


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_peering_facilities(
    records: list[dict[str, Any]], snapshot_id: str, retrieved_at: str
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Return eligible US IXP facilities, rejected source rows and audit counts.

    Eligibility requires an active US PeeringDB listing, valid non-placeholder
    coordinates, and a valid positive IXP count. A missing network count is
    retained as null because it is a display metric, not the eligibility gate.
    Conflicting records for the same stable PeeringDB ID make the whole
    snapshot ambiguous and therefore fail closed.
    """
    eligible: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: dict[int, str] = {}
    duplicate_rows_removed = 0
    rejected_reasons: Counter[str] = Counter()

    def reject(record: Any, reason: str) -> None:
        rejected_reasons[reason] += 1
        rejected.append(
            {
                "source_id": record.get("id") if isinstance(record, dict) else None,
                "rejection_reason": reason,
                "raw_record": json.dumps(
                    record, ensure_ascii=False, sort_keys=True, default=str
                ),
            }
        )

    for record in records:
        if not isinstance(record, dict):
            reject(record, "invalid_record")
            continue
        missing_fields = REQUIRED_ELIGIBILITY_FIELDS.difference(record)
        if missing_fields:
            raise ValueError(
                "PeeringDB facility record missing required fields: "
                f"{', '.join(sorted(missing_fields))}"
            )

        facility_id = _nonnegative_integer(record.get("id"))
        if facility_id is None or facility_id == 0:
            reject(record, "invalid_id")
            continue
        canonical = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            default=str,
        )
        previous = seen.get(facility_id)
        if previous is not None:
            if previous != canonical:
                raise ValueError(f"conflicting PeeringDB facility ID {facility_id}")
            duplicate_rows_removed += 1
            continue
        seen[facility_id] = canonical

        country = _text(record.get("country"))
        status = _text(record.get("status"))
        if country != "US":
            reject(record, "not_us")
            continue
        if status != "ok":
            reject(record, "not_active")
            continue

        latitude = _finite_number(record.get("latitude"))
        longitude = _finite_number(record.get("longitude"))
        if (
            latitude is None
            or longitude is None
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
            or (latitude == 0 and longitude == 0)
        ):
            reject(record, "invalid_coordinates")
            continue

        ix_count = _nonnegative_integer(record.get("ix_count"))
        if ix_count is None:
            reject(record, "invalid_ix_count")
            continue
        if ix_count == 0:
            reject(record, "no_ixp")
            continue

        network_count = _nonnegative_integer(record.get("net_count"))
        eligible.append(
            {
                "facility_id": facility_id,
                "name": _text(record.get("name")),
                "country": country,
                "state": _text(record.get("state")),
                "city": _text(record.get("city")),
                "latitude": latitude,
                "longitude": longitude,
                "ix_count": ix_count,
                "network_count": network_count,
                "source_updated_at": _text(record.get("updated")),
                "retrieved_at": retrieved_at,
                "snapshot_id": snapshot_id,
            }
        )

    facilities = pd.DataFrame(eligible, columns=FACILITY_COLUMNS)
    if not facilities.empty:
        facilities = facilities.astype(
            {
                "facility_id": "int64",
                "ix_count": "int64",
                "network_count": "Int64",
            }
        )
        if facilities["facility_id"].duplicated().any():
            raise ValueError("normalized PeeringDB facility IDs must be unique")
    rejected_frame = pd.DataFrame(
        rejected, columns=["source_id", "rejection_reason", "raw_record"]
    )
    summary = {
        "raw_count": len(records),
        "eligible_count": len(facilities),
        "rejected_count": len(rejected_frame),
        "duplicate_rows_removed": duplicate_rows_removed,
        "network_count_missing": int(facilities["network_count"].isna().sum()),
        "rejected_by_reason": dict(sorted(rejected_reasons.items())),
        "snapshot_id": snapshot_id,
        "retrieved_at": retrieved_at,
    }
    return facilities, rejected_frame, summary

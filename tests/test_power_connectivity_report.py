import hashlib

import pandas as pd
import pytest

from scripts.build_power_connectivity_report import build_connectivity_report


def report_inputs():
    sites = pd.DataFrame({"site_id": [1, 2, 3, 4, 5, 6]})
    metrics = pd.DataFrame(
        {
            "site_id": [1, 2, 3, 4, 5, 6],
            "substation_distance_km": [0.0, 1.0, 2.0, None, 4.0, 5.0],
            "peering_facility_id": pd.Series([10, 10, 11, 11, 12, pd.NA], dtype="Int64"),
            "peering_facility_distance_km": [1.0, 2.0, 3.0, 4.0, 5.0, None],
            "peering_facility_network_count": pd.Series([1, 1, 0, 0, pd.NA, pd.NA], dtype="Int64"),
            "connectivity_status": ["matched"] * 5 + ["invalid_site_coordinates"],
            "peering_snapshot_id": ["snapshot-a"] * 6,
        }
    )
    facilities = pd.DataFrame(
        {
            "facility_id": pd.Series([10, 11, 12], dtype="int64"),
            "network_count": pd.Series([1, 0, pd.NA], dtype="Int64"),
            "snapshot_id": ["snapshot-a"] * 3,
        }
    )
    page_hashes = ["a" * 64, "b" * 64, "c" * 64]
    manifest = {
        "schema_version": 1,
        "snapshot_id": "snapshot-a",
        "status": "ready",
        "started_at": "2026-10-03T12:00:00Z",
        "completed_at": "2026-10-03T12:01:00Z",
        "retrieved_at": "2026-10-03T12:01:00Z",
        "raw_row_count": 5,
        "pages": [
            {"file": "pages/1.json", "sha256": page_hashes[0], "count": 2},
            {"file": "pages/2.json", "sha256": page_hashes[1], "count": 3},
            {"file": "pages/3.json", "sha256": page_hashes[2], "count": 0},
        ],
        "normalization": {
            "raw_count": 5,
            "eligible_count": 3,
            "rejected_count": 2,
            "duplicate_rows_removed": 0,
            "network_count_missing": 1,
            "rejected_by_reason": {"invalid_coordinates": 1, "no_ixp": 1},
            "snapshot_id": "snapshot-a",
            "retrieved_at": "2026-10-03T12:01:00Z",
        },
    }
    return sites, metrics, facilities, manifest


def test_report_matches_manifest_and_metric_coverage_with_stable_examples():
    sites, metrics, facilities, manifest = report_inputs()

    summary, markdown = build_connectivity_report(sites, metrics, facilities, manifest)

    expected_hash = hashlib.sha256((
        "pages/1.json\n" + "a" * 64 + "\n" +
        "pages/2.json\n" + "b" * 64 + "\n" +
        "pages/3.json\n" + "c" * 64 + "\n"
    ).encode()).hexdigest()
    assert summary["peeringdb"]["raw_row_count"] == 5
    assert summary["peeringdb"]["eligible_facility_count"] == 3
    assert summary["peeringdb"]["rejected_by_reason"] == {"invalid_coordinates": 1, "no_ixp": 1}
    assert summary["peeringdb"]["snapshot_sha256"] == expected_hash
    assert summary["candidate_linkage"]["site_rows"] == 6
    assert summary["candidate_linkage"]["status_counts"] == {
        "invalid_site_coordinates": 1,
        "matched": 5,
    }
    assert summary["metrics"]["substation_distance_km"]["unknown_count"] == 1
    assert summary["metrics"]["peering_facility_distance_km"]["unknown_count"] == 1
    assert summary["metrics"]["peering_facility_network_count"]["zero_count"] == 2
    assert len(summary["fixed_random_sample"]["rows"]) == 5
    assert all("site_id" in row and "facility_id" in row for row in summary["fixed_random_sample"]["rows"])
    assert "does not indicate" in markdown
    assert "network count" in markdown.lower()


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda s, m, f, d: (s.iloc[:-1], m, f, d), "site ID sets"),
        (lambda s, m, f, d: (s, m.assign(peering_snapshot_id="snapshot-b"), f, d), "snapshot"),
        (lambda s, m, f, d: (s, m.assign(peering_facility_id=pd.Series([99, 10, 11, 11, 12, pd.NA], dtype="Int64")), f, d), "unknown facility"),
    ],
)
def test_report_rejects_inconsistent_inputs(change, message):
    inputs = change(*report_inputs())

    with pytest.raises(ValueError, match=message):
        build_connectivity_report(*inputs)

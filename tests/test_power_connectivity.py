import hashlib
import json

import pandas as pd
import pytest

from scripts.build_power_connectivity import build_outputs, load_ready_snapshot
from src.processing.peeringdb import normalize_peering_facilities
from src.processing.power_connectivity import build_power_connectivity


def make_sites():
    return pd.DataFrame(
        {
            "site_id": pd.Series([10, 20, 30], dtype="int64"),
            "lat": [0.0, 0.0, float("nan")],
            "lon": [-78.0, -77.0, -77.0],
            "substation_distance": [1.0, None, 3.5],
        }
    )


def make_facilities():
    return pd.DataFrame(
        {
            "facility_id": pd.Series([10, 30], dtype="int64"),
            "name": ["Closest with missing count", "Farther listed network"],
            "latitude": [0.0, 0.0],
            "longitude": [-77.0, -81.0],
            "ix_count": pd.Series([1, 1], dtype="int64"),
            "network_count": pd.Series([pd.NA, 88], dtype="Int64"),
            "snapshot_id": ["snapshot-a", "snapshot-a"],
        }
    )


def test_builds_one_nearest_facility_row_per_site_and_keeps_same_facility_count():
    result = build_power_connectivity(make_sites(), make_facilities(), "snapshot-a")

    assert result.site_id.tolist() == [10, 20, 30]
    assert result.site_id.is_unique
    first = result.set_index("site_id").loc[10]
    assert first.substation_distance_km == pytest.approx(1.609344)
    assert first.peering_facility_id == 10
    assert first.peering_facility_distance_km == pytest.approx(111.319, abs=0.002)
    assert pd.isna(first.peering_facility_network_count)
    assert first.connectivity_status == "matched"
    assert result.set_index("site_id").loc[20, "connectivity_status"] == "matched"
    assert result.set_index("site_id").loc[30, "connectivity_status"] == "invalid_site_coordinates"


def test_finds_facility_without_an_arbitrary_distance_cutoff():
    sites = pd.DataFrame(
        {"site_id": [1], "lat": [0.0], "lon": [0.0], "substation_distance": [0.0]}
    )
    facilities = make_facilities().iloc[[0]].copy()
    facilities.loc[:, "longitude"] = 25.0

    result = build_power_connectivity(sites, facilities, "snapshot-a").iloc[0]

    assert result.connectivity_status == "matched"
    assert result.peering_facility_distance_km > 1000


def test_deterministically_chooses_lower_id_for_equidistant_facilities():
    sites = pd.DataFrame(
        {"site_id": [1], "lat": [0.0], "lon": [0.0], "substation_distance": [0.0]}
    )
    facilities = make_facilities().copy()
    facilities.loc[:, "latitude"] = 0.0
    facilities.loc[:, "longitude"] = [-1.0, 1.0]

    result = build_power_connectivity(sites, facilities, "snapshot-a").iloc[0]

    assert result.peering_facility_id == 10


def test_distinguishes_no_eligible_facilities_from_invalid_site_coordinates():
    sites = make_sites()
    result = build_power_connectivity(
        sites, make_facilities().iloc[0:0], "snapshot-a"
    )

    assert result.loc[result.site_id.eq(10), "connectivity_status"].item() == "no_eligible_facilities"
    assert result.loc[result.site_id.eq(30), "connectivity_status"].item() == "invalid_site_coordinates"
    assert result.peering_facility_distance_km.isna().all()


def test_rejects_duplicate_site_ids_duplicate_facility_ids_and_snapshot_mismatch():
    sites = make_sites()
    duplicate_sites = pd.concat([sites, sites.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="site_id.*unique"):
        build_power_connectivity(duplicate_sites, make_facilities(), "snapshot-a")

    duplicate_facilities = pd.concat(
        [make_facilities(), make_facilities().iloc[[0]]], ignore_index=True
    )
    with pytest.raises(ValueError, match="facility_id.*unique"):
        build_power_connectivity(sites, duplicate_facilities, "snapshot-a")

    with pytest.raises(ValueError, match="snapshot"):
        build_power_connectivity(sites, make_facilities(), "snapshot-b")


def test_handles_antimeridian_distance_with_wgs84_geodesics():
    sites = pd.DataFrame(
        {"site_id": [1], "lat": [0.0], "lon": [179.9], "substation_distance": [2.0]}
    )
    facilities = make_facilities().iloc[[0]].copy()
    facilities.loc[:, "longitude"] = -179.9

    result = build_power_connectivity(sites, facilities, "snapshot-a").iloc[0]

    assert result.peering_facility_distance_km == pytest.approx(22.264, abs=0.01)


def make_ready_snapshot(snapshot_dir):
    snapshot_dir.mkdir(parents=True)
    pages_dir = snapshot_dir / "pages"
    pages_dir.mkdir()
    snapshot_id = snapshot_dir.name
    retrieved_at = "2026-10-03T22:52:37.460806Z"
    raw_rows = [
        {
            "id": 10,
            "name": "Nearest IX",
            "country": "US",
            "state": "VA",
            "city": "Ashburn",
            "latitude": 38.0,
            "longitude": -77.0,
            "status": "ok",
            "ix_count": 1,
            "net_count": 20,
            "updated": "2026-10-01T00:00:00Z",
        }
    ]
    page_payloads = [{"data": raw_rows}, {"data": []}]
    page_entries = []
    for index, payload in enumerate(page_payloads):
        body = json.dumps(payload, separators=(",", ":")).encode()
        filename = f"fac_page_{index:05d}.json"
        (pages_dir / filename).write_bytes(body)
        count = len(payload["data"])
        page_entries.append(
            {
                "file": f"pages/{filename}",
                "sha256": hashlib.sha256(body).hexdigest(),
                "count": count,
                "http_status": 200,
                "parameters": {
                    "country": "US",
                    "status": "ok",
                    "depth": "0",
                    "fields": "id,name,country,state,city,latitude,longitude,status,ix_count,net_count,updated",
                    "limit": 250,
                    "skip": 0 if index == 0 else 1,
                },
            }
        )
    facilities, _, normalization = normalize_peering_facilities(
        raw_rows, snapshot_id, retrieved_at
    )
    facilities.to_parquet(snapshot_dir / "facilities.parquet", index=False)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "snapshot_id": snapshot_id,
                "status": "ready",
                "started_at": retrieved_at,
                "completed_at": retrieved_at,
                "retrieved_at": retrieved_at,
                "request_base": "https://www.peeringdb.com/api/fac",
                "raw_row_count": len(raw_rows),
                "pages": page_entries,
                "normalization": normalization,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return raw_rows


def test_ready_snapshot_loader_checks_pages_and_normalized_facilities(tmp_path):
    snapshot_dir = tmp_path / "snapshot-a"
    make_ready_snapshot(snapshot_dir)

    manifest, facilities = load_ready_snapshot(snapshot_dir)

    assert manifest["snapshot_id"] == "snapshot-a"
    assert facilities.facility_id.tolist() == [10]


def test_ready_snapshot_loader_rejects_a_tampered_page(tmp_path):
    snapshot_dir = tmp_path / "snapshot-a"
    make_ready_snapshot(snapshot_dir)
    (snapshot_dir / "pages/fac_page_00000.json").write_text('{"data":[]}', encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        load_ready_snapshot(snapshot_dir)


def test_build_outputs_requires_and_uses_a_local_snapshot_without_fetching(tmp_path):
    snapshot_dir = tmp_path / "snapshot-a"
    make_ready_snapshot(snapshot_dir)
    sites_path = tmp_path / "sites.parquet"
    pd.DataFrame(
        {"site_id": [3], "lat": [38.0], "lon": [-77.0], "substation_distance": [1.0]}
    ).to_parquet(sites_path, index=False)
    facilities_output = tmp_path / "out/facilities.parquet"
    metrics_output = tmp_path / "out/metrics.parquet"
    summary_output = tmp_path / "out/summary.json"

    summary = build_outputs(
        snapshot_dir,
        sites_path=sites_path,
        facilities_output=facilities_output,
        metrics_output=metrics_output,
        summary_output=summary_output,
    )

    facilities = pd.read_parquet(facilities_output)
    metrics = pd.read_parquet(metrics_output)
    assert facilities.facility_id.tolist() == [10]
    assert metrics.loc[0, "peering_facility_id"] == 10
    assert metrics.loc[0, "peering_facility_network_count"] == 20
    assert summary["nearest_facility_relations_valid"] is True
    assert json.loads(summary_output.read_text(encoding="utf-8"))["snapshot_id"] == "snapshot-a"
